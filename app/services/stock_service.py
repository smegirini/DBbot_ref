"""
Stock Chart Service
네이버 금융 API를 사용한 주식 차트 생성
"""
import requests
import io
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from app.utils import LoggerMixin, ExternalServiceError


class StockService(LoggerMixin):
    """주식 정보 및 차트 생성 서비스"""

    def __init__(self):
        """Initialize stock service"""
        self.font_path = "res/fonts/NanumGothic.ttf"  # 폰트 경로 (필요 시 설치)
        self.logger.info("stock_service_initialized")

    async def create_stock_chart(self, query: str) -> Optional[io.BytesIO]:
        """
        주식 차트 이미지 생성

        Args:
            query: 종목명 또는 종목코드

        Returns:
            Optional[io.BytesIO]: 생성된 이미지 또는 None

        Raises:
            ExternalServiceError: 차트 생성 실패 시
        """
        try:
            # 1. 종목 코드 검색
            autocomplete_url = (
                f"https://ac.stock.naver.com/ac?q={query}&"
                f"target=stock%2Cipo%2Cindex%2Cmarketindicator"
            )
            autocomplete_response = requests.get(autocomplete_url, timeout=10)
            autocomplete_response.raise_for_status()
            autocomplete_json = autocomplete_response.json()

            if not autocomplete_json['items'] or not autocomplete_json['items'][0]:
                raise ExternalServiceError("종목을 찾는데 실패했습니다.")

            type_code = autocomplete_json['items'][0]['typeCode']
            if type_code not in ["KOSPI", "KOSDAQ"]:
                raise ExternalServiceError("현재는 국내 주식시장만 지원합니다.")

            stock_code = autocomplete_json['items'][0]["code"]
            stock_name = autocomplete_json['items'][0]["name"]

            self.logger.info("stock_found", code=stock_code, name=stock_name)

            # 2. 차트 이미지 다운로드
            chart_url = f"https://ssl.pstatic.net/imgfinance/chart/item/area/day/{stock_code}.png"
            chart_response = requests.get(chart_url, stream=True, timeout=10)
            chart_response.raise_for_status()

            chart_image = Image.open(io.BytesIO(chart_response.content)).convert("RGBA")
            chart_width, chart_height = chart_image.size

            # 3. 실시간 주가 데이터 조회
            realtime_url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_RECENT_ITEM:{stock_code}"
            realtime_response = requests.get(realtime_url, timeout=10)
            realtime_response.raise_for_status()
            realtime_json = realtime_response.json()

            if (
                realtime_json['resultCode'] != 'success'
                or not realtime_json['result']['areas']
                or not realtime_json['result']['areas'][0]['datas']
            ):
                raise ExternalServiceError("실시간 주가 데이터를 가져올 수 없습니다.")

            stock_data = realtime_json['result']['areas'][0]['datas'][0]

            # 4. 새 이미지 생성 (차트 + 정보)
            new_height = 550
            new_image = Image.new("RGB", (chart_width, new_height), "white")
            new_image.paste(chart_image, (0, new_height - chart_height), chart_image)

            # 5. 주식 정보 추가
            draw = ImageDraw.Draw(new_image)

            # 폰트 설정 (기본 폰트 사용)
            try:
                font_title = ImageFont.truetype(self.font_path, 40)
                font_code = ImageFont.truetype(self.font_path, 18)
                font_normal = ImageFont.truetype(self.font_path, 30)
            except:
                font_title = ImageFont.load_default()
                font_code = ImageFont.load_default()
                font_normal = ImageFont.load_default()

            text_color = (0, 0, 0)

            # 종목명과 코드
            title_text = stock_name
            code_text = stock_code

            title_x, title_y = 15, 15
            draw.text((title_x, title_y), title_text, font=font_title, fill=text_color)

            title_bbox = font_title.getbbox(title_text)
            code_bbox = font_code.getbbox(code_text)

            code_x = title_x + title_bbox[2] + 10
            code_y = title_y + title_bbox[3] - code_bbox[3]

            draw.text((code_x, code_y), code_text, font=font_code, fill=text_color)

            # 현재가 및 등락
            current_price_text = f"{stock_data['nv']:,}"
            change_text = f"{stock_data['cv']:,}"
            change_rate_text = f"{stock_data['cr']:.2f}%"

            price_x = 15
            price_y = code_y + code_bbox[3] + 30
            change_color = (
                (255, 0, 0) if stock_data['rf'] == '2'  # 상승: 빨강
                else (0, 0, 255) if stock_data['rf'] == '5'  # 하락: 파랑
                else text_color
            )
            current_price_color = change_color if stock_data['rf'] != '0' else text_color

            draw.text((price_x, price_y), current_price_text, font=font_title, fill=current_price_color)
            price_bbox = font_title.getbbox(current_price_text)
            price_bottom_y = price_y + price_bbox[3]

            change_symbol = "▲" if stock_data['rf'] == '2' else "▼" if stock_data['rf'] == '5' else ""
            change_x = price_x + font_title.getlength(current_price_text) + 10

            change_symbol_bbox = font_normal.getbbox(change_symbol)
            change_text_bbox = font_normal.getbbox(change_text)
            change_rate_text_bbox = font_normal.getbbox(change_rate_text)

            change_symbol_y = price_bottom_y - change_symbol_bbox[3]
            change_text_y = price_bottom_y - change_rate_text_bbox[3]
            change_rate_text_y = price_bottom_y - change_rate_text_bbox[3]

            draw.text((change_x, change_symbol_y), change_symbol, font=font_normal, fill=change_color)
            draw.text((change_x + font_normal.getlength(change_symbol), change_text_y), change_text, font=font_normal, fill=change_color)
            draw.text((change_x + font_normal.getlength(change_symbol + change_text) + 15, change_rate_text_y), change_rate_text, font=font_normal, fill=change_color)

            # 추가 정보 (전일, 시가, 고가, 저가, 거래량, 거래대금)
            info_x_start_label = 15
            info_x_start_value = 90
            info_y_start = price_y + font_title.getbbox(current_price_text)[3] + 30
            line_height = 32
            info_margin = 220

            # 첫 번째 열
            draw.text((info_x_start_label, info_y_start), "전일", font=font_normal, fill=text_color)
            draw.text((info_x_start_label, info_y_start + line_height), "시가", font=font_normal, fill=text_color)
            draw.text((info_x_start_label, info_y_start + 2 * line_height), "저가", font=font_normal, fill=text_color)

            draw.text((info_x_start_value, info_y_start), f"{stock_data['pcv']:,}", font=font_normal, fill=text_color)
            draw.text((info_x_start_value, info_y_start + line_height), f"{stock_data['ov']:,}", font=font_normal, fill=text_color)
            draw.text((info_x_start_value, info_y_start + 2 * line_height), f"{stock_data['lv']:,}", font=font_normal, fill=text_color)

            # 두 번째 열
            info_x_start_label_col2 = info_x_start_value + info_margin
            info_x_start_value_col2 = info_x_start_label_col2 + 150

            draw.text((info_x_start_label_col2, info_y_start), "고가", font=font_normal, fill=text_color)
            draw.text((info_x_start_label_col2, info_y_start + line_height), "거래량", font=font_normal, fill=text_color)
            draw.text((info_x_start_label_col2, info_y_start + 2 * line_height), "거래대금", font=font_normal, fill=text_color)

            high_price_text = f"{stock_data['hv']:,}"
            volume_text = f"{stock_data['aq']:,}"
            transaction_amount_text = f"{int(stock_data['aa']/1000000):,} 백만"

            value_col2_x = info_x_start_value_col2
            draw.text((value_col2_x, info_y_start), high_price_text, font=font_normal, fill=text_color)
            draw.text((value_col2_x, info_y_start + line_height), volume_text, font=font_normal, fill=text_color)
            draw.text((value_col2_x, info_y_start + 2 * line_height), transaction_amount_text, font=font_normal, fill=text_color)

            # 6. 이미지를 BytesIO로 변환
            img_byte_arr = io.BytesIO()
            new_image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)

            self.logger.info("stock_chart_created", stock_code=stock_code)
            return img_byte_arr

        except requests.exceptions.RequestException as e:
            self.logger.error("stock_chart_request_failed", error=str(e))
            raise ExternalServiceError(f"주식 정보를 가져오는데 실패했습니다: {str(e)}")
        except Exception as e:
            self.logger.error("stock_chart_creation_failed", error=str(e))
            raise ExternalServiceError(f"차트 생성 중 오류가 발생했습니다: {str(e)}")
