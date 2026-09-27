"""
키움증권 REST API 클라이언트 (https://openapi.kiwoom.com)

- 실전: https://api.kiwoom.com / 모의투자: https://mockapi.kiwoom.com
- API 명세(필드명, api-id)는 키움 개발자 사이트 문서 기준입니다. 키움이 명세를 바꾸면
  이 파일만 고치면 되도록 API 호출을 여기에 모아두었습니다.
"""

import time

import requests

REAL_URL = "https://api.kiwoom.com"
MOCK_URL = "https://mockapi.kiwoom.com"


def to_int(value):
    """키움 응답의 '+70000', '-1500', '000123' 같은 문자열을 정수로 변환 (부호는 등락 표시라 제거)."""
    if value is None:
        return 0
    s = str(value).strip().replace(",", "").lstrip("+-")
    return int(float(s)) if s else 0


class KiwoomError(Exception):
    pass


class KiwoomAPI:
    MIN_INTERVAL = 0.25  # 초당 요청 수 제한 대비 최소 간격(초)

    def __init__(self, appkey, secretkey, mock=True, timeout=10):
        self.base = MOCK_URL if mock else REAL_URL
        self.appkey = appkey
        self.secretkey = secretkey
        self.timeout = timeout
        self.token = None
        self._last_call = 0.0

    # ---------- 공통 ----------
    def login(self):
        r = requests.post(
            f"{self.base}/oauth2/token",
            json={"grant_type": "client_credentials", "appkey": self.appkey, "secretkey": self.secretkey},
            headers={"Content-Type": "application/json;charset=UTF-8"},
            timeout=self.timeout,
        )
        data = r.json()
        self.token = data.get("token")
        if not self.token:
            raise KiwoomError(f"토큰 발급 실패: {data.get('return_msg') or data}")
        return self.token

    def _post(self, path, api_id, body):
        if not self.token:
            self.login()
        wait = self.MIN_INTERVAL - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()
        r = requests.post(
            f"{self.base}{path}",
            json=body,
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": f"Bearer {self.token}",
                "api-id": api_id,
            },
            timeout=self.timeout,
        )
        data = r.json()
        code = data.get("return_code", 0)
        if str(code) not in ("0", ""):
            raise KiwoomError(f"[{api_id}] {data.get('return_msg') or data}")
        return data

    # ---------- 시세 ----------
    def get_quote(self, code):
        """현재가/시가/고가/저가 (ka10001 주식기본정보요청)."""
        d = self._post("/api/dostk/stkinfo", "ka10001", {"stk_cd": code})
        return {
            "code": code,
            "name": d.get("stk_nm", ""),
            "price": to_int(d.get("cur_prc")),
            "open": to_int(d.get("open_pric")),
            "high": to_int(d.get("high_pric")),
            "low": to_int(d.get("low_pric")),
        }

    def get_daily(self, code, base_date):
        """일봉 목록, 최신순 (ka10081 주식일봉차트조회요청). base_date: 'YYYYMMDD'."""
        d = self._post("/api/dostk/chart", "ka10081", {"stk_cd": code, "base_dt": base_date, "upd_stkpce_tp": "1"})
        rows = d.get("stk_dt_pole_chart_qry") or []
        return [
            {
                "date": row.get("dt"),
                "open": to_int(row.get("open_pric")),
                "high": to_int(row.get("high_pric")),
                "low": to_int(row.get("low_pric")),
                "close": to_int(row.get("cur_prc")),
            }
            for row in rows
        ]

    # ---------- 주문 ----------
    def buy_market(self, code, qty):
        """시장가 매수 (kt10000). 주문번호 반환."""
        d = self._post("/api/dostk/ordr", "kt10000", {
            "dmst_stex_tp": "KRX", "stk_cd": code, "ord_qty": str(qty), "ord_uv": "", "trde_tp": "3", "cond_uv": "",
        })
        return d.get("ord_no")

    def sell_market(self, code, qty):
        """시장가 매도 (kt10001). 주문번호 반환."""
        d = self._post("/api/dostk/ordr", "kt10001", {
            "dmst_stex_tp": "KRX", "stk_cd": code, "ord_qty": str(qty), "ord_uv": "", "trde_tp": "3", "cond_uv": "",
        })
        return d.get("ord_no")

    # ---------- 계좌 ----------
    def get_holdings(self):
        """보유 종목 {종목코드: {'qty', 'avg_price', 'price'}} (kt00018 계좌평가잔고내역요청)."""
        d = self._post("/api/dostk/acnt", "kt00018", {"qry_tp": "1", "dmst_stex_tp": "KRX"})
        holdings = {}
        for row in d.get("acnt_evlt_remn_indv_tot") or []:
            code = str(row.get("stk_cd", "")).lstrip("A")
            qty = to_int(row.get("trde_able_qty") or row.get("rmnd_qty"))
            if code and qty > 0:
                holdings[code] = {
                    "qty": qty,
                    "avg_price": to_int(row.get("pur_pric")),
                    "price": to_int(row.get("cur_prc")),
                }
        return holdings
