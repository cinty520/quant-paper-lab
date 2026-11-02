"""不能偷看未来数据的测试。"""
import numpy as np
import pandas as pd
import pytest

from qpl.backtest import run_backtest
from qpl.strategies import VARIANTS, target_weights


@pytest.mark.parametrize("name", list(VARIANTS))
def test_signal_uses_only_past(prices, name):
    """t 日的目标权重，用截断到 t 日的数据算和用全量数据算必须完全一样。"""
    full = target_weights(name, prices)
    for t in [210, 260, 333, 399]:
        part = target_weights(name, prices.iloc[: t + 1])
        pd.testing.assert_series_equal(part.iloc[-1], full.iloc[t], check_names=False)


@pytest.mark.parametrize("name", list(VARIANTS))
def test_future_shock_does_not_change_past_signals(prices, name):
    shocked = prices.copy()
    shocked.iloc[300:] *= 3.0
    a, b = target_weights(name, prices), target_weights(name, shocked)
    pd.testing.assert_frame_equal(a.iloc[:300], b.iloc[:300])


def test_engine_applies_weights_to_next_day(prices):
    """t 日收盘定的权重只赚 t+1 日收益：用无成本手算结果核对。"""
    rng = np.random.default_rng(1)
    tgt = pd.DataFrame(rng.uniform(0, 0.5, prices.shape), index=prices.index, columns=prices.columns)
    res = run_backtest(prices, tgt, cost_rate=0.0, band=0.0)
    r = prices.pct_change().fillna(0)
    manual = (tgt.shift(1) * r).sum(axis=1)
    np.testing.assert_allclose(res["ret"].to_numpy(), manual.to_numpy(), atol=1e-12)


def test_cheating_signal_gets_no_free_profit(prices):
    """“看到当日涨了才买”的信号若被引擎错误对齐会稳赚；正确引擎下它只赚次日收益。"""
    r = prices.pct_change().fillna(0)
    cheat = (r > 0).astype(float) * 0.5
    res = run_backtest(prices, cheat, cost_rate=0.0, band=0.0)
    same_day = (cheat * r).sum(axis=1)
    assert same_day.mean() > 0.01           # 如果偷看会有明显“收益”
    assert abs(res["ret"].mean()) < 0.005   # 正确对齐后没有这种收益


def test_future_prices_do_not_change_past_returns(prices):
    tgt = target_weights("MA-50", prices)
    shocked = prices.copy()
    shocked.iloc[300:] *= 0.3
    a = run_backtest(prices, tgt)
    b = run_backtest(shocked, target_weights("MA-50", shocked))
    pd.testing.assert_frame_equal(a.iloc[:300], b.iloc[:300])
