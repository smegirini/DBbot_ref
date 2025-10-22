"""
Playwright-based Web Crawler Service
JavaScript 렌더링 필요한 동적 페이지 수집 기능
"""
import asyncio
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.utils import LoggerMixin, ExternalServiceError


class PlaywrightCrawlerService(LoggerMixin):
    """Playwright 기반 동적 웹 크롤링 서비스"""

    def __init__(self):
        """Initialize Playwright crawler service"""
        self.headless = True
        self.timeout = 15000  # 15초 (밀리초)
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        # 선택적 의존성 체크
        self.playwright_available = False
        self.bs4_available = False
        self.trafilatura_available = False

        try:
            from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
            self.async_playwright = async_playwright
            self.PlaywrightTimeout = PlaywrightTimeout
            self.playwright_available = True
            self.logger.info("playwright_available")
        except ImportError:
            self.logger.warning("playwright_not_available", note="pip install playwright && playwright install chromium")

        try:
            from bs4 import BeautifulSoup
            import requests
            self.BeautifulSoup = BeautifulSoup
            self.requests = requests
            self.bs4_available = True
            self.logger.info("beautifulsoup_available")
        except ImportError:
            self.logger.warning("beautifulsoup_not_available")

        try:
            import trafilatura
            self.trafilatura = trafilatura
            self.trafilatura_available = True
            self.logger.info("trafilatura_available")
        except ImportError:
            self.logger.warning("trafilatura_not_available")

        self.logger.info("playwright_crawler_service_initialized", enabled=self.playwright_available)

    async def fetch_with_playwright(
        self,
        url: str,
        wait_for_selector: Optional[str] = None
    ) -> str:
        """
        Playwright로 JavaScript 렌더링 페이지 수집

        Args:
            url: 수집할 URL
            wait_for_selector: 로드 대기할 CSS 선택자 (optional)

        Returns:
            str: 페이지 텍스트 콘텐츠

        Raises:
            ExternalServiceError: Playwright 사용 불가 또는 수집 실패
        """
        try:
            if not self.playwright_available:
                raise ExternalServiceError("Playwright가 설치되어 있지 않습니다.")

            self.logger.info("playwright_fetch_request", url=url[:100])

            async with self.async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(user_agent=self.user_agent)
                page = await context.new_page()

                # 페이지 로드
                await page.goto(url, timeout=self.timeout, wait_until='domcontentloaded')

                # 특정 요소 대기 (선택적)
                if wait_for_selector:
                    try:
                        await page.wait_for_selector(wait_for_selector, timeout=self.timeout)
                    except self.PlaywrightTimeout:
                        self.logger.debug("selector_timeout", selector=wait_for_selector)

                # JavaScript 실행 대기
                await asyncio.sleep(2)

                # 텍스트 콘텐츠 추출
                content = await page.evaluate('''() => {
                    // 불필요한 요소 제거
                    const elementsToRemove = document.querySelectorAll(
                        'script, style, nav, header, footer, aside, .advertisement, .ad, .sidebar'
                    );
                    elementsToRemove.forEach(el => el.remove());

                    // 메인 콘텐츠 추출
                    const main = document.querySelector(
                        'main, article, .main-content, .content, .post-content, #content, #main'
                    );
                    if (main) {
                        return main.innerText;
                    }

                    // 폴백: body 전체
                    return document.body.innerText;
                }''')

                await browser.close()

                # 정리
                content = content.strip()

                # 최소 품질 체크
                if len(content) < 200:
                    self.logger.debug("content_too_short", length=len(content))
                    return ""

                self.logger.info("playwright_fetch_success", content_length=len(content))
                return content

        except Exception as e:
            self.logger.error("playwright_fetch_failed", error=str(e))
            return ""

    async def fetch_with_trafilatura(self, url: str) -> str:
        """
        Trafilatura로 정적 HTML 페이지 수집 (빠름)

        Args:
            url: 수집할 URL

        Returns:
            str: 페이지 텍스트 콘텐츠
        """
        try:
            if not self.trafilatura_available or not self.bs4_available:
                return ""

            self.logger.info("trafilatura_fetch_request", url=url[:100])

            headers = {"User-Agent": self.user_agent}
            response = self.requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # trafilatura로 메인 콘텐츠 추출
            content = self.trafilatura.extract(
                response.text,
                include_comments=False,
                include_tables=True
            )

            if content and len(content) > 200:
                self.logger.info("trafilatura_fetch_success", content_length=len(content))
                return content
            else:
                return ""

        except Exception as e:
            self.logger.debug("trafilatura_fetch_failed", error=str(e))
            return ""

    async def fetch_with_beautifulsoup(self, url: str) -> str:
        """
        BeautifulSoup로 페이지 수집 (최후 폴백)

        Args:
            url: 수집할 URL

        Returns:
            str: 페이지 텍스트 콘텐츠
        """
        try:
            if not self.bs4_available:
                return ""

            self.logger.info("beautifulsoup_fetch_request", url=url[:100])

            headers = {"User-Agent": self.user_agent}
            response = self.requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            response.raise_for_status()

            soup = self.BeautifulSoup(response.text, 'html.parser')

            # 불필요한 태그 제거
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()

            # 텍스트 추출
            text = soup.get_text(separator=' ', strip=True)

            if len(text) > 200:
                self.logger.info("beautifulsoup_fetch_success", content_length=len(text))
                return text
            else:
                return ""

        except Exception as e:
            self.logger.debug("beautifulsoup_fetch_failed", error=str(e))
            return ""

    async def fetch_page_multi_strategy(
        self,
        url: str,
        max_chars: int = 3000
    ) -> str:
        """
        다층 크롤링 전략:
        1. Playwright (JavaScript 렌더링)
        2. Trafilatura (정적 HTML, 빠름)
        3. BeautifulSoup (폴백)

        Args:
            url: 수집할 URL
            max_chars: 최대 문자 수

        Returns:
            str: 페이지 콘텐츠
        """
        try:
            self.logger.info("multi_strategy_fetch", url=url[:100])

            # 전략 1: Playwright (JavaScript 페이지)
            if self.playwright_available:
                content = await self.fetch_with_playwright(url)
                if content and len(content) > 200:
                    self.logger.info("multi_strategy_success", strategy="playwright")
                    return content[:max_chars]

            # 전략 2: Trafilatura (정적 HTML)
            if self.trafilatura_available:
                content = await self.fetch_with_trafilatura(url)
                if content and len(content) > 200:
                    self.logger.info("multi_strategy_success", strategy="trafilatura")
                    return content[:max_chars]

            # 전략 3: BeautifulSoup (최후 폴백)
            if self.bs4_available:
                content = await self.fetch_with_beautifulsoup(url)
                if content and len(content) > 200:
                    self.logger.info("multi_strategy_success", strategy="beautifulsoup")
                    return content[:max_chars]

            self.logger.warning("multi_strategy_failed", url=url[:100])
            return ""

        except Exception as e:
            self.logger.error("multi_strategy_error", error=str(e))
            return ""

    async def fetch_pages_parallel(
        self,
        urls: List[str],
        max_workers: int = 5,
        max_chars: int = 3000
    ) -> List[Dict[str, any]]:
        """
        여러 페이지 병렬 수집

        Args:
            urls: 수집할 URL 리스트
            max_workers: 병렬 작업자 수
            max_chars: 페이지당 최대 문자 수

        Returns:
            List[Dict]: 수집된 문서 리스트
        """
        try:
            self.logger.info("parallel_fetch_request", url_count=len(urls))

            docs = []
            failed_count = 0

            def fetch_single(url: str) -> Optional[Dict[str, any]]:
                """개별 페이지 수집 (동기 래퍼)"""
                try:
                    # asyncio.run으로 래핑
                    content = asyncio.run(self.fetch_page_multi_strategy(url, max_chars))

                    if content and len(content) > 200:
                        # 품질 체크: 리다이렉트/에러 페이지 필터링
                        content_lower = content.lower()
                        bad_keywords = [
                            "please click here",
                            "page does not redirect",
                            "javascript is disabled",
                            "enable javascript",
                            "access denied",
                            "403 forbidden",
                            "404 not found",
                        ]

                        if any(kw in content_lower for kw in bad_keywords):
                            return None

                        return {
                            "url": url,
                            "content": content,
                            "content_length": len(content),
                            "crawl_method": "multi_strategy"
                        }

                except Exception as e:
                    self.logger.debug("single_fetch_failed", url=url[:50], error=str(e))

                return None

            # 병렬 처리
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(fetch_single, url): url for url in urls}

                for future in as_completed(futures):
                    try:
                        doc = future.result(timeout=30)
                        if doc:
                            docs.append(doc)
                        else:
                            failed_count += 1
                    except Exception as e:
                        failed_count += 1
                        self.logger.debug("future_failed", error=str(e))

            # 콘텐츠 길이 기준 정렬
            docs.sort(key=lambda x: x.get("content_length", 0), reverse=True)

            self.logger.info(
                "parallel_fetch_complete",
                success=len(docs),
                failed=failed_count
            )

            return docs

        except Exception as e:
            self.logger.error("parallel_fetch_failed", error=str(e))
            return []

    def check_installation(self) -> Dict[str, bool]:
        """
        설치 상태 확인

        Returns:
            Dict: 설치 상태 정보
        """
        return {
            "playwright_available": self.playwright_available,
            "beautifulsoup_available": self.bs4_available,
            "trafilatura_available": self.trafilatura_available,
            "any_available": (
                self.playwright_available or
                self.bs4_available or
                self.trafilatura_available
            )
        }
