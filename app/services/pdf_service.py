"""
PDF Summary Service
PDF 문서 요약 기능
"""
import requests
import json
from io import BytesIO
from typing import Optional
import PyPDF2

from app.config import settings
from app.utils import LoggerMixin, ExternalServiceError


class PDFService(LoggerMixin):
    """PDF 문서 처리 및 요약 서비스"""

    def __init__(self):
        """Initialize PDF service"""
        self.logger.info("pdf_service_initialized")

    async def extract_text_from_pdf(self, pdf_url: str) -> str:
        """
        PDF URL에서 텍스트 내용 추출

        Args:
            pdf_url: PDF 파일 URL

        Returns:
            str: 추출된 텍스트

        Raises:
            ExternalServiceError: PDF 다운로드/처리 실패 시
        """
        try:
            # PDF 파일 다운로드
            response = requests.get(pdf_url, timeout=30)
            if response.status_code != 200:
                raise ExternalServiceError(
                    f"PDF 다운로드 실패: {response.status_code}"
                )

            # PDF 파일 읽기
            pdf_file = BytesIO(response.content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            # 텍스트 추출
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                extracted_text = page.extract_text()

                if extracted_text is not None:
                    text += extracted_text + "\n\n"
                else:
                    text += f"[페이지 {page_num+1}의 텍스트를 추출할 수 없습니다.]\n\n"

            if not text.strip():
                raise ExternalServiceError(
                    "PDF에서 텍스트를 추출할 수 없습니다. "
                    "이미지 기반 PDF이거나 텍스트 레이어가 없는 PDF일 수 있습니다."
                )

            self.logger.info(
                "pdf_text_extracted",
                text_length=len(text),
                pages=len(pdf_reader.pages)
            )
            return text

        except Exception as e:
            self.logger.error("pdf_extraction_failed", error=str(e))
            raise ExternalServiceError(f"PDF 처리 중 오류가 발생했습니다: {str(e)}")

    async def summarize_pdf(
        self,
        pdf_content: str,
        prompt: str = "이 PDF 문서의 내용을 핵심만 간략하게 요약해주세요."
    ) -> str:
        """
        PDF 내용을 Azure OpenAI로 요약

        Args:
            pdf_content: PDF 텍스트 내용
            prompt: 요약 프롬프트

        Returns:
            str: 요약 결과
        """
        try:
            # 텍스트가 너무 길면 잘라내기
            max_chars = 500000
            if len(pdf_content) > max_chars:
                pdf_content = pdf_content[:max_chars] + "\n... (내용이 너무 길어 일부만 분석합니다)"

            # Azure OpenAI API 호출
            headers = {
                "Content-Type": "application/json",
                "api-key": settings.azure_openai.api_key
            }

            data = {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "당신은 PDF 문서를 요약하는 도우미입니다. "
                            "주어진 텍스트를 분석하고 핵심 내용을 간결하게 정리해주세요. "
                            "중요한 규칙: 답변 작성시에는 마크다운 문법(#, *, **, -, `, [](), 등)을 "
                            "절대 사용하지 마세요. 일반 텍스트로만 답변하세요. "
                            "제목은 숫자나 구분자로 표시하고, 강조는 따옴표나 대괄호를 사용하세요."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"{prompt}\n\n"
                            f"참고: 답변은 마크다운 문법 없이 일반 텍스트로만 작성해주세요.\n\n"
                            f"{pdf_content}"
                        )
                    }
                ],
                "max_completion_tokens": 1200,
                "temperature": 0.3,
                "top_p": 1,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "model": settings.azure_openai.model
            }

            endpoint = (
                f"{settings.azure_openai.endpoint}/openai/deployments/"
                f"{settings.azure_openai.model}/chat/completions"
                f"?api-version={settings.azure_openai.api_version}"
            )

            response = requests.post(
                endpoint,
                headers=headers,
                json=data,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()["choices"][0]["message"]["content"]
                self.logger.info("pdf_summarized", summary_length=len(result))
                return result
            else:
                raise ExternalServiceError(
                    f"Azure OpenAI API 오류: {response.status_code}, {response.text}"
                )

        except Exception as e:
            self.logger.error("pdf_summary_failed", error=str(e))
            raise ExternalServiceError(f"요약 과정에서 오류가 발생했습니다: {str(e)}")

    def load_attachment(self, message) -> Optional[dict]:
        """
        메시지의 첨부 파일 데이터를 가져오는 도우미 함수

        Args:
            message: 메시지 객체

        Returns:
            Optional[dict]: 첨부 파일 데이터 또는 None
        """
        try:
            if hasattr(message, "attachment") and message.attachment:
                try:
                    # JSON 문자열이면 파싱 시도
                    if isinstance(message.attachment, str):
                        return json.loads(message.attachment)
                    return message.attachment
                except Exception:
                    return message.attachment
            return None
        except Exception as e:
            self.logger.error("attachment_load_failed", error=str(e))
            return None
