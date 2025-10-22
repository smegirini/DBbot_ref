"""
RAG (Retrieval-Augmented Generation) Service
웹 검색 + 컨텍스트 주입으로 정확한 AI 응답 생성
"""
import requests
import time
import hashlib
import os
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote_plus, urlparse, parse_qs
from bs4 import BeautifulSoup
import random

from app.config import settings
from app.utils import LoggerMixin, ExternalServiceError

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

try:
    from diskcache import Cache
    DISKCACHE_AVAILABLE = True
except ImportError:
    DISKCACHE_AVAILABLE = False


class RAGService(LoggerMixin):
    """RAG (Retrieval-Augmented Generation) 서비스"""

    def __init__(self):
        """Initialize RAG service"""
        # 캐시 설정
        self._cache: Dict[str, Tuple[float, object]] = {}
        self._cache_ttl = 300.0  # 5분

        # L2 디스크 캐시
        if DISKCACHE_AVAILABLE:
            cache_dir = os.path.expanduser("~/.cache/kakaobot_rag")
            os.makedirs(cache_dir, exist_ok=True)
            self._l2_cache = Cache(cache_dir)
        else:
            self._l2_cache = None

        # User-Agent 풀
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]

        self.logger.info("rag_service_initialized", trafilatura=TRAFILATURA_AVAILABLE, diskcache=DISKCACHE_AVAILABLE)

    def _get_random_headers(self) -> Dict[str, str]:
        """랜덤 User-Agent 헤더 생성"""
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
            "DNT": "1",
        }

    def _cache_key(self, prefix: str, payload: str) -> str:
        """캐시 키 생성"""
        h = hashlib.md5(payload.encode("utf-8", errors="ignore")).hexdigest()
        return f"{prefix}:{h}"

    def _cache_get(self, key: str) -> Optional[object]:
        """캐시에서 값 가져오기 (L1 → L2)"""
        # L1 메모리 캐시
        entry = self._cache.get(key)
        if entry:
            ts, val = entry
            if (time.time() - ts) <= self._cache_ttl:
                return val
            else:
                del self._cache[key]

        # L2 디스크 캐시
        if self._l2_cache:
            try:
                val = self._l2_cache.get(key, default=None)
                if val is not None:
                    self._cache[key] = (time.time(), val)
                    return val
            except Exception:
                pass

        return None

    def _cache_set(self, key: str, val: object):
        """캐시에 값 저장 (L1 + L2)"""
        self._cache[key] = (time.time(), val)

        if self._l2_cache:
            try:
                self._l2_cache.set(key, val, expire=86400)  # 24시간
            except Exception:
                pass

    async def search_web(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        웹 검색 (DuckDuckGo)

        Args:
            query: 검색 쿼리
            max_results: 최대 결과 수

        Returns:
            List[{"title": str, "url": str, "snippet": str}]
        """
        try:
            cache_key = self._cache_key("search", query)
            cached = self._cache_get(cache_key)
            if cached:
                self.logger.info("search_cache_hit", query=query)
                return cached

            self.logger.info("web_search_request", query=query)

            # DuckDuckGo HTML 검색
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            headers = self._get_random_headers()

            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []

            for result in soup.select('.result')[:max_results]:
                try:
                    title_elem = result.select_one('.result__title')
                    url_elem = result.select_one('.result__url')
                    snippet_elem = result.select_one('.result__snippet')

                    if title_elem and url_elem:
                        # DuckDuckGo 리다이렉트 URL 디코딩
                        href = result.select_one('.result__a')['href']
                        actual_url = self._decode_ddg_link(href)

                        results.append({
                            "title": title_elem.get_text(strip=True),
                            "url": actual_url,
                            "snippet": snippet_elem.get_text(strip=True) if snippet_elem else ""
                        })

                except Exception as e:
                    self.logger.debug("search_result_parse_error", error=str(e))
                    continue

            self._cache_set(cache_key, results)
            self.logger.info("web_search_success", count=len(results))

            return results

        except Exception as e:
            self.logger.error("web_search_failed", error=str(e))
            return []

    def _decode_ddg_link(self, href: str) -> str:
        """DuckDuckGo 리다이렉트 URL 디코딩"""
        try:
            parsed = urlparse(href)
            if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
                qs = parse_qs(parsed.query)
                return qs.get("uddg", [href])[0]
            return href
        except Exception:
            return href

    async def fetch_page_content(self, url: str, max_chars: int = 5000) -> str:
        """
        웹 페이지 콘텐츠 가져오기

        Args:
            url: 페이지 URL
            max_chars: 최대 문자 수

        Returns:
            페이지 텍스트 콘텐츠
        """
        try:
            cache_key = self._cache_key("page", url)
            cached = self._cache_get(cache_key)
            if cached:
                return cached

            self.logger.info("fetch_page_request", url=url[:50])

            headers = self._get_random_headers()
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            # Trafilatura로 메인 콘텐츠 추출 (사용 가능한 경우)
            if TRAFILATURA_AVAILABLE:
                content = trafilatura.extract(
                    response.text,
                    include_comments=False,
                    include_tables=True
                )
                if content and len(content) > 200:
                    content = content[:max_chars]
                    self._cache_set(cache_key, content)
                    self.logger.info("fetch_page_success_trafilatura", length=len(content))
                    return content

            # BeautifulSoup 폴백
            soup = BeautifulSoup(response.text, 'html.parser')

            # 불필요한 태그 제거
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()

            # 메인 콘텐츠 추출
            main_content = soup.find(['main', 'article', 'div'], class_=lambda x: x and ('content' in x.lower() or 'main' in x.lower()))

            if main_content:
                content = main_content.get_text(separator='\n', strip=True)
            else:
                content = soup.get_text(separator='\n', strip=True)

            # 정리
            content = '\n'.join(line for line in content.split('\n') if line.strip())
            content = content[:max_chars]

            self._cache_set(cache_key, content)
            self.logger.info("fetch_page_success_bs4", length=len(content))

            return content

        except Exception as e:
            self.logger.error("fetch_page_failed", error=str(e))
            return ""

    async def generate_rag_context(self, query: str, max_pages: int = 3) -> str:
        """
        RAG 컨텍스트 생성

        Args:
            query: 사용자 질문
            max_pages: 최대 페이지 수

        Returns:
            검색 결과를 기반으로 한 컨텍스트 문자열
        """
        try:
            self.logger.info("rag_context_generation", query=query)

            # 웹 검색
            search_results = await self.search_web(query, max_results=max_pages)

            if not search_results:
                return ""

            # 페이지 콘텐츠 수집
            context_parts = [f"다음은 '{query}'에 대한 웹 검색 결과입니다:\n"]

            for i, result in enumerate(search_results[:max_pages], 1):
                url = result['url']
                title = result['title']

                # 페이지 콘텐츠 가져오기
                content = await self.fetch_page_content(url, max_chars=1500)

                if content:
                    context_parts.append(f"\n[출처 {i}: {title}]\n{content}\n")

            full_context = "\n".join(context_parts)

            self.logger.info("rag_context_generated", length=len(full_context), sources=len(search_results))

            return full_context

        except Exception as e:
            self.logger.error("rag_context_generation_failed", error=str(e))
            return ""

    async def answer_with_rag(self, question: str, ai_service) -> str:
        """
        RAG 기반 질문 응답

        Args:
            question: 사용자 질문
            ai_service: AI 서비스 인스턴스

        Returns:
            RAG 기반 AI 응답
        """
        try:
            self.logger.info("rag_answer_request", question=question[:50])

            # 컨텍스트 생성
            context = await self.generate_rag_context(question, max_pages=3)

            if not context:
                # 컨텍스트 없으면 일반 AI 응답
                return await ai_service.generate_text(question)

            # RAG 프롬프트 생성
            rag_prompt = f"""{context}

위 정보를 참고하여 다음 질문에 답변해주세요. 답변은 간결하고 정확하게 작성하세요.

질문: {question}

답변:"""

            # AI 응답 생성
            response = await ai_service.generate_text(rag_prompt, temperature=0.3)

            self.logger.info("rag_answer_generated", response_length=len(response))

            return response

        except Exception as e:
            self.logger.error("rag_answer_failed", error=str(e))
            raise ExternalServiceError(f"RAG 응답 생성 실패: {str(e)}")
