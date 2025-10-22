"""
Cryptocurrency Service
업비트 API를 사용한 암호화폐 정보 제공
"""
import requests
import datetime
import pytz
from typing import Optional, Dict, List
from iris import PyKV

from app.utils import LoggerMixin, ExternalServiceError


class CryptoService(LoggerMixin):
    """암호화폐 정보 서비스"""

    def __init__(self):
        """Initialize cryptocurrency service"""
        self.all_url = "https://api.upbit.com/v1/market/all"
        self.base_url = "https://api.upbit.com/v1/ticker?markets="
        self.currency_url = (
            "https://m.search.naver.com/p/csearch/content/qapirender.nhn"
            "?key=calculator&pkid=141&q=%ED%99%98%EC%9C%A8&where=m"
            "&u1=keb&u6=standardUnit&u7=0&u3=USD&u4=KRW&u8=down&u2=1"
        )
        self.binance_url = "https://api.binance.com/api/v3/ticker/"
        self.kv = PyKV()

        self.logger.info("crypto_service_initialized")

    async def get_coin_price(self, symbol: str, user_id: str) -> str:
        """
        특정 코인의 현재 가격 조회

        Args:
            symbol: 코인 심볼 (예: BTC, ETH)
            user_id: 사용자 ID (보유 정보 조회용)

        Returns:
            str: 코인 가격 정보
        """
        try:
            query = symbol.upper()
            response = requests.get(
                self.base_url + 'KRW-' + query,
                timeout=10
            )

            if 'error' in response.text:
                # 한글 이름으로 검색 시도
                try:
                    result_json, query = await self._get_upbit_korean(query)
                except:
                    raise ExternalServiceError("검색된 코인이 없습니다.")
            else:
                result_json = response.json()[0]

            price = result_json['trade_price']
            change = result_json['signed_change_rate'] * 100

            if price % 1 == 0:
                price = int(price)

            result = f"{query}\n현재가 : {price:,}원\n등락률 : {change:,.2f}%"

            # 사용자 보유 코인 정보 확인
            user_coin_info = self.kv.get(f"coin.{user_id}")
            if user_coin_info and query in user_coin_info:
                amount = user_coin_info[query]["amount"]
                average = user_coin_info[query]["average"]
                seed = average * amount
                total = round(result_json['trade_price'] * amount, 0)
                percent = round((total / seed - 1) * 100, 1)
                plus_mark = "+" if percent > 0 else ""

                result += (
                    f'\n총평가금액 : {total:,.0f}원({plus_mark}{percent:,.1f}%)'
                    f'\n총매수금액 : {seed:,.0f}원'
                    f'\n보유수량 : {amount:,.0f}개'
                    f'\n평균단가 : {average:,}원'
                )

            self.logger.info("coin_price_retrieved", symbol=query, price=price)
            return result

        except Exception as e:
            self.logger.error("coin_price_failed", error=str(e))
            raise ExternalServiceError(f"코인 가격 조회 실패: {str(e)}")

    async def get_my_coins(self, user_id: str) -> str:
        """
        사용자가 등록한 코인 목록 조회

        Args:
            user_id: 사용자 ID

        Returns:
            str: 보유 코인 정보
        """
        try:
            my_coins = self.kv.get(f"coin.{user_id}")
            if not my_coins:
                return "등록된 코인이 없습니다. !코인등록 기능으로 코인을 등록하세요."

            my_coins_list = [f"KRW-{key}" for key in my_coins.keys()]
            coins_query = ",".join(my_coins_list)

            response = requests.get(self.base_url + coins_query, timeout=10)
            result_list = []
            coins = {}
            current_total = 0
            bought_total = 0

            for coin in response.json():
                coins[coin['market'][4:]] = {
                    'price': coin['trade_price'],
                    'change': coin['signed_change_rate'] * 100
                }

            for key in coins.keys():
                amount = my_coins[key]["amount"]
                average = my_coins[key]["average"]
                seed = average * amount
                total = round(coins[key]["price"] * amount, 0)
                percent = round((total / seed - 1) * 100, 1)
                plus_mark = "+" if percent > 0 else ""

                to_append = (
                    f'{key}\n현재가 : {coins[key]["price"]} 원\n등락률 : {coins[key]["change"]:.2f} %'
                    f'\n총평가금액 : {total:,.0f}원({plus_mark}{percent:,.1f}%)'
                    f'\n총매수금액 : {seed:,.0f}원'
                    f'\n보유수량 : {amount:,.0f}개'
                    f'\n평균단가 : {average:,}원'
                )
                result_list.append(to_append)
                current_total += total
                bought_total += seed

            result = '\n\n'.join(result_list)
            total_change = round((current_total / bought_total - 1) * 100, 1)
            result = (
                '내 코인\n' + '\u200b' * 500 +
                f'\n전체\n총평가 : {current_total:,.0f}원'
                f'\n총매수 : {bought_total:,.0f}원'
                f'\n평가손익 : {current_total-bought_total:+,.0f}원'
                f'\n수익률 : {total_change:+,.1f}%\n\n' + result
            )

            self.logger.info("my_coins_retrieved", user_id=user_id, count=len(my_coins))
            return result

        except Exception as e:
            self.logger.error("my_coins_failed", error=str(e))
            raise ExternalServiceError(f"내 코인 조회 실패: {str(e)}")

    async def get_kimchi_premium(self) -> str:
        """
        김치 프리미엄 조회

        Returns:
            str: 김치 프리미엄 정보
        """
        try:
            BTCUSDT = float(
                requests.get(self.binance_url + "price?symbol=BTCUSDT", timeout=10)
                .json()["price"]
            )
            BTCKRW = requests.get(
                self.base_url + "KRW-BTC",
                timeout=10
            ).json()[0]["trade_price"]
            USDKRW = await self._get_usd_krw()

            local_time = datetime.datetime.now()
            eastern = pytz.timezone('US/Eastern')
            eastern_time = local_time.astimezone(eastern)
            EST = eastern_time.strftime("%d일 %H시%M분")

            BTCUSDT_to_KRW = BTCUSDT * USDKRW
            BTCKRW_to_USDT = BTCKRW / USDKRW
            kimchi_premium = (BTCKRW - BTCUSDT_to_KRW) / BTCUSDT_to_KRW * 100

            result = (
                f'김치 프리미엄\n'
                f'업빗 : ￦{BTCKRW:,.0f}(${BTCKRW_to_USDT:,.0f})\n'
                f'바낸 : ￦{BTCUSDT_to_KRW:,.0f}(${BTCUSDT:,.0f})\n'
                f'김프 : {kimchi_premium:.2f}%\n'
                f'환율 : ￦{USDKRW:,.0f}\n'
                f'버거시간(동부) : {EST}'
            )

            self.logger.info("kimchi_premium_retrieved", premium=kimchi_premium)
            return result

        except Exception as e:
            self.logger.error("kimchi_premium_failed", error=str(e))
            raise ExternalServiceError(f"김치 프리미엄 조회 실패: {str(e)}")

    async def add_coin(self, user_id: str, symbol: str, amount: float, average: float) -> str:
        """
        코인 등록

        Args:
            user_id: 사용자 ID
            symbol: 코인 심볼
            amount: 보유 수량
            average: 평균 단가

        Returns:
            str: 등록 결과 메시지
        """
        try:
            symbol = symbol.upper()
            response = requests.get(self.base_url + 'KRW-' + symbol, timeout=10)

            if 'error' in response.text:
                raise ExternalServiceError('업비트 원화마켓만 지원합니다.')

            user_kv = self.kv.get(f"coin.{user_id}") or {}
            user_kv[symbol] = {"amount": amount, "average": average}
            self.kv.put(f"coin.{user_id}", user_kv)

            self.logger.info("coin_added", user_id=user_id, symbol=symbol)
            return f'{symbol}코인을 {average}원에 {amount}개 등록하였습니다.'

        except Exception as e:
            self.logger.error("coin_add_failed", error=str(e))
            raise ExternalServiceError(f"코인 등록 실패: {str(e)}")

    async def remove_coin(self, user_id: str, symbol: str) -> str:
        """
        코인 삭제

        Args:
            user_id: 사용자 ID
            symbol: 코인 심볼

        Returns:
            str: 삭제 결과 메시지
        """
        try:
            symbol = symbol.upper()
            user_kv = self.kv.get(f"coin.{user_id}") or {}

            if symbol in user_kv.keys():
                user_kv.pop(symbol)
                self.kv.put(f"coin.{user_id}", user_kv)
                self.logger.info("coin_removed", user_id=user_id, symbol=symbol)
                return f'{symbol}코인을 삭제하였습니다.'
            else:
                raise ExternalServiceError('코인이 없거나 잘못된 명령입니다.')

        except Exception as e:
            self.logger.error("coin_remove_failed", error=str(e))
            raise ExternalServiceError(f"코인 삭제 실패: {str(e)}")

    async def _get_upbit_korean(self, query: str) -> tuple:
        """한글 이름으로 코인 검색"""
        response = requests.get(self.all_url, timeout=10)
        for market in response.json():
            if 'KRW' in market['market'] and query in market['korean_name']:
                eng_query = market['market']
                if query == market['korean_name']:
                    break

        response = requests.get(self.base_url + eng_query, timeout=10)
        return (response.json()[0], eng_query[4:])

    async def _get_usd_krw(self) -> float:
        """USD-KRW 환율 조회"""
        response = requests.get(self.currency_url, timeout=10)
        return float(response.json()["country"][1]["value"].replace(",", ""))
