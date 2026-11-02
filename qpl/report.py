"""把结果表格化为 Markdown。"""
from __future__ import annotations

import math

PCT = {"年化收益", "累计收益", "年化波动", "最大回撤", "平均仓位", "PSR", "DSR"}
DEC = {"夏普": 2, "年换手": 1, "SR0(年化)": 2}


def fmt(col: str, v) -> str:
    if isinstance(v, str):
        return v
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    if col in PCT:
        return f"{v:.1%}"
    if col in DEC:
        return f"{v:.{DEC[col]}f}"
    if isinstance(v, float):
        return f"{v:.3g}"
    return str(v)


def md_table(rows: dict, cols: list[str], key: str = "名称") -> str:
    out = [f"| {key} | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for name, m in rows.items():
        out.append(f"| {name} | " + " | ".join(fmt(c, m.get(c)) for c in cols) + " |")
    return "\n".join(out)
