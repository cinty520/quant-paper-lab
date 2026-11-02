import numpy as np
import pandas as pd
import pytest

from qpl.metrics import deflated_sharpe, perf


def test_max_drawdown_and_total():
    res = pd.DataFrame({"ret": [0.1, -0.5, 0.2], "turnover": [1, 0, 0], "exposure": [1, 1, 1]})
    m = perf(res)
    assert m["最大回撤"] == pytest.approx(-0.5)
    assert m["累计收益"] == pytest.approx(1.1 * 0.5 * 1.2 - 1)


def test_dsr_penalises_more_trials():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.001, 0.02, 2000))
    srs = list(rng.normal(0, 0.02, 15))
    one = deflated_sharpe(r, srs, 1)
    many = deflated_sharpe(r, srs, 15)
    assert one["DSR"] == pytest.approx(one["PSR"])
    assert many["DSR"] < one["DSR"]
