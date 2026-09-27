"""
변동성 돌파 전략 (Larry Williams)

매수: 오늘 가격이 목표가 = 오늘 시가 + (전일 고가 - 전일 저가) * k 를 돌파하면 매수
매도: 장 마감 전(기본 15:15) 전량 매도, 또는 손절가 도달 시 매도
필터(선택): 전일 종가가 N일 이동평균 위에 있을 때만 매매 (하락장 회피)
"""


def target_price(today_open, prev_high, prev_low, k):
    return today_open + (prev_high - prev_low) * k


def passes_ma_filter(closes_recent_first, ma_days):
    """closes_recent_first: 전일 종가부터 과거순. ma_days=0 이면 필터 사용 안 함."""
    if not ma_days:
        return True
    if len(closes_recent_first) < ma_days:
        return False
    ma = sum(closes_recent_first[:ma_days]) / ma_days
    return closes_recent_first[0] > ma


def tick_size(price):
    """국내 주식 호가 단위 (2023년 이후 KOSPI/KOSDAQ 공통)."""
    for limit, tick in ((2000, 1), (5000, 5), (20000, 10), (50000, 50), (200000, 100), (500000, 500)):
        if price < limit:
            return tick
    return 1000


def round_up_to_tick(price):
    t = tick_size(price)
    return int(-(-price // t) * t)
