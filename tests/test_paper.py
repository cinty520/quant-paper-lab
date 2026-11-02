"""模拟盘台账：费用正确、重复运行不重复记账、漏跑可补。"""
import filecmp

import numpy as np
import pandas as pd
import pytest

from qpl import paper

CFG = {"strategy": "MA-50", "start_date": "2020-08-01", "initial_cash": 10000,
       "fee_rate": 0.006, "slippage": 0.0005, "band": 0.02}


def test_rerun_same_period_is_noop(prices, tmp_path):
    first = paper.run(prices, CFG, tmp_path)
    assert first
    snap = {f: (tmp_path / f).read_bytes() for f in ["trades.csv", "equity.csv"]}
    again = paper.run(prices, CFG, tmp_path)
    assert again == []
    for f, b in snap.items():
        assert (tmp_path / f).read_bytes() == b


def test_catch_up_equals_single_run(prices, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    paper.run(prices.iloc[:250], CFG, a)
    paper.run(prices.iloc[:300], CFG, a)
    paper.run(prices, CFG, a)
    paper.run(prices, CFG, b)
    for f in ["trades.csv", "equity.csv"]:
        assert filecmp.cmp(a / f, b / f, shallow=False)


def test_no_duplicate_ids_and_cash_never_negative(prices, tmp_path):
    paper.run(prices, CFG, tmp_path)
    paper.run(prices, CFG, tmp_path)
    t = pd.read_csv(tmp_path / "trades.csv")
    e = pd.read_csv(tmp_path / "equity.csv")
    assert t["id"].is_unique and e["date"].is_unique
    assert (e["cash"] > -1e-9).all()


def test_fees_and_slippage_on_fill(tmp_path):
    idx = pd.date_range("2021-01-01", periods=3, freq="D")
    px = pd.DataFrame({"BTC-USD": [100.0, 100.0, 100.0], "ETH-USD": [10.0, 10.0, 10.0]}, index=idx)
    cfg = dict(CFG, strategy="VT-60", start_date="2021-01-01")
    import qpl.paper as P
    orig = P.target_weights
    P.target_weights = lambda name, p: pd.DataFrame({"BTC-USD": 0.5, "ETH-USD": 0.0}, index=p.index)
    try:
        paper.run(px.iloc[:1], cfg, tmp_path)
    finally:
        P.target_weights = orig
    t = pd.read_csv(tmp_path / "trades.csv").iloc[0]
    assert t["side"] == "BUY"
    assert t["fill_price"] == pytest.approx(100.05)
    assert t["notional"] == pytest.approx(5000.0)
    assert t["fee"] == pytest.approx(30.0)
    assert t["cash_after"] == pytest.approx(10000 - 5000 - 30)
    e = pd.read_csv(tmp_path / "equity.csv").iloc[0]
    assert e["equity"] == pytest.approx(4970 + 5000 / 100.05 * 100)
