"""候选策略。每个函数只用 t 日及之前的收盘价算出 t 日收盘时的目标权重。

组合规则：BTC、ETH 各分配 50% 资金预算，每个资产的权重 = 0.5 × 信号(0/1) × 缩放(≤1)。
只做多或空仓（现货不能做空），不加杠杆，权重总和 ≤ 1。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

BUDGET = 0.5
VOL_WINDOW = 30
MR_VOL_WINDOW = 60


def _log_ret(px: pd.DataFrame) -> pd.DataFrame:
    return np.log(px).diff()


def vol_scale(px: pd.DataFrame, target_vol: float) -> pd.DataFrame:
    """波动率目标缩放：target / 近 30 日年化实现波动率，上限 1（不加杠杆）。"""
    rv = _log_ret(px).rolling(VOL_WINDOW).std() * np.sqrt(config.ANN)
    return (target_vol / rv).clip(upper=1.0).fillna(0.0)


def tsmom(px, lookback):
    """时间序列动量：过去 lookback 天收益为正则持有，否则空仓。"""
    return BUDGET * (px / px.shift(lookback) - 1 > 0).astype(float)


def sma_trend(px, n):
    """趋势跟随：收盘价在 n 日均线之上则持有。"""
    return BUDGET * (px > px.rolling(n).mean()).astype(float)


def vt_hold(px, target_vol):
    """始终持有，但按波动率目标缩放仓位。"""
    return BUDGET * vol_scale(px, target_vol) * px.notna()


def sma_vt(px, n, target_vol=0.5):
    """均线趋势信号 × 波动率目标缩放。"""
    return sma_trend(px, n) * vol_scale(px, target_vol)


def mean_rev(px, lookback, z_entry):
    """短期均值回归：近 lookback 天累计对数收益的 z 值低于阈值则次日持有。"""
    r = _log_ret(px)
    z = r.rolling(lookback).sum() / (r.rolling(MR_VOL_WINDOW).std() * np.sqrt(lookback))
    return BUDGET * (z < z_entry).astype(float)


# 预注册的全部变体（与 docs/PREREGISTRATION.md 一致，共 15 个）
VARIANTS = {
    "TS-30": ("时间序列动量", tsmom, {"lookback": 30}),
    "TS-90": ("时间序列动量", tsmom, {"lookback": 90}),
    "TS-180": ("时间序列动量", tsmom, {"lookback": 180}),
    "MA-50": ("均线趋势", sma_trend, {"n": 50}),
    "MA-100": ("均线趋势", sma_trend, {"n": 100}),
    "MA-200": ("均线趋势", sma_trend, {"n": 200}),
    "VT-40": ("波动率目标持有", vt_hold, {"target_vol": 0.4}),
    "VT-60": ("波动率目标持有", vt_hold, {"target_vol": 0.6}),
    "MAVT-50": ("均线趋势+波动率目标", sma_vt, {"n": 50}),
    "MAVT-100": ("均线趋势+波动率目标", sma_vt, {"n": 100}),
    "MAVT-200": ("均线趋势+波动率目标", sma_vt, {"n": 200}),
    "MR-5-1.0": ("短期均值回归", mean_rev, {"lookback": 5, "z_entry": -1.0}),
    "MR-5-2.0": ("短期均值回归", mean_rev, {"lookback": 5, "z_entry": -2.0}),
    "MR-10-1.0": ("短期均值回归", mean_rev, {"lookback": 10, "z_entry": -1.0}),
    "MR-10-2.0": ("短期均值回归", mean_rev, {"lookback": 10, "z_entry": -2.0}),
}


def target_weights(name: str, px: pd.DataFrame) -> pd.DataFrame:
    _, fn, params = VARIANTS[name]
    return fn(px, **params).fillna(0.0)
