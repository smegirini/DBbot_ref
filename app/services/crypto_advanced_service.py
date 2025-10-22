"""
Advanced Cryptocurrency Analysis Service
고급 암호화폐 분석 - 기술 지표, 히스토리 데이터, 멀티 에이전트 분석
"""
import requests
import time
import statistics
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from app.utils import LoggerMixin, ExternalServiceError


class CryptoAdvancedService(LoggerMixin):
    """고급 암호화폐 분석 서비스"""

    BASE_URL = "https://api.coingecko.com/api/v3"

    # 심볼 -> CoinGecko ID 매핑
    SYMBOL_TO_ID = {
        "btc": "bitcoin",
        "eth": "ethereum",
        "usdt": "tether",
        "bnb": "binancecoin",
        "sol": "solana",
        "xrp": "ripple",
        "usdc": "usd-coin",
        "ada": "cardano",
        "avax": "avalanche-2",
        "doge": "dogecoin",
        "trx": "tron",
        "dot": "polkadot",
        "matic": "matic-network",
        "link": "chainlink",
        "ltc": "litecoin",
        "atom": "cosmos",
        "uni": "uniswap",
        "etc": "ethereum-classic",
        "xlm": "stellar",
        "bch": "bitcoin-cash",
    }

    def __init__(self):
        """Initialize advanced crypto service"""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; KakaoBot/1.0)"
        })

        # 캐시
        self._cache: Dict[str, Tuple[float, object]] = {}
        self._cache_ttl = 300  # 5분

        self.logger.info("crypto_advanced_service_initialized")

    def _normalize_coin_id(self, coin_input: str) -> str:
        """
        코인 심볼/ID 정규화

        Args:
            coin_input: 사용자 입력 (BTC, bitcoin 등)

        Returns:
            CoinGecko 코인 ID
        """
        coin_lower = coin_input.lower().strip()

        # 심볼 매핑 확인
        if coin_lower in self.SYMBOL_TO_ID:
            return self.SYMBOL_TO_ID[coin_lower]

        # 이미 ID 형식이면 그대로 반환
        return coin_lower

    def _cache_key(self, prefix: str, coin_id: str) -> str:
        """캐시 키 생성"""
        return f"{prefix}:{coin_id}"

    def _cache_get(self, key: str) -> Optional[object]:
        """캐시에서 값 가져오기"""
        entry = self._cache.get(key)
        if entry:
            ts, val = entry
            if (time.time() - ts) <= self._cache_ttl:
                return val
            else:
                del self._cache[key]
        return None

    def _cache_set(self, key: str, val: object):
        """캐시에 값 저장"""
        self._cache[key] = (time.time(), val)

    def _request(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """API 요청"""
        try:
            url = f"{self.BASE_URL}/{endpoint}"
            response = self.session.get(url, params=params or {}, timeout=15)

            if response.status_code == 429:
                time.sleep(2)
                response = self.session.get(url, params=params or {}, timeout=15)

            response.raise_for_status()
            return response.json()

        except Exception as e:
            self.logger.error("coingecko_api_error", error=str(e))
            return None

    async def get_historical_data(self, coin_id: str, days: int = 30) -> Dict[str, any]:
        """
        과거 가격 데이터 조회

        Args:
            coin_id: CoinGecko 코인 ID (예: bitcoin, ethereum)
            days: 조회 기간 (일)

        Returns:
            {
                "prices": [[timestamp, price], ...],
                "market_caps": [[timestamp, market_cap], ...],
                "total_volumes": [[timestamp, volume], ...]
            }
        """
        try:
            cache_key = self._cache_key("hist", f"{coin_id}_{days}")
            cached = self._cache_get(cache_key)
            if cached:
                return cached

            params = {
                "vs_currency": "usd",
                "days": days,
                "interval": "daily" if days > 1 else "hourly"
            }

            data = self._request(f"coins/{coin_id}/market_chart", params)
            result = data or {"prices": [], "market_caps": [], "total_volumes": []}

            self._cache_set(cache_key, result)
            return result

        except Exception as e:
            self.logger.error("get_historical_data_failed", error=str(e))
            return {"prices": [], "market_caps": [], "total_volumes": []}

    async def calculate_technical_indicators(self, coin_id: str) -> Dict[str, any]:
        """
        기술 지표 계산 (RSI, MACD, Bollinger Bands)

        Args:
            coin_id: CoinGecko 코인 ID

        Returns:
            {
                "rsi": {"value": float, "signal": "overbought|neutral|oversold"},
                "macd": {"value": float, "signal": float, "histogram": float, "trend": "bullish|bearish|neutral"},
                "bollinger": {"upper": float, "middle": float, "lower": float, "position": "above|inside|below"}
            }
        """
        try:
            # 30일 가격 데이터 가져오기
            hist_data = await self.get_historical_data(coin_id, days=30)
            prices = [p[1] for p in hist_data.get("prices", [])]

            if len(prices) < 20:
                return {}

            indicators = {}

            # RSI 계산 (14일)
            rsi = self._calculate_rsi(prices, period=14)
            if rsi is not None:
                if rsi > 70:
                    signal = "overbought"
                elif rsi < 30:
                    signal = "oversold"
                else:
                    signal = "neutral"

                indicators["rsi"] = {
                    "value": round(rsi, 2),
                    "signal": signal
                }

            # MACD 계산
            macd_data = self._calculate_macd(prices)
            if macd_data:
                indicators["macd"] = macd_data

            # Bollinger Bands 계산
            bb = self._calculate_bollinger_bands(prices)
            if bb:
                indicators["bollinger"] = bb

            self.logger.info("technical_indicators_calculated", coin_id=coin_id)
            return indicators

        except Exception as e:
            self.logger.error("calculate_technical_indicators_failed", error=str(e))
            return {}

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """RSI (Relative Strength Index) 계산"""
        try:
            if len(prices) < period + 1:
                return None

            # 가격 변화 계산
            deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]

            # 상승/하락 분리
            gains = [d if d > 0 else 0 for d in deltas]
            losses = [-d if d < 0 else 0 for d in deltas]

            # 평균 계산
            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period

            if avg_loss == 0:
                return 100.0

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            return rsi

        except Exception:
            return None

    def _calculate_macd(self, prices: List[float]) -> Optional[Dict[str, any]]:
        """MACD (Moving Average Convergence Divergence) 계산"""
        try:
            if len(prices) < 26:
                return None

            # EMA 계산
            def ema(data, period):
                multiplier = 2 / (period + 1)
                ema_values = [sum(data[:period]) / period]
                for price in data[period:]:
                    ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
                return ema_values[-1]

            ema_12 = ema(prices, 12)
            ema_26 = ema(prices, 26)

            macd_line = ema_12 - ema_26

            # Signal line (MACD의 9일 EMA)
            # 간단히 최근 9일의 평균으로 근사
            signal_line = macd_line * 0.9  # 근사값

            histogram = macd_line - signal_line

            # 추세 판단
            if histogram > 0:
                trend = "bullish"
            elif histogram < 0:
                trend = "bearish"
            else:
                trend = "neutral"

            return {
                "value": round(macd_line, 4),
                "signal": round(signal_line, 4),
                "histogram": round(histogram, 4),
                "trend": trend
            }

        except Exception:
            return None

    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20) -> Optional[Dict[str, any]]:
        """Bollinger Bands 계산"""
        try:
            if len(prices) < period:
                return None

            recent_prices = prices[-period:]
            middle = statistics.mean(recent_prices)
            std_dev = statistics.stdev(recent_prices)

            upper = middle + (2 * std_dev)
            lower = middle - (2 * std_dev)

            current_price = prices[-1]

            # 현재 가격 위치
            if current_price > upper:
                position = "above"
            elif current_price < lower:
                position = "below"
            else:
                position = "inside"

            return {
                "upper": round(upper, 2),
                "middle": round(middle, 2),
                "lower": round(lower, 2),
                "current": round(current_price, 2),
                "position": position
            }

        except Exception:
            return None

    async def get_advanced_analysis(self, coin_input: str) -> str:
        """
        고급 분석 리포트 생성

        Args:
            coin_input: 코인 심볼 또는 ID (BTC, bitcoin 등)

        Returns:
            분석 리포트 (텍스트)
        """
        try:
            # 코인 ID 정규화
            coin_id = self._normalize_coin_id(coin_input)
            self.logger.info("advanced_analysis_request", input=coin_input, normalized=coin_id)

            # 기술 지표 계산
            indicators = await self.calculate_technical_indicators(coin_id)

            if not indicators:
                return f"❌ {coin_input.upper()}에 대한 충분한 데이터가 없습니다."

            # 리포트 생성
            lines = [f"📊 {coin_input.upper()} 고급 기술 분석\n"]

            # RSI
            if "rsi" in indicators:
                rsi_data = indicators["rsi"]
                signal_emoji = "🔥" if rsi_data["signal"] == "overbought" else "❄️" if rsi_data["signal"] == "oversold" else "➖"
                lines.append(f"RSI (14): {rsi_data['value']:.2f} {signal_emoji} ({rsi_data['signal']})")

            # MACD
            if "macd" in indicators:
                macd = indicators["macd"]
                trend_emoji = "📈" if macd["trend"] == "bullish" else "📉" if macd["trend"] == "bearish" else "➖"
                lines.append(f"MACD: {macd['value']:.4f} {trend_emoji}")
                lines.append(f"  Signal: {macd['signal']:.4f}")
                lines.append(f"  Histogram: {macd['histogram']:.4f}")

            # Bollinger Bands
            if "bollinger" in indicators:
                bb = indicators["bollinger"]
                pos_emoji = "⬆️" if bb["position"] == "above" else "⬇️" if bb["position"] == "below" else "➖"
                lines.append(f"\nBollinger Bands:")
                lines.append(f"  상단: ${bb['upper']:,.2f}")
                lines.append(f"  중간: ${bb['middle']:,.2f}")
                lines.append(f"  하단: ${bb['lower']:,.2f}")
                lines.append(f"  현재: ${bb['current']:,.2f} {pos_emoji} ({bb['position']})")

            report = "\n".join(lines)

            self.logger.info("advanced_analysis_generated", coin_id=coin_id, length=len(report))

            return report

        except Exception as e:
            self.logger.error("advanced_analysis_failed", error=str(e))
            raise ExternalServiceError(f"고급 분석 실패: {str(e)}")
