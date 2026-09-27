"""
변동성 돌파 단타 자동매매 (키움증권 REST API)

하루 흐름:
  09:00 이후  종목별 목표가 계산 (시가 + 전일 변동폭 × k), 이동평균 필터 적용
  매수 시간    현재가가 목표가를 돌파하면 시장가 매수 (종목당 하루 1회)
  보유 중      손절가 도달 시 매도
  15:15       보유 종목 전량 시장가 매도 후 종료

안전장치:
  - 기본 모드는 dry (주문 없이 신호만 기록). mock → real 순서로 검증하세요.
  - real 모드는 시작할 때 'REAL' 을 직접 입력해야 실행됩니다.
  - 하루 손실 한도 / 최대 보유 종목 수 / 하루 최대 주문 횟수
  - 이 폴더에 STOP 이라는 파일을 만들면 즉시 전량 매도 후 종료합니다.
  - 재시작해도 오늘 이미 산 종목은 다시 사지 않습니다(state 파일).
"""

import configparser
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from kiwoom_api import KiwoomAPI, KiwoomError
from strategy import passes_ma_filter, round_up_to_tick, target_price

HERE = os.path.dirname(os.path.abspath(__file__))
KST = ZoneInfo("Asia/Seoul")
STOP_FILE = os.path.join(HERE, "STOP")
LOG_DIR = os.path.join(HERE, "logs")

log = logging.getLogger("trader")


def hm(s):
    h, m = s.strip().split(":")
    return int(h), int(m)


def at(now, hhmm):
    h, m = hm(hhmm)
    return now.replace(hour=h, minute=m, second=0, microsecond=0)


class Trader:
    def __init__(self, api, cfg, mode, today):
        s, r, c = cfg["strategy"], cfg["risk"], cfg["cost"]
        self.api = api
        self.mode = mode
        self.today = today  # 'YYYYMMDD'
        self.codes = s.get("watchlist").split()
        self.k = s.getfloat("k", 0.5)
        self.ma_days = s.getint("ma_filter_days", 5)
        self.stop_loss_pct = s.getfloat("stop_loss_pct", 2.0)
        self.buy_start, self.buy_end, self.sell_time = s.get("buy_start"), s.get("buy_end"), s.get("sell_time")
        self.budget = r.getint("budget_per_stock")
        self.max_positions = r.getint("max_positions")
        self.loss_limit = r.getint("daily_loss_limit")
        self.max_orders = r.getint("max_orders_per_day")
        self.fee = c.getfloat("fee_pct", 0.015) / 100
        self.tax = c.getfloat("tax_pct", 0.20) / 100

        self.targets = {}        # code -> 목표가 (None 이면 오늘 매매 제외)
        self.positions = {}      # code -> {'qty', 'entry'}
        self.last_price = {}
        self.realized = 0
        self.orders = 0
        self.bought_today = set()
        self.halted = False
        self.state_path = os.path.join(LOG_DIR, f"state_{today}_{mode}.json")
        self.trades_path = os.path.join(LOG_DIR, f"trades_{today}_{mode}.csv")
        self._load_state()

    # ---------- 상태 저장 (재시작 대비) ----------
    def _load_state(self):
        if os.path.exists(self.state_path):
            with open(self.state_path, encoding="utf-8") as f:
                st = json.load(f)
            self.bought_today = set(st.get("bought_today", []))
            self.realized = st.get("realized", 0)
            self.orders = st.get("orders", 0)
            self.positions = st.get("positions", {})
            log.info(f"이전 상태 불러옴: 매수완료 {sorted(self.bought_today)}, 실현손익 {self.realized:,}원")

    def _save_state(self):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({"bought_today": sorted(self.bought_today), "realized": self.realized,
                       "orders": self.orders, "positions": self.positions}, f, ensure_ascii=False)

    def _record(self, side, code, qty, price, note=""):
        new = not os.path.exists(self.trades_path)
        with open(self.trades_path, "a", encoding="utf-8-sig") as f:
            if new:
                f.write("time,side,code,qty,price,note\n")
            f.write(f"{datetime.now(KST):%H:%M:%S},{side},{code},{qty},{price},{note}\n")

    # ---------- 준비 ----------
    def sync_holdings(self):
        """모의/실전: 실제 계좌 잔고와 맞추기 (체결 수량, 평균단가 반영)."""
        if self.mode == "dry":
            return
        held = self.api.get_holdings()
        for code in list(self.positions):
            if code not in held:
                log.warning(f"{code}: 계좌에 잔고 없음 → 보유 목록에서 제거")
                self.positions.pop(code)
        for code, h in held.items():
            if code in self.codes:
                pos = self.positions.setdefault(code, {"qty": 0, "entry": h["avg_price"]})
                pos["qty"] = h["qty"]
                if h["avg_price"]:
                    pos["entry"] = h["avg_price"]

    def prepare_targets(self):
        for code in self.codes:
            if code in self.targets:
                continue
            try:
                q = self.api.get_quote(code)
                if not q["open"]:
                    continue  # 아직 시가 미형성
                rows = self.api.get_daily(code, self.today)
                if rows and rows[0]["date"] == self.today:
                    rows = rows[1:]  # 오늘 봉 제외
                if not rows:
                    self.targets[code] = None
                    continue
                prev = rows[0]
                closes = [r["close"] for r in rows]
                if not passes_ma_filter(closes, self.ma_days):
                    self.targets[code] = None
                    log.info(f"{code} {q['name']}: 이동평균 필터 미통과 → 오늘 제외")
                    continue
                tgt = round_up_to_tick(target_price(q["open"], prev["high"], prev["low"], self.k))
                self.targets[code] = tgt
                log.info(f"{code} {q['name']}: 시가 {q['open']:,} / 전일범위 {prev['high'] - prev['low']:,} → 목표가 {tgt:,}")
            except KiwoomError as e:
                log.error(f"{code} 목표가 계산 실패: {e}")

    # ---------- 손익/리스크 ----------
    def unrealized(self):
        total = 0
        for code, p in self.positions.items():
            price = self.last_price.get(code, p["entry"])
            total += (price - p["entry"]) * p["qty"] - price * p["qty"] * (self.fee + self.tax)
        return int(total)

    def daily_pnl(self):
        return self.realized + self.unrealized()

    # ---------- 주문 ----------
    def _can_order(self):
        if self.orders >= self.max_orders:
            if not self.halted:
                log.error(f"하루 최대 주문 횟수({self.max_orders}) 도달 → 신규 주문 중지")
            self.halted = True
            return False
        return True

    def buy(self, code, price):
        qty = self.budget // price
        if qty < 1 or not self._can_order():
            return
        if self.mode != "dry":
            ord_no = self.api.buy_market(code, qty)
            log.info(f"[매수 주문] {code} {qty}주 시장가 (주문번호 {ord_no})")
        else:
            log.info(f"[매수 신호/dry] {code} {qty}주 @ {price:,}")
        self.orders += 1
        self.bought_today.add(code)
        self.positions[code] = {"qty": qty, "entry": price}
        self._record("BUY", code, qty, price)
        self._save_state()

    def sell(self, code, price, reason):
        pos = self.positions.get(code)
        if not pos or pos["qty"] < 1:
            return
        if self.mode != "dry":
            if self.orders >= self.max_orders + 10:  # 매도는 한도 초과 후에도 여유분 허용 (청산 우선)
                log.error(f"{code}: 주문 횟수 비상 한도 초과. 직접 HTS/MTS에서 매도하세요!")
                return
            ord_no = self.api.sell_market(code, pos["qty"])
            log.info(f"[매도 주문] {code} {pos['qty']}주 시장가 - {reason} (주문번호 {ord_no})")
        else:
            log.info(f"[매도 신호/dry] {code} {pos['qty']}주 @ {price:,} - {reason}")
        self.orders += 1
        pnl = (price - pos["entry"]) * pos["qty"] - int(pos["entry"] * pos["qty"] * self.fee
                                                         + price * pos["qty"] * (self.fee + self.tax))
        self.realized += pnl
        self.positions.pop(code)
        self._record("SELL", code, pos["qty"], price, f"{reason} 손익 {pnl:+,}원")
        log.info(f"    → 예상 손익 {pnl:+,}원 / 오늘 실현 {self.realized:+,}원")
        self._save_state()

    def liquidate(self, reason):
        for code in list(self.positions):
            price = self.last_price.get(code) or self.api.get_quote(code)["price"]
            self.sell(code, price, reason)

    # ---------- 한 번의 점검 ----------
    def step(self, now):
        """now 시점의 1회 점검. 장 종료(모든 청산 완료) 시 False 반환."""
        if os.path.exists(STOP_FILE):
            log.warning("STOP 파일 감지 → 전량 매도 후 종료")
            self.liquidate("수동 정지")
            return False
        if now < at(now, "09:00"):
            return True
        if now >= at(now, self.sell_time):
            self.liquidate("장마감 청산")
            return False

        self.prepare_targets()
        for code in self.codes:
            try:
                price = self.api.get_quote(code)["price"]
            except KiwoomError as e:
                log.error(f"{code} 시세 조회 실패: {e}")
                continue
            if not price:
                continue
            self.last_price[code] = price
            pos = self.positions.get(code)
            if pos and self.stop_loss_pct and price <= pos["entry"] * (1 - self.stop_loss_pct / 100):
                self.sell(code, price, f"손절 -{self.stop_loss_pct}%")
                continue
            tgt = self.targets.get(code)
            if (not pos and tgt and price >= tgt and code not in self.bought_today and not self.halted
                    and at(now, self.buy_start) <= now < at(now, self.buy_end)
                    and len(self.positions) < self.max_positions):
                self.buy(code, price)

        if not self.halted and self.daily_pnl() <= -self.loss_limit:
            log.error(f"하루 손실 한도 도달 ({self.daily_pnl():+,}원) → 전량 매도, 오늘 신규 매수 중지")
            self.halted = True
            self.liquidate("손실 한도")
        return True


def setup_logging(today, mode):
    os.makedirs(LOG_DIR, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    fh = logging.FileHandler(os.path.join(LOG_DIR, f"trader_{today}_{mode}.log"), encoding="utf-8")
    sh = logging.StreamHandler(sys.stdout)
    for h in (fh, sh):
        h.setFormatter(fmt)
        log.addHandler(h)
    log.setLevel(logging.INFO)


def main():
    cfg = configparser.ConfigParser()
    path = os.path.join(HERE, "config.ini")
    if not os.path.exists(path):
        sys.exit("[오류] config.ini 가 없습니다. config.example.ini 를 복사해 config.ini 로 만들고 값을 채우세요.")
    cfg.read(path, encoding="utf-8")
    mode = cfg["mode"].get("mode", "dry").strip().lower()
    if mode not in ("dry", "mock", "real"):
        sys.exit("[오류] mode 는 dry / mock / real 중 하나여야 합니다.")
    if mode == "real":
        print("!!! 실전 계좌로 실제 주문이 나갑니다. 손실이 발생할 수 있습니다. !!!")
        if input("계속하려면 REAL 을 입력하세요: ").strip() != "REAL":
            sys.exit("취소했습니다.")

    now = datetime.now(KST)
    today = now.strftime("%Y%m%d")
    setup_logging(today, mode)
    if now.weekday() >= 5:
        sys.exit("주말에는 장이 열리지 않습니다.")

    k = cfg["kiwoom"]
    if not k.get("appkey") or not k.get("secretkey"):
        sys.exit("[오류] config.ini 에 appkey / secretkey 를 입력하세요.")
    # dry 모드도 시세 조회는 필요하므로 모의투자 서버에 접속
    api = KiwoomAPI(k.get("appkey").strip(), k.get("secretkey").strip(), mock=(mode != "real"))
    api.login()
    log.info(f"=== 자동매매 시작 | 모드: {mode} | 종목: {cfg['strategy'].get('watchlist')} ===")

    trader = Trader(api, cfg, mode, today)
    trader.sync_holdings()
    poll = cfg["strategy"].getint("poll_seconds", 3)
    last_sync = time.time()
    while True:
        try:
            if not trader.step(datetime.now(KST)):
                break
            if mode != "dry" and time.time() - last_sync > 60:
                trader.sync_holdings()
                last_sync = time.time()
        except KeyboardInterrupt:
            log.warning("Ctrl+C 입력 → 보유 종목 전량 매도 후 종료")
            trader.liquidate("수동 종료")
            break
        except Exception as e:  # 네트워크 오류 등: 기록하고 계속
            log.exception(f"오류: {e}")
            time.sleep(10)
        time.sleep(poll)

    if mode != "dry":
        time.sleep(5)
        left = {c: h for c, h in api.get_holdings().items() if c in trader.codes}
        if left:
            log.error(f"아직 남은 보유 종목: {left} → HTS/MTS에서 확인하세요!")
    log.info(f"=== 종료 | 오늘 실현손익(추정) {trader.realized:+,}원 | 주문 {trader.orders}회 ===")


if __name__ == "__main__":
    main()
