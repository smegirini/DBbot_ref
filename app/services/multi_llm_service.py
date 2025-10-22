"""
Multi-Provider LLM Service
Cerebras, Groq, Anthropic 멀티 프로바이더 LLM 통합 with 자동 폴백
"""
import os
from typing import Optional, Dict, Any
from enum import Enum

from app.config import settings
from app.utils import LoggerMixin, ExternalServiceError

try:
    from cerebras.cloud.sdk import Cerebras
    CEREBRAS_AVAILABLE = True
except ImportError:
    CEREBRAS_AVAILABLE = False

try:
    import groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


class LLMProvider(str, Enum):
    """LLM 프로바이더 종류"""
    CEREBRAS = "cerebras"
    GROQ = "groq"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    GEMINI = "gemini"


class MultiLLMService(LoggerMixin):
    """
    멀티 프로바이더 LLM 서비스

    우선순위:
    1. Cerebras (빠른 추론)
    2. Groq (고품질 응답)
    3. Anthropic Claude (고급 추론)
    4. Azure OpenAI (폴백)
    5. Gemini (최종 폴백)
    """

    def __init__(self):
        """Initialize Multi-LLM service"""
        self._cerebras_client: Optional[Cerebras] = None
        self._groq_client: Optional[groq.Client] = None

        # Cerebras 초기화
        if CEREBRAS_AVAILABLE and settings.cerebras.is_configured:
            try:
                self._cerebras_client = Cerebras(api_key=settings.cerebras.api_key)
                self.logger.info("cerebras_initialized")
            except Exception as e:
                self.logger.error("cerebras_init_failed", error=str(e))

        # Groq 초기화
        if GROQ_AVAILABLE and settings.groq.is_configured:
            try:
                self._groq_client = groq.Client(api_key=settings.groq.api_key)
                self.logger.info("groq_initialized")
            except Exception as e:
                self.logger.error("groq_init_failed", error=str(e))

        self.logger.info(
            "multi_llm_service_initialized",
            cerebras=self._cerebras_client is not None,
            groq=self._groq_client is not None,
            anthropic=settings.anthropic.is_configured,
            azure=settings.azure_openai.is_configured,
            gemini=settings.gemini.is_configured
        )

    async def generate_with_fallback(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
        preferred_provider: Optional[LLMProvider] = None
    ) -> str:
        """
        폴백 체인으로 텍스트 생성

        Args:
            prompt: 입력 프롬프트
            temperature: 온도 (0.0~2.0)
            max_tokens: 최대 토큰 수
            system_prompt: 시스템 프롬프트 (optional)
            preferred_provider: 선호 프로바이더 (optional)

        Returns:
            생성된 텍스트

        Raises:
            ExternalServiceError: 모든 프로바이더 실패 시
        """
        # 우선순위 설정
        if preferred_provider:
            providers = [preferred_provider]
            # 폴백 추가
            for p in [LLMProvider.CEREBRAS, LLMProvider.GROQ, LLMProvider.ANTHROPIC, LLMProvider.AZURE, LLMProvider.GEMINI]:
                if p != preferred_provider and p not in providers:
                    providers.append(p)
        else:
            providers = [
                LLMProvider.CEREBRAS,
                LLMProvider.GROQ,
                LLMProvider.ANTHROPIC,
                LLMProvider.AZURE,
                LLMProvider.GEMINI
            ]

        last_error = None

        for provider in providers:
            try:
                match provider:
                    case LLMProvider.CEREBRAS:
                        if self._cerebras_client:
                            return await self._generate_cerebras(prompt, temperature, max_tokens, system_prompt)

                    case LLMProvider.GROQ:
                        if self._groq_client:
                            return await self._generate_groq(prompt, temperature, max_tokens, system_prompt)

                    case LLMProvider.ANTHROPIC:
                        if settings.anthropic.is_configured:
                            return await self._generate_anthropic(prompt, temperature, max_tokens, system_prompt)

                    case LLMProvider.AZURE:
                        if settings.azure_openai.is_configured:
                            return await self._generate_azure(prompt, temperature, max_tokens, system_prompt)

                    case LLMProvider.GEMINI:
                        if settings.gemini.is_configured:
                            return await self._generate_gemini(prompt, temperature, max_tokens, system_prompt)

            except Exception as e:
                self.logger.warning(
                    "llm_provider_failed",
                    provider=provider,
                    error=str(e)
                )
                last_error = e
                continue

        # 모든 프로바이더 실패
        raise ExternalServiceError(
            f"모든 LLM 프로바이더 실패. 마지막 오류: {last_error}"
        )

    async def _generate_cerebras(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str]
    ) -> str:
        """Cerebras로 텍스트 생성"""
        try:
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            response = self._cerebras_client.chat.completions.create(
                model="llama-3.3-70b",  # Cerebras 기본 모델
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            result = response.choices[0].message.content
            self.logger.info("cerebras_generation_success", length=len(result))
            return result

        except Exception as e:
            self.logger.error("cerebras_generation_failed", error=str(e))
            raise ExternalServiceError(f"Cerebras 실패: {str(e)}")

    async def _generate_groq(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str]
    ) -> str:
        """Groq로 텍스트 생성"""
        try:
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            response = self._groq_client.chat.completions.create(
                model="llama-3.1-70b-versatile",  # Groq 기본 모델
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            result = response.choices[0].message.content
            self.logger.info("groq_generation_success", length=len(result))
            return result

        except Exception as e:
            self.logger.error("groq_generation_failed", error=str(e))
            raise ExternalServiceError(f"Groq 실패: {str(e)}")

    async def _generate_anthropic(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str]
    ) -> str:
        """Anthropic Claude로 텍스트 생성"""
        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=settings.anthropic.api_key)

            kwargs = {
                "model": settings.anthropic.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}]
            }

            if system_prompt:
                kwargs["system"] = system_prompt

            response = await client.messages.create(**kwargs)

            result = response.content[0].text
            self.logger.info("anthropic_generation_success", length=len(result))
            return result

        except Exception as e:
            self.logger.error("anthropic_generation_failed", error=str(e))
            raise ExternalServiceError(f"Anthropic 실패: {str(e)}")

    async def _generate_azure(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str]
    ) -> str:
        """Azure OpenAI로 텍스트 생성"""
        try:
            from openai import AsyncAzureOpenAI

            client = AsyncAzureOpenAI(
                api_key=settings.azure_openai.api_key,
                api_version=settings.azure_openai.api_version,
                azure_endpoint=settings.azure_openai.endpoint
            )

            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            response = await client.chat.completions.create(
                model=settings.azure_openai.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            result = response.choices[0].message.content
            self.logger.info("azure_generation_success", length=len(result))
            return result

        except Exception as e:
            self.logger.error("azure_generation_failed", error=str(e))
            raise ExternalServiceError(f"Azure OpenAI 실패: {str(e)}")

    async def _generate_gemini(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str]
    ) -> str:
        """Gemini로 텍스트 생성"""
        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.gemini.api_key)

            model = genai.GenerativeModel(settings.gemini.model)

            # System prompt와 user prompt 결합
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            response = model.generate_content(
                full_prompt,
                generation_config={
                    'temperature': temperature,
                    'max_output_tokens': max_tokens
                }
            )

            result = response.text
            self.logger.info("gemini_generation_success", length=len(result))
            return result

        except Exception as e:
            self.logger.error("gemini_generation_failed", error=str(e))
            raise ExternalServiceError(f"Gemini 실패: {str(e)}")
