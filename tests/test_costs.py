"""费用计算测试。"""
import numpy as np
import pandas as pd
import pytest

from qpl.backtest import buy_and_hold, run_backtest


def flat_prices(n=5):
    idx = pd.date_range("2021-01-01", periods=n, freq="D")
    return pd.DataFrame({"BTC-USD": 100.0, "ETH-USD": 50.0}, index=idx)


def test_round_trip_costs_twice_the_rate():
    px = flat_prices()
    tgt = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    tgt.iloc[1, 0] = 1.0  # 第 1 天买入 100%，第 2 天卖出
    res = run_backtest(px, tgt, cost_rate=0.0065, band=0.0)
    eq = (1 + res["ret"]).prod()
    assert eq == pytest.approx((1 - 0.0065) ** 2)
    assert res["turnover"].sum() == pytest.approx(2.0)


def test_band_skips_small_rebalances():
    px = flat_prices()
    tgt = pd.DataFrame(0.5, index=px.index, columns=px.columns)
    tgt.iloc[2:, 0] = 0.51  # 只差 1%，小于 2% 的调仓阈值
    res = run_backtest(px, tgt, cost_rate=0.01, band=0.02)
    assert res["turnover"].iloc[0] == pytest.approx(1.0)
    assert res["turnover"].iloc[1:].sum() == 0.0


def test_exit_to_zero_always_trades_even_below_band():
    px = flat_prices()
    tgt = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    tgt.iloc[0, 0] = 0.01
    res = run_backtest(px, tgt, cost_rate=0.01, band=0.02)
    assert res["exposure"].iloc[-1] == 0.0


def test_buy_and_hold_pays_entry_cost_once():
    idx = pd.date_range("2021-01-01", periods=4, freq="D")
    px = pd.DataFrame({"BTC-USD": [100, 110, 121, 133.1], "ETH-USD": [50, 50, 50, 50]}, index=idx)
    res = buy_and_hold(px, {"BTC-USD": 1.0}, "2021-01-02", "2021-01-04", cost_rate=0.0065)
    assert (1 + res["ret"]).prod() == pytest.approx(1.331 * (1 - 0.0065))
    assert res["turnover"].sum() == pytest.approx(1.0)
