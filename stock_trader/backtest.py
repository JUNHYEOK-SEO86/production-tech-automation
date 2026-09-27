"""
변동성 돌파 전략 백테스트 (일봉 기준)

과거 일봉 데이터로 "이 규칙대로 매매했다면?"을 계산합니다.
- 진입: 당일 고가가 목표가 이상이면 목표가에 매수 (시가가 이미 목표가 위면 시가에 매수)
- 청산: 당일 종가에 매도 (실전의 15:15 매도를 근사), 손절 사용 시 저가가 손절가 이하면 손절가에 매도
- 비용: 매수/매도 수수료 + 매도 시 증권거래세 + 슬리피지(체결 가격 불리함)

사용법:
    python backtest.py                          # config.ini 의 종목/설정으로 실행
    python backtest.py --codes 005930 000660 --start 2023-01-01
    python backtest.py --sweep                  # k 값 0.3~0.8 비교
    python backtest.py --csv 005930.csv         # 직접 받은 일봉 CSV(Date,Open,High,Low,Close) 사용
"""

import argparse
import configparser
import os
import sys

import pandas as pd

from strategy import passes_ma_filter, target_price

HERE = os.path.dirname(os.path.abspath(__file__))


def load_settings():
    cfg = configparser.ConfigParser()
    path = os.path.join(HERE, "config.ini")
    cfg.read(path if os.path.exists(path) else os.path.join(HERE, "config.example.ini"), encoding="utf-8")
    s = cfg["strategy"]
    c = cfg["cost"]
    return {
        "codes": s.get("watchlist", "005930").split(),
        "k": s.getfloat("k", 0.5),
        "ma_days": s.getint("ma_filter_days", 5),
        "stop_loss_pct": s.getfloat("stop_loss_pct", 2.0),
        "fee_pct": c.getfloat("fee_pct", 0.015),
        "tax_pct": c.getfloat("tax_pct", 0.20),
        "slippage_pct": c.getfloat("slippage_pct", 0.10),
    }


def load_data(code, start, end, csv_path=None):
    if csv_path:
        df = pd.read_csv(csv_path, parse_dates=[0], index_col=0)
    else:
        try:
            import FinanceDataReader as fdr
        except ImportError:
            sys.exit("[오류] pip install finance-datareader 를 먼저 실행하세요.")
        df = fdr.DataReader(code, start, end)
    df = df.rename(columns=str.capitalize)[["Open", "High", "Low", "Close"]]
    return df[(df["Open"] > 0) & (df["High"] > 0)].dropna()


def run(df, k, ma_days, stop_loss_pct, fee_pct, tax_pct, slippage_pct):
    """일봉 DataFrame -> 거래 목록 DataFrame (date, entry, exit, ret_pct)."""
    trades = []
    closes = df["Close"].tolist()
    for i in range(1, len(df)):
        prev, today = df.iloc[i - 1], df.iloc[i]
        recent = closes[:i][::-1]  # 전일 종가부터 과거순
        if not passes_ma_filter(recent, ma_days):
            continue
        tgt = target_price(today["Open"], prev["High"], prev["Low"], k)
        if today["High"] < tgt:
            continue
        entry = max(tgt, today["Open"]) * (1 + slippage_pct / 100)
        exit_ = today["Close"]
        if stop_loss_pct:
            stop = entry * (1 - stop_loss_pct / 100)
            if today["Low"] <= stop:  # 일봉으로는 순서를 알 수 없어 보수적으로 손절 처리
                exit_ = stop
        exit_ *= (1 - slippage_pct / 100)
        cost = entry * fee_pct / 100 + exit_ * (fee_pct + tax_pct) / 100
        ret = (exit_ - entry - cost) / entry * 100
        trades.append({"date": df.index[i].date(), "entry": round(entry), "exit": round(exit_), "ret_pct": ret})
    return pd.DataFrame(trades)


def summarize(trades, days):
    if trades.empty:
        return {"거래일수": days, "매매횟수": 0, "승률%": 0, "평균수익%": 0, "누적수익%": 0, "최대낙폭%": 0}
    equity = (1 + trades["ret_pct"] / 100).cumprod()
    mdd = ((equity / equity.cummax()) - 1).min() * 100
    return {
        "거래일수": days,
        "매매횟수": len(trades),
        "승률%": round((trades["ret_pct"] > 0).mean() * 100, 1),
        "평균수익%": round(trades["ret_pct"].mean(), 3),
        "누적수익%": round((equity.iloc[-1] - 1) * 100, 1),
        "최대낙폭%": round(mdd, 1),
    }


def main():
    st = load_settings()
    p = argparse.ArgumentParser(description="변동성 돌파 전략 백테스트")
    p.add_argument("--codes", nargs="+", default=st["codes"], help="종목코드 (예: 005930 000660)")
    p.add_argument("--start", default="2022-01-01")
    p.add_argument("--end", default=None)
    p.add_argument("--k", type=float, default=st["k"])
    p.add_argument("--ma", type=int, default=st["ma_days"], help="이동평균 필터 일수 (0=사용 안 함)")
    p.add_argument("--stop", type=float, default=st["stop_loss_pct"], help="손절 %% (0=사용 안 함)")
    p.add_argument("--sweep", action="store_true", help="k 값 0.3~0.8 비교")
    p.add_argument("--csv", default=None, help="일봉 CSV 파일 (종목 1개)")
    a = p.parse_args()

    codes = ["CSV"] if a.csv else a.codes
    ks = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8] if a.sweep else [a.k]
    rows = []
    for code in codes:
        df = load_data(code, a.start, a.end, a.csv)
        if len(df) < 30:
            print(f"[건너뜀] {code}: 데이터 부족")
            continue
        for k in ks:
            t = run(df, k, a.ma, a.stop, st["fee_pct"], st["tax_pct"], st["slippage_pct"])
            rows.append({"종목": code, "k": k, **summarize(t, len(df))})
            if not a.sweep:
                out = os.path.join(HERE, f"backtest_{code}.csv")
                t.to_csv(out, index=False, encoding="utf-8-sig")

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(f"\n=== 변동성 돌파 백테스트 ({a.start} ~ {a.end or '오늘'}) | MA필터 {a.ma}일, 손절 {a.stop}% ===")
    print(f"비용: 수수료 {st['fee_pct']}%(편도), 거래세 {st['tax_pct']}%, 슬리피지 {st['slippage_pct']}%(편도)")
    print(result.to_string(index=False))
    print("\n※ 과거 성과가 미래 수익을 보장하지 않습니다. 일봉 근사치이므로 모의투자로 반드시 재확인하세요.")


if __name__ == "__main__":
    main()
