"""
YouTube Service
유튜브 영상 및 웹페이지 요약 서비스
"""
import re
import json
from typing import Optional, List, Dict
import httpx
from yt_dlp import YoutubeDL

from app.services import AIService
from app.utils import LoggerMixin, ExternalServiceError


class YouTubeService(LoggerMixin):
    """
    유튜브 및 웹페이지 요약 서비스

    유튜브 영상의 자막을 추출하고
    AI를 사용하여 요약합니다.
    """

    def __init__(self, ai_service: AIService):
        """
        Initialize YouTube Service

        Args:
            ai_service: AI service instance
        """
        self.ai_service = ai_service

    async def summarize_video(self, url: str) -> str:
        """
        유튜브 영상 요약

        Args:
            url: 유튜브 URL

        Returns:
            str: 요약 결과
        """
        try:
            self.logger.info("youtube_summarize_started", url=url)

            # 영상 정보 추출
            video_info = await self._get_video_info(url)

            # 자막 추출
            transcript = await self._get_transcript(url)

            if not transcript:
                # 자막이 없으면 영상 정보만 반환
                return (
                    f"제목: {video_info['title']}\n"
                    f"채널: {video_info['channel']}\n"
                    f"길이: {video_info['duration']}\n\n"
                    f"⚠️ 자막을 사용할 수 없어 요약할 수 없습니다."
                )

            # AI로 요약
            summary_prompt = f"""
다음은 유튜브 영상의 자막입니다. 이를 읽고 핵심 내용을 3-5개의 bullet point로 요약해주세요.

영상 제목: {video_info['title']}
채널: {video_info['channel']}

자막:
{transcript[:3000]}  # 처음 3000자만 사용

요약 형식:
• 첫 번째 핵심 내용
• 두 번째 핵심 내용
• ...
"""

            summary = await self.ai_service.generate_text(summary_prompt)

            result = (
                f"📺 {video_info['title']}\n"
                f"👤 {video_info['channel']}\n"
                f"⏱️ {video_info['duration']}\n\n"
                f"📝 요약:\n{summary}"
            )

            self.logger.info("youtube_summarize_completed", url=url)
            return result

        except Exception as e:
            self.logger.error("youtube_summarize_failed", url=url, error=str(e))
            raise ExternalServiceError(f"유튜브 요약 실패: {str(e)}")

    async def summarize_webpage(self, url: str) -> str:
        """
        웹페이지 요약

        Args:
            url: 웹페이지 URL

        Returns:
            str: 요약 결과
        """
        try:
            self.logger.info("webpage_summarize_started", url=url)

            # 웹페이지 내용 가져오기
            content = await self._fetch_webpage_content(url)

            if not content:
                return "⚠️ 웹페이지 내용을 가져올 수 없습니다."

            # AI로 요약
            summary_prompt = f"""
다음은 웹페이지의 내용입니다. 이를 읽고 핵심 내용을 3-5개의 bullet point로 요약해주세요.

URL: {url}

내용:
{content[:3000]}  # 처음 3000자만 사용

요약 형식:
• 첫 번째 핵심 내용
• 두 번째 핵심 내용
• ...
"""

            summary = await self.ai_service.generate_text(summary_prompt)

            result = (
                f"🌐 {url}\n\n"
                f"📝 요약:\n{summary}"
            )

            self.logger.info("webpage_summarize_completed", url=url)
            return result

        except Exception as e:
            self.logger.error("webpage_summarize_failed", url=url, error=str(e))
            raise ExternalServiceError(f"웹페이지 요약 실패: {str(e)}")

    async def _get_video_info(self, url: str) -> dict:
        """
        유튜브 영상 정보 추출

        Args:
            url: 유튜브 URL

        Returns:
            dict: 영상 정보
        """
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True
            }

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                return {
                    'title': info.get('title', 'Unknown'),
                    'channel': info.get('uploader', 'Unknown'),
                    'duration': self._format_duration(info.get('duration', 0)),
                    'description': info.get('description', '')
                }

        except Exception as e:
            self.logger.error("video_info_extraction_failed", error=str(e))
            return {
                'title': 'Unknown',
                'channel': 'Unknown',
                'duration': 'Unknown',
                'description': ''
            }

    async def _get_transcript(self, url: str) -> Optional[str]:
        """
        유튜브 자막 추출

        Args:
            url: 유튜브 URL

        Returns:
            Optional[str]: 자막 텍스트
        """
        try:
            ydl_opts = {
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['ko', 'en'],
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 30,
                'fragment_retries': 1,
                'retries': 1,
            }

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # 자막 정보 확인
                if 'subtitles' not in info and 'automatic_captions' not in info:
                    self.logger.warning("no_subtitles_available", url=url)
                    return None

                self.logger.info("subtitle_info_found")

                # 수동 자막 우선 시도
                if 'subtitles' in info:
                    # 한국어 자막 우선
                    if 'ko' in info['subtitles']:
                        subtitle_url = info['subtitles']['ko'][0]['url']
                        self.logger.info("korean_manual_subtitle_found")
                        return await self._download_and_parse_subtitle(subtitle_url)
                    # 영어 자막 시도
                    elif 'en' in info['subtitles']:
                        subtitle_url = info['subtitles']['en'][0]['url']
                        self.logger.info("english_manual_subtitle_found")
                        return await self._download_and_parse_subtitle(subtitle_url)

                # 자동 생성 자막 시도
                if 'automatic_captions' in info:
                    # 한국어 자동 자막 우선
                    if 'ko' in info['automatic_captions']:
                        subtitle_url = info['automatic_captions']['ko'][0]['url']
                        self.logger.info("korean_auto_subtitle_found")
                        return await self._download_and_parse_subtitle(subtitle_url)
                    # 영어 자동 자막 시도
                    elif 'en' in info['automatic_captions']:
                        subtitle_url = info['automatic_captions']['en'][0]['url']
                        self.logger.info("english_auto_subtitle_found")
                        return await self._download_and_parse_subtitle(subtitle_url)

                self.logger.warning("no_usable_subtitles", url=url)
                return None

        except Exception as e:
            self.logger.error("transcript_extraction_failed", error=str(e))
            return None

    async def _download_and_parse_subtitle(self, subtitle_url: str) -> Optional[str]:
        """
        자막 URL에서 자막을 다운로드하고 파싱

        Args:
            subtitle_url: 자막 다운로드 URL

        Returns:
            Optional[str]: 파싱된 자막 텍스트
        """
        try:
            self.logger.info("subtitle_download_started", url=subtitle_url)

            # 자막 다운로드
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(subtitle_url)
                response.raise_for_status()

                vtt_content = response.text

                # VTT/JSON 파싱
                transcript_list = self._parse_subtitle(vtt_content)

                if not transcript_list:
                    return None

                # 텍스트로 변환
                transcript_text = ' '.join([item['text'] for item in transcript_list])

                self.logger.info("subtitle_parsed", count=len(transcript_list))
                return transcript_text

        except Exception as e:
            self.logger.error("subtitle_download_failed", error=str(e))
            return None

    def _parse_subtitle(self, content: str) -> List[Dict]:
        """
        VTT 또는 JSON 형식의 자막 파싱

        Args:
            content: 자막 내용

        Returns:
            List[Dict]: 파싱된 자막 리스트
        """
        try:
            # JSON 형식인지 확인
            if content.strip().startswith('{'):
                return self._parse_json_subtitle(content)
            else:
                return self._parse_vtt_subtitle(content)

        except Exception as e:
            self.logger.error("subtitle_parse_failed", error=str(e))
            return []

    def _parse_json_subtitle(self, json_content: str) -> List[Dict]:
        """
        JSON 형식의 자막 파싱

        Args:
            json_content: JSON 자막 내용

        Returns:
            List[Dict]: 파싱된 자막 리스트
        """
        try:
            data = json.loads(json_content)
            transcript_list = []

            if 'events' in data:
                for event in data['events']:
                    if 'segs' in event:
                        text_parts = []
                        for seg in event['segs']:
                            if 'utf8' in seg:
                                text_parts.append(seg['utf8'])

                        if text_parts:
                            text = ''.join(text_parts).strip()
                            if text:  # 빈 텍스트가 아닌 경우만 추가
                                transcript_list.append({
                                    'text': text,
                                    'start': event.get('tStartMs', 0) / 1000,
                                    'duration': event.get('dDurationMs', 0) / 1000
                                })

            return transcript_list

        except Exception as e:
            self.logger.error("json_subtitle_parse_failed", error=str(e))
            return []

    def _parse_vtt_subtitle(self, vtt_content: str) -> List[Dict]:
        """
        VTT 형식의 자막 파싱

        Args:
            vtt_content: VTT 자막 내용

        Returns:
            List[Dict]: 파싱된 자막 리스트
        """
        try:
            lines = vtt_content.strip().split('\n')
            transcript_list = []
            current_text = ""
            current_start = 0

            for line in lines:
                line = line.strip()

                # 타임스탬프 라인 건너뛰기
                if '-->' in line or line.startswith('WEBVTT') or line == '':
                    continue

                # 숫자 라인 건너뛰기
                if line.isdigit():
                    continue

                # 텍스트 라인 처리
                if line:
                    if current_text:
                        current_text += " " + line
                    else:
                        current_text = line
                else:
                    # 빈 라인은 텍스트 블록의 끝을 의미
                    if current_text:
                        transcript_list.append({
                            'text': current_text.strip(),
                            'start': current_start,
                            'duration': 0
                        })
                        current_text = ""
                        current_start += 1

            # 마지막 텍스트 블록 처리
            if current_text:
                transcript_list.append({
                    'text': current_text.strip(),
                    'start': current_start,
                    'duration': 0
                })

            return transcript_list

        except Exception as e:
            self.logger.error("vtt_subtitle_parse_failed", error=str(e))
            return []

    async def _fetch_webpage_content(self, url: str) -> Optional[str]:
        """
        웹페이지 내용 가져오기

        Args:
            url: 웹페이지 URL

        Returns:
            Optional[str]: 페이지 내용
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()

                # HTML에서 텍스트 추출 (간단한 방법)
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, 'html.parser')

                # 스크립트와 스타일 제거
                for script in soup(["script", "style"]):
                    script.decompose()

                # 텍스트 추출
                text = soup.get_text()

                # 공백 정리
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)

                return text

        except Exception as e:
            self.logger.error("webpage_fetch_failed", url=url, error=str(e))
            return None

    def _format_duration(self, seconds: int) -> str:
        """
        초 단위를 시간 형식으로 변환

        Args:
            seconds: 초

        Returns:
            str: 포맷된 시간 (예: 1:23:45 또는 5:30)
        """
        if seconds <= 0:
            return "Unknown"

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
