"""
TTS (Text-to-Speech) Service
Gemini TTS API를 사용한 음성 변환 기능
"""
import os
import base64
import requests
import wave
import numpy as np
from datetime import datetime
from typing import Optional
from pathlib import Path

from app.config import settings
from app.utils import LoggerMixin, ExternalServiceError


class TTSService(LoggerMixin):
    """텍스트 음성 변환 서비스"""

    def __init__(self):
        """Initialize TTS service"""
        # 저장 경로 설정
        self.save_dir = Path("res/tts")
        self.save_dir.mkdir(parents=True, exist_ok=True)

        self.api_url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash-preview-tts:streamGenerateContent"
        )

        self.logger.info("tts_service_initialized", save_dir=str(self.save_dir))

    def get_tts_config(self, voice_name: str = "charon", language_code: str = "ko-KR") -> dict:
        """
        TTS 설정 반환

        Args:
            voice_name: 음성 이름
            language_code: 언어 코드

        Returns:
            dict: TTS 설정
        """
        return {
            "responseModalities": ["audio"],
            "temperature": 1,
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": voice_name
                    }
                }
            }
        }

    async def generate_tts(
        self,
        text: str,
        voice_name: str = "charon",
        language_code: str = "ko-KR"
    ) -> str:
        """
        텍스트를 음성으로 변환하고 WAV 파일로 저장

        Args:
            text: 변환할 텍스트
            voice_name: 음성 이름 (기본: charon)
            language_code: 언어 코드 (기본: ko-KR)

        Returns:
            str: 저장된 파일 경로

        Raises:
            ExternalServiceError: TTS 생성 실패 시
        """
        try:
            self.logger.info(
                "tts_request",
                text_preview=text[:30],
                voice=voice_name,
                lang=language_code
            )

            if not settings.gemini.is_configured:
                raise ExternalServiceError("Gemini API 키가 설정되어 있지 않습니다.")

            url = f"{self.api_url}?key={settings.gemini.api_key}"
            headers = {"Content-Type": "application/json"}

            body = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": text}]
                    }
                ],
                "generationConfig": self.get_tts_config(voice_name, language_code)
            }

            response = requests.post(url, json=body, headers=headers, timeout=60)
            self.logger.info("tts_api_response", status_code=response.status_code)

            if response.status_code != 200:
                raise ExternalServiceError(
                    f"TTS API 오류: {response.status_code} {response.text[:200]}"
                )

            data = response.json()

            # 리스트 응답 대응
            if isinstance(data, list):
                data = data[0]

            # 응답 파싱
            try:
                parts = data["candidates"][0]["content"]["parts"]
                inline_data = parts[0]["inlineData"]
                base64_audio = inline_data["data"]
                mime_type = inline_data.get("mimeType", "audio/wav; rate=24000")

                self.logger.info("tts_response_parsed", mime_type=mime_type)

            except Exception as e:
                raise ExternalServiceError(f"TTS 응답 파싱 오류: {str(e)}")

            # WAV 파일로 변환
            wav_bytes = self._pcm_base64_to_wav(base64_audio, mime_type)

            # 파일 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"tts_{timestamp}.wav"
            filepath = self.save_dir / filename

            with open(filepath, "wb") as f:
                f.write(wav_bytes)

            self.logger.info("tts_file_saved", filepath=str(filepath))
            return str(filepath)

        except Exception as e:
            self.logger.error("tts_generation_failed", error=str(e))
            raise ExternalServiceError(f"TTS 생성 중 오류가 발생했습니다: {str(e)}")

    def _pcm_base64_to_wav(self, base64_audio: str, mime_type: str) -> bytes:
        """
        Gemini TTS의 base64 PCM 데이터를 WAV로 변환

        Args:
            base64_audio: Base64로 인코딩된 PCM 데이터
            mime_type: MIME 타입 (샘플레이트 정보 포함)

        Returns:
            bytes: WAV 파일 바이트
        """
        import re
        import io

        # 샘플레이트 추출
        rate = 24000
        m = re.search(r"rate=(\d+)", mime_type)
        if m:
            rate = int(m.group(1))

        # Base64 디코딩
        pcm_data = base64.b64decode(base64_audio)

        # numpy로 int16 변환
        audio_np = np.frombuffer(pcm_data, dtype=np.int16)

        # WAV로 변환 (메모리)
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(rate)
            wf.writeframes(audio_np.tobytes())

        self.logger.info("wav_converted", samples=len(audio_np), sample_rate=rate)
        return buf.getvalue()

    def parse_tts_options(self, text: str) -> tuple:
        """
        TTS 옵션 파싱 (--voice=남성 --lang=en)

        Args:
            text: 옵션이 포함된 텍스트

        Returns:
            tuple: (clean_text, voice_name, language_code)
        """
        import re

        voice_name = "charon"  # Gemini TTS 기본 목소리
        language_code = "ko-KR"

        m_voice = re.search(r"--voice=(\S+)", text)
        m_lang = re.search(r"--lang=(\S+)", text)

        if m_voice:
            voice_name = m_voice.group(1)
        if m_lang:
            language_code = m_lang.group(1)

        # 옵션 제거한 텍스트 반환
        clean_text = re.sub(r"--voice=\S+", "", text)
        clean_text = re.sub(r"--lang=\S+", "", clean_text)

        return clean_text.strip(), voice_name, language_code

    def cleanup_old_files(self, max_age_seconds: int = 3600):
        """
        오래된 TTS 파일 정리

        Args:
            max_age_seconds: 파일 최대 보관 시간 (초)
        """
        try:
            import time

            now = time.time()
            deleted_count = 0

            for filepath in self.save_dir.glob("tts_*.wav"):
                if now - filepath.stat().st_mtime > max_age_seconds:
                    filepath.unlink()
                    deleted_count += 1

            if deleted_count > 0:
                self.logger.info("tts_files_cleaned", count=deleted_count)

        except Exception as e:
            self.logger.error("tts_cleanup_failed", error=str(e))
