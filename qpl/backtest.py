"""小而清楚的日线回测引擎。

时序约定（防止偷看未来）：
- target 的第 t 行 = 用 t 日收盘及以前的数据算出的目标权重；
- 在 t 日收盘按 target[t] 调仓并付费用；
- 新权重只赚取 t+1 日的收益（close[t] → close[t+1]）。
成本：成交额 × cost_rate（手续费 + 滑点，按每一边计）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def run_backtest(prices: pd.DataFrame, target: pd.DataFrame, cost_rate: float = config.COST_RATE,
                 band: float = config.REBALANCE_BAND, rebalance: bool = True) -> pd.DataFrame:
    """返回逐日 DataFrame：ret(扣费后组合收益)、turnover(当日成交额/权益)、exposure(持仓总权重)。

    第 0 行只建仓（ret = -成本），之后每行先按持仓计收益，再在收盘调仓。
    rebalance=False 时只在第 0 行建仓，之后不再交易（买入持有）。
    """
    px = prices.to_numpy(dtype=float)
    n, k = px.shape
    rets = np.zeros((n, k))
    rets[1:] = np.nan_to_num(px[1:] / px[:-1] - 1.0)
    tgt = target.reindex(index=prices.index, columns=prices.columns).fillna(0.0).to_numpy(dtype=float)

    w = np.zeros(k)
    out = np.zeros((n, 3))
    for t in range(n):
        gross = 0.0
        if t > 0:
            gross = float(w @ rets[t])
            if 1.0 + gross > 0:
                w = w * (1.0 + rets[t]) / (1.0 + gross)  # 持仓随价格漂移
        turnover = 0.0
        if t == 0 or rebalance:
            diff = tgt[t] - w
            mask = (np.abs(diff) > band) | ((tgt[t] == 0) & (w != 0))
            trade = np.where(mask, diff, 0.0)
            turnover = float(np.abs(trade).sum())
            w = w + trade
        cost = turnover * cost_rate
        out[t] = ((1.0 + gross) * (1.0 - cost) - 1.0, turnover, float(np.abs(w).sum()))
    return pd.DataFrame(out, index=prices.index, columns=["ret", "turnover", "exposure"])


def simulate(prices: pd.DataFrame, target: pd.DataFrame, start: str, end: str,
             cost_rate: float = config.COST_RATE, rebalance: bool = True) -> pd.DataFrame:
    """从 start 前一日收盘空仓建仓，评估 [start, end] 区间。建仓成本并入第一天。"""
    s = pd.Timestamp(start)
    window = prices.loc[s - pd.Timedelta(days=1): end]
    res = run_backtest(window, target, cost_rate=cost_rate, rebalance=rebalance)
    first = res.iloc[0]
    res = res.iloc[1:].copy()
    res.iloc[0, 0] = (1 + res.iloc[0, 0]) * (1 + first["ret"]) - 1
    res.iloc[0, 1] += first["turnover"]
    return res


def buy_and_hold(prices: pd.DataFrame, weights: dict, start: str, end: str,
                 cost_rate: float = config.COST_RATE) -> pd.DataFrame:
    tgt = pd.DataFrame({c: weights.get(c, 0.0) for c in prices.columns}, index=prices.index)
    return simulate(prices, tgt, start, end, cost_rate, rebalance=False)


BENCHMARKS = {
    "买入持有BTC": {"BTC-USD": 1.0},
    "BTC/ETH等权买入持有": {"BTC-USD": 0.5, "ETH-USD": 0.5},
}
