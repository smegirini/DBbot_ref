"""
AI Service
AI API 통합 및 폴백 처리
"""
from typing import Optional, Dict, Any
from enum import Enum
import re
import httpx
from openai import AsyncAzureOpenAI
import google.generativeai as genai
from anthropic import AsyncAnthropic

from app.config import settings
from app.utils import (
    LoggerMixin,
    ai_service_breaker,
    AIServiceError,
    ConfigurationError
)


class AIProvider(str, Enum):
    """AI Provider 종류"""
    AZURE_OPENAI = "azure_openai"
    GEMINI = "gemini"
    CLAUDE = "claude"


def remove_markdown(text: str) -> str:
    """
    마크다운 문법을 제거하고 플레인 텍스트로 변환
    카카오톡은 마크다운을 지원하지 않으므로 제거 필요

    Args:
        text: 마크다운이 포함된 텍스트

    Returns:
        str: 플레인 텍스트
    """
    # 코드 블록 제거 (```로 감싸진 부분)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # 헤더 제거 (# ## ### 등)
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)

    # 볼드/이탤릭 제거 (**text**, *text*, __text__, _text_)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)

    # 링크 제거 [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # 이미지 제거 ![alt](url) -> alt
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)

    # 리스트 마커 제거 (-, *, +, 숫자.)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

    # 인용문 제거 (>)
    text = re.sub(r'^\s*>\s+', '', text, flags=re.MULTILINE)

    # 수평선 제거 (---, ***, ___)
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # 연속된 빈 줄을 하나로 합치기
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


class AIService(LoggerMixin):
    """
    AI 서비스 통합 클래스

    우선순위:
    1. Azure OpenAI
    2. Google Gemini
    3. Anthropic Claude
    """

    def __init__(self):
        """Initialize AI service with configured providers"""
        self._azure_client: Optional[AsyncAzureOpenAI] = None
        self._anthropic_client: Optional[AsyncAnthropic] = None
        self._gemini_configured = False

        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize AI clients based on configuration"""
        # Azure OpenAI
        if settings.azure_openai.is_configured:
            try:
                self._azure_client = AsyncAzureOpenAI(
                    api_key=settings.azure_openai.api_key,
                    api_version=settings.azure_openai.api_version,
                    azure_endpoint=settings.azure_openai.endpoint
                )
                self.logger.info("azure_openai_initialized")
            except Exception as e:
                self.logger.error("azure_openai_init_failed", error=str(e))

        # Google Gemini
        if settings.gemini.is_configured:
            try:
                genai.configure(api_key=settings.gemini.api_key)
                self._gemini_configured = True
                self.logger.info("gemini_initialized")
            except Exception as e:
                self.logger.error("gemini_init_failed", error=str(e))

        # Anthropic Claude
        if settings.anthropic.is_configured:
            try:
                self._anthropic_client = AsyncAnthropic(
                    api_key=settings.anthropic.api_key
                )
                self.logger.info("anthropic_initialized")
            except Exception as e:
                self.logger.error("anthropic_init_failed", error=str(e))

    @ai_service_breaker
    async def generate_text(
        self,
        prompt: str,
        provider: Optional[AIProvider] = None,
        **kwargs
    ) -> str:
        """
        Generate text using AI

        Args:
            prompt: Input prompt
            provider: Preferred AI provider (optional)
            **kwargs: Additional parameters

        Returns:
            str: Generated text

        Raises:
            AIServiceError: If all providers fail
        """
        # Try preferred provider first
        if provider:
            try:
                return await self._generate_with_provider(provider, prompt, **kwargs)
            except Exception as e:
                self.logger.warning(
                    "ai_provider_failed",
                    provider=provider,
                    error=str(e)
                )

        # Fallback chain: Azure OpenAI -> Gemini -> Claude
        providers = [
            (AIProvider.AZURE_OPENAI, self._azure_client is not None),
            (AIProvider.GEMINI, self._gemini_configured),
            (AIProvider.CLAUDE, self._anthropic_client is not None)
        ]

        last_error = None
        for prov, is_configured in providers:
            if not is_configured or prov == provider:
                continue

            try:
                return await self._generate_with_provider(prov, prompt, **kwargs)
            except Exception as e:
                self.logger.warning(
                    "ai_fallback_failed",
                    provider=prov,
                    error=str(e)
                )
                last_error = e

        # All providers failed
        raise AIServiceError(
            "All AI providers failed",
            details={"last_error": str(last_error) if last_error else None}
        )

    async def _generate_with_provider(
        self,
        provider: AIProvider,
        prompt: str,
        **kwargs
    ) -> str:
        """
        Generate text with specific provider

        Args:
            provider: AI provider
            prompt: Input prompt
            **kwargs: Additional parameters

        Returns:
            str: Generated text
        """
        match provider:
            case AIProvider.AZURE_OPENAI:
                return await self._generate_azure(prompt, **kwargs)
            case AIProvider.GEMINI:
                return await self._generate_gemini(prompt, **kwargs)
            case AIProvider.CLAUDE:
                return await self._generate_claude(prompt, **kwargs)
            case _:
                raise AIServiceError(f"Unknown provider: {provider}")

    async def _generate_azure(self, prompt: str, **kwargs) -> str:
        """Generate text using Azure OpenAI"""
        if not self._azure_client:
            raise ConfigurationError("Azure OpenAI not configured")

        try:
            response = await self._azure_client.chat.completions.create(
                model=kwargs.get('model', settings.azure_openai.model),
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=kwargs.get('max_tokens', 2000),
                temperature=kwargs.get('temperature', 0.7)
            )

            result = response.choices[0].message.content
            self.logger.info("azure_generation_success", prompt_length=len(prompt))
            # 마크다운 제거 (카카오톡 호환성)
            return remove_markdown(result)

        except Exception as e:
            self.logger.error("azure_generation_failed", error=str(e))
            raise AIServiceError(f"Azure OpenAI failed: {str(e)}")

    async def _generate_gemini(self, prompt: str, **kwargs) -> str:
        """Generate text using Google Gemini"""
        if not self._gemini_configured:
            raise ConfigurationError("Gemini not configured")

        try:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            def _sync_generate():
                """동기 방식으로 Gemini 호출"""
                model = genai.GenerativeModel(
                    kwargs.get('model', settings.gemini.model)
                )

                response = model.generate_content(
                    prompt,
                    generation_config={
                        'temperature': kwargs.get('temperature', settings.gemini.temperature),
                        'max_output_tokens': kwargs.get('max_tokens', settings.gemini.max_tokens)
                    }
                )
                return response.text

            # 별도 스레드에서 동기 함수 실행
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, _sync_generate)

            self.logger.info("gemini_generation_success", prompt_length=len(prompt))
            # 마크다운 제거 (카카오톡 호환성)
            return remove_markdown(result)

        except Exception as e:
            self.logger.error("gemini_generation_failed", error=str(e))
            raise AIServiceError(f"Gemini failed: {str(e)}")

    async def _generate_claude(self, prompt: str, **kwargs) -> str:
        """Generate text using Anthropic Claude"""
        if not self._anthropic_client:
            raise ConfigurationError("Claude not configured")

        try:
            response = await self._anthropic_client.messages.create(
                model=kwargs.get('model', settings.anthropic.model),
                max_tokens=kwargs.get('max_tokens', settings.anthropic.max_tokens),
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            result = response.content[0].text
            self.logger.info("claude_generation_success", prompt_length=len(prompt))
            # 마크다운 제거 (카카오톡 호환성)
            return remove_markdown(result)

        except Exception as e:
            self.logger.error("claude_generation_failed", error=str(e))
            raise AIServiceError(f"Claude failed: {str(e)}")

    async def analyze_text(
        self,
        text: str,
        analysis_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Analyze text using AI

        Args:
            text: Text to analyze
            analysis_type: Type of analysis (general, sentiment, summary, etc.)

        Returns:
            Dict[str, Any]: Analysis results
        """
        prompts = {
            "general": f"다음 텍스트를 분석해주세요:\n\n{text}",
            "sentiment": f"다음 텍스트의 감정을 분석해주세요:\n\n{text}",
            "summary": f"다음 텍스트를 요약해주세요:\n\n{text}",
            "keywords": f"다음 텍스트의 주요 키워드를 추출해주세요:\n\n{text}"
        }

        prompt = prompts.get(analysis_type, prompts["general"])
        result = await self.generate_text(prompt)

        return {
            "analysis_type": analysis_type,
            "result": result,
            "original_text_length": len(text)
        }
