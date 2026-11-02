"""绩效指标与多重检验校正（Deflated Sharpe Ratio）。"""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from . import config

_N = NormalDist()
EULER_GAMMA = 0.5772156649015329


def perf(res: pd.DataFrame) -> dict:
    """res 需含 ret、turnover 列（逐日）。夏普按无风险利率 0 计算。"""
    r = res["ret"]
    years = len(r) / config.ANN
    eq = np.concatenate([[1.0], (1 + r).cumprod().to_numpy()])
    sd = r.std(ddof=1)
    return {
        "年化收益": eq[-1] ** (1 / years) - 1 if eq[-1] > 0 else -1.0,
        "累计收益": eq[-1] - 1,
        "年化波动": sd * math.sqrt(config.ANN),
        "夏普": r.mean() / sd * math.sqrt(config.ANN) if sd > 0 else float("nan"),
        "最大回撤": float((eq / np.maximum.accumulate(eq) - 1).min()),
        "年换手": res["turnover"].sum() / years,
        "平均仓位": res["exposure"].mean() if "exposure" in res else float("nan"),
        "天数": len(r),
    }


def _sr_z(sr, sr0, T, skew, kurt):
    denom = 1 - skew * sr + (kurt - 1) / 4 * sr ** 2
    return (sr - sr0) * math.sqrt(T - 1) / math.sqrt(max(denom, 1e-12))


def expected_max_sr(sr_var: float, n_trials: int) -> float:
    """在 n_trials 个夏普真值都为 0 的试验里，最大样本夏普的期望（逐期单位）。"""
    if n_trials <= 1:
        return 0.0
    return math.sqrt(sr_var) * ((1 - EULER_GAMMA) * _N.inv_cdf(1 - 1 / n_trials)
                                + EULER_GAMMA * _N.inv_cdf(1 - 1 / (n_trials * math.e)))


def deflated_sharpe(ret: pd.Series, trial_srs: list[float], n_trials: int) -> dict:
    """Bailey & López de Prado (2014) DSR。trial_srs 为各试验的逐日（非年化）夏普。

    返回 PSR（相对 0 的概率夏普）、SR0（多重检验门槛）与 DSR（真实夏普 > 0 的校正后概率）。
    """
    r = ret.to_numpy()
    T = len(r)
    sr = r.mean() / r.std(ddof=1)
    skew = float(pd.Series(r).skew())
    kurt = float(pd.Series(r).kurt()) + 3.0  # 转为非超额峰度
    sr0 = expected_max_sr(float(np.var(trial_srs, ddof=1)), n_trials)
    return {
        "逐日夏普": sr,
        "PSR": _N.cdf(_sr_z(sr, 0.0, T, skew, kurt)),
        "SR0(年化)": sr0 * math.sqrt(config.ANN),
        "DSR": _N.cdf(_sr_z(sr, sr0, T, skew, kurt)),
        "试验数N": n_trials,
        "偏度": skew,
        "峰度": kurt,
    }
