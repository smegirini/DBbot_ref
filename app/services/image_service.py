"""
Image Generation Service
Gemini API를 사용한 이미지 생성 기능
"""
from typing import Optional
from io import BytesIO

from app.config import settings
from app.utils import LoggerMixin, ExternalServiceError


class ImageService(LoggerMixin):
    """AI 이미지 생성 서비스"""

    def __init__(self):
        """Initialize image generation service"""
        self.model = "gemini-2.0-flash-exp-image-generation"
        self.enabled = False  # google-genai import 실패 시 비활성화

        # google-genai 라이브러리 체크
        try:
            from google import genai
            from google.genai import types
            self.genai = genai
            self.types = types
            self.enabled = True

            # Safety settings
            self.safety_settings = [
                types.SafetySetting(
                    category="HARM_CATEGORY_HARASSMENT",
                    threshold="BLOCK_NONE",
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold="BLOCK_NONE",
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    threshold="BLOCK_ONLY_HIGH",
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_NONE",
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_CIVIC_INTEGRITY",
                    threshold="BLOCK_NONE",
                ),
            ]
            self.logger.info("image_service_initialized")
        except ImportError as e:
            self.logger.warning("image_service_disabled", reason="google-genai import failed")

    async def generate_image(self, prompt: str) -> tuple[Optional[BytesIO], Optional[str]]:
        """
        텍스트 프롬프트로 이미지 생성

        Args:
            prompt: 이미지 생성 프롬프트

        Returns:
            tuple: (image_bytes, error_message)
                - image_bytes: 생성된 이미지 (성공 시)
                - error_message: 오류 메시지 (실패 시)
        """
        try:
            if not self.enabled:
                return (None, "이미지 생성 기능이 비활성화되어 있습니다. (google-genai 라이브러리 필요)")

            if not settings.gemini.is_configured:
                raise ExternalServiceError("Gemini API 키가 설정되어 있지 않습니다.")

            self.logger.info("image_generation_request", prompt_preview=prompt[:50])

            client = self.genai.Client(api_key=settings.gemini.api_key)

            contents = [
                self.types.Content(
                    role="user",
                    parts=[self.types.Part.from_text(text=prompt)],
                ),
            ]

            generate_content_config = self.types.GenerateContentConfig(
                response_modalities=["image", "text"],
                safety_settings=self.safety_settings
            )

            response_text = ""

            for chunk in client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=generate_content_config,
            ):
                if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
                    continue

                # 이미지 데이터 확인
                if chunk.candidates[0].content.parts[0].inline_data:
                    image_data = chunk.candidates[0].content.parts[0].inline_data.data
                    self.logger.info("image_generated", size=len(image_data))
                    return (BytesIO(image_data), None)

                # 텍스트 응답 수집
                elif chunk.candidates[0].content.parts[0].text:
                    response_text += chunk.candidates[0].content.parts[0].text

            # 이미지가 생성되지 않았을 경우
            if response_text.strip():
                return (None, response_text.strip())
            else:
                return (None, "Gemini가 이미지 생성을 거부했거나 오류가 발생했습니다.")

        except Exception as e:
            self.logger.error("image_generation_failed", error=str(e))
            return (None, f"이미지 생성 중 오류가 발생했습니다: {str(e)}")

    async def analyze_image(self, image_url: str) -> str:
        """
        이미지를 분석하여 폭력성/선정성 점수 반환

        Args:
            image_url: 분석할 이미지 URL

        Returns:
            str: 분석 결과 (폭력성/선정성 점수)
        """
        try:
            if not self.enabled:
                return "이미지 분석 기능이 비활성화되어 있습니다. (google-genai 라이브러리 필요)"

            if not settings.gemini.is_configured:
                raise ExternalServiceError("Gemini API 키가 설정되어 있지 않습니다.")

            from PIL import Image
            import io
            import requests

            self.logger.info("image_analysis_request", url=image_url)

            # 이미지 다운로드
            response = requests.get(image_url, timeout=30)
            if response.status_code != 200:
                raise ExternalServiceError(f"이미지 다운로드 실패: {response.status_code}")

            image = Image.open(io.BytesIO(response.content))

            client = self.genai.Client(api_key=settings.gemini.api_key)

            system_instruction = (
                "analyze the given image, and rate violence, sexuality score out of 100 "
                "in below format. If the image given is text-only image, scores must be N/A. "
                "If sexuality score is over 50, 성인물 will be True. "
                "Do not add any other comments or markdown\n"
                "폭력성 : score/100\n"
                "선정성 : score/100\n"
                "성인물 : True/False"
            )

            res = client.models.generate_content(
                model=self.model,
                config=self.types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=[self.types.Tool(
                        google_search=self.types.GoogleSearchRetrieval(
                            dynamic_retrieval_config=self.types.DynamicRetrievalConfig(
                                dynamic_threshold=0.6
                            )
                        )
                    )],
                ),
                contents=[image]
            )

            try:
                result = res.text.strip()
                self.logger.info("image_analyzed", result_length=len(result))
                return result
            except:
                return "Gemini 서버에서 오류가 발생했거나 분당 한도가 초과하였습니다. 잠시 후 다시 시도해주세요."

        except Exception as e:
            self.logger.error("image_analysis_failed", error=str(e))
            raise ExternalServiceError(f"이미지 분석 중 오류가 발생했습니다: {str(e)}")
