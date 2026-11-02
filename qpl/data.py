"""行情数据：只调用 Coinbase Exchange 公开 K 线接口（无需账号、无需密钥），本地缓存。

接口：GET /products/{product}/candles?granularity=&start=&end=
返回 [time, low, high, open, close, volume]，每次最多 300 根。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from . import config

GRAN = {"1d": 86400, "1h": 3600}
FIRST = {"BTC-USD": "2015-07-20", "ETH-USD": "2016-05-18"}
COLS = ["time", "low", "high", "open", "close", "volume"]


def _get(url: str, params: dict, retries: int = 6) -> list:
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=30,
                             headers={"User-Agent": "quant-paper-lab (public market data, paper trading only)"})
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** i)
                continue
            r.raise_for_status()
        except requests.RequestException:
            if i == retries - 1:
                raise
            time.sleep(2 ** i)
    raise RuntimeError(f"请求失败: {url} {params}")


def fetch_candles(product: str, interval: str, start: datetime, end: datetime) -> pd.DataFrame:
    """抓取 [start, end) 区间的 K 线，自动分页。"""
    g = GRAN[interval]
    step = timedelta(seconds=g * 300)
    rows, cur = [], start
    url = f"{config.COINBASE_API}/products/{product}/candles"
    while cur < end:
        nxt = min(cur + step, end)
        # Coinbase 的 end 是包含的，减 1 秒避免与下一页重复
        rows += _get(url, {"granularity": g, "start": cur.isoformat(),
                           "end": (nxt - timedelta(seconds=1)).isoformat()})
        cur = nxt
        time.sleep(0.15)  # 公开接口限速约每秒 10 次，这里留足余量
    df = pd.DataFrame(rows, columns=COLS)
    if df.empty:
        return df
    df = df.drop_duplicates("time").sort_values("time")
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df[["time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


def cache_path(product: str, interval: str):
    return config.DATA_DIR / (f"{product}_{interval}.csv" + (".gz" if interval == "1h" else ""))


def update_cache(product: str, interval: str, now: datetime | None = None) -> pd.DataFrame:
    """增量更新本地缓存，只保留已收盘的 K 线，并写入来源和抓取时间。"""
    now = now or datetime.now(timezone.utc)
    g = timedelta(seconds=GRAN[interval])
    path = cache_path(product, interval)
    path.parent.mkdir(parents=True, exist_ok=True)
    old = pd.read_csv(path, parse_dates=["time"]) if path.exists() else pd.DataFrame(columns=COLS)
    if len(old):
        start = old["time"].max().to_pydatetime() - 2 * g  # 回补两根以覆盖修订
    else:
        start = datetime.fromisoformat(FIRST[product]).replace(tzinfo=timezone.utc)
    new = fetch_candles(product, interval, start, now)
    df = pd.concat([old, new]) if len(old) else new
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.drop_duplicates("time", keep="last").sort_values("time")
    df = df[df["time"] + g <= now]  # 丢弃未收盘的 K 线
    df.to_csv(path, index=False)
    _write_meta(product, interval, df, now)
    return df


def _write_meta(product, interval, df, now):
    meta_path = config.DATA_DIR / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    meta[f"{product}_{interval}"] = {
        "source": f"{config.COINBASE_API}/products/{product}/candles?granularity={GRAN[interval]}",
        "fetched_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows": int(len(df)),
        "first_bar": str(df["time"].min()),
        "last_bar": str(df["time"].max()),
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")


def load_daily_close(end: str | None = None) -> pd.DataFrame:
    """日线收盘价（列=产品，索引=UTC 日期）。缺失日用前值填充（当日收益记为 0）。"""
    closes = {}
    for p in config.PRODUCTS:
        df = pd.read_csv(cache_path(p, "1d"), parse_dates=["time"])
        s = df.set_index(df["time"].dt.tz_convert(None).dt.normalize())["close"]
        closes[p] = s
    px = pd.DataFrame(closes).sort_index()
    px = px.reindex(pd.date_range(px.index.min(), px.index.max(), freq="D")).ffill()
    if end is not None:
        px = px.loc[:end]
    return px


def load_dev_close() -> pd.DataFrame:
    """开发阶段唯一允许使用的数据入口：严格截断在留出期之前。"""
    px = load_daily_close(end=(pd.Timestamp(config.HOLDOUT_START) - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    assert px.index.max() < pd.Timestamp(config.HOLDOUT_START)
    return px
