#!/usr/bin/env python3
"""
KakaoBot 실행 스크립트
Iris WebSocket을 통한 카카오톡 봇 실행
"""
import sys
import asyncio
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.bot import KakaoBotHandler
from app.utils import setup_logging


def main():
    """메인 실행 함수"""
    # 기본 Iris URL
    DEFAULT_IRIS_URL = "10.82.62.72:3000"

    # Iris URL 결정 (인자로 받거나 기본값 사용)
    if len(sys.argv) < 2:
        print("=" * 50)
        print("KakaoBot - Iris 기반 카카오톡 봇")
        print("=" * 50)
        print()
        print(f"⚠️  Iris URL이 제공되지 않아 기본값을 사용합니다: {DEFAULT_IRIS_URL}")
        print()
        print("사용법:")
        print("  python run_bot.py                    # 기본값 사용")
        print("  python run_bot.py <IRIS_URL>         # 사용자 지정")
        print()
        print("예제:")
        print(f"  python run_bot.py {DEFAULT_IRIS_URL}")
        print("  python run_bot.py 192.168.1.100:3000")
        print()
        print("=" * 50)
        iris_url = DEFAULT_IRIS_URL
    else:
        iris_url = sys.argv[1]

    # 로깅 설정
    setup_logging()

    print("=" * 50)
    print("KakaoBot 시작 중...")
    print(f"Iris 서버: {iris_url}")
    print("=" * 50)

    try:
        # 봇 핸들러 생성 (백그라운드 이벤트 루프 자동 시작)
        handler = KakaoBotHandler(iris_url)

        # 백그라운드 루프에서 비동기 서비스 초기화
        print("서비스 초기화 중...")
        future = asyncio.run_coroutine_threadsafe(
            handler.initialize_services(),
            handler._loop
        )
        future.result()  # 초기화 완료 대기
        print("✅ 서비스 초기화 완료")

        # 봇 실행 (블로킹)
        print("✅ 봇 실행 중... (Ctrl+C로 종료)")
        print("=" * 50)
        handler.run()

    except KeyboardInterrupt:
        print("\n" + "=" * 50)
        print("사용자에 의해 종료되었습니다.")
        print("=" * 50)
    except Exception as e:
        print("\n" + "=" * 50)
        print(f"❌ 오류 발생: {str(e)}")
        print("=" * 50)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
