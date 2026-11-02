"""抓取/增量更新 BTC-USD、ETH-USD 的日线与小时线到 data/coinbase/。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qpl import config, data  # noqa: E402

if __name__ == "__main__":
    intervals = sys.argv[1:] or ["1d", "1h"]
    for p in config.PRODUCTS:
        for iv in intervals:
            df = data.update_cache(p, iv)
            print(f"{p} {iv}: {len(df)} 根, {df['time'].min()} → {df['time'].max()}")
