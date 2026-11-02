import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def prices():
    """合成价格（几何随机游走），不依赖真实行情。"""
    rng = np.random.default_rng(0)
    idx = pd.date_range("2020-01-01", periods=400, freq="D")
    r = rng.normal(0.0005, 0.04, size=(400, 2))
    return pd.DataFrame(100 * np.exp(np.cumsum(r, axis=0)), index=idx, columns=["BTC-USD", "ETH-USD"])
