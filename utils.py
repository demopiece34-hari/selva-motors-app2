from __future__ import annotations

import re
import uuid
from datetime import datetime, date, time as time_cls
from zoneinfo import ZoneInfo
from typing import Iterable

import pandas as pd

APP_TZ = ZoneInfo("Asia/Kolkata")


def now_india() -> datetime:
    return datetime.now(APP_TZ)


def today_str() -> str:
    return now_india().strftime("%Y-%m-%d")


def now_time_str() -> str:
    return now_india().strftime("%H:%M:%S")


def make_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def clean_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    try:
        return df.loc[:, ~df.columns.duplicated()].copy()
    except Exception:
        return df.copy()


def ensure_columns(df: pd.DataFrame, required: list[str]) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame(columns=required)
    out = clean_duplicate_columns(df).copy()
    for col in required:
        if col not in out.columns:
            out[col] = ""
    ordered = [c for c in required if c in out.columns]
    extras = [c for c in out.columns if c not in ordered]
    return out[ordered + extras].fillna("")


def normalize_text(value) -> str:
    return str(value).strip().lower()


def safe_str(value) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def to_float(value, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(str(value).replace(",", "").strip())
    except Exception:
        return default


def money(value) -> str:
    try:
        return f"₹{to_float(value):,.2f}"
    except Exception:
        return "₹0.00"


def date_key(value) -> str:
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    s = safe_str(value)
    return s[:10] if len(s) >= 10 else s


def month_key(value) -> str:
    s = date_key(value)
    return s[:7] if len(s) >= 7 else s


def filter_contains(df: pd.DataFrame, columns: Iterable[str], term: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=getattr(df, "columns", []))
    q = normalize_text(term)
    if not q:
        return df.copy()
    mask = pd.Series(False, index=df.index)
    for col in columns:
        if col in df.columns:
            mask = mask | df[col].astype(str).str.lower().str.contains(re.escape(q), na=False)
    return df.loc[mask].copy()


def unique_non_empty(values) -> list[str]:
    out: list[str] = []
    for v in values:
        s = safe_str(v)
        if s and s not in out:
            out.append(s)
    return out


def row_signature(row: pd.Series, cols: list[str]) -> tuple:
    return tuple(safe_str(row.get(c, "")) for c in cols)


def detect_duplicates(df: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=df.columns if df is not None else [])
    key_cols = [c for c in key_cols if c in df.columns]
    if not key_cols:
        return df.iloc[0:0].copy()
    duplicated = df.duplicated(subset=key_cols, keep=False)
    return df.loc[duplicated].copy()


def group_metric(df: pd.DataFrame, group_col: str, value_col: str | None = None) -> pd.DataFrame:
    if df is None or df.empty or group_col not in df.columns:
        return pd.DataFrame(columns=[group_col, "Count"])
    if value_col and value_col in df.columns:
        out = df.groupby(group_col, dropna=False)[value_col].sum().reset_index()
        out.columns = [group_col, value_col]
        return out.sort_values(value_col, ascending=False)
    return df.groupby(group_col, dropna=False).size().reset_index(name="Count").sort_values("Count", ascending=False)


def haversine_meters(lat1, lon1, lat2, lon2) -> float:
    from math import radians, sin, cos, sqrt, atan2
    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    except Exception:
        return 0.0
    r = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * atan2(sqrt(a), sqrt(1 - a))


def extract_number(text: str, default: float = 0.0) -> float:
    try:
        m = re.search(r"(-?\d+(?:\.\d+)?)", safe_str(text).replace(",", ""))
        return float(m.group(1)) if m else default
    except Exception:
        return default


def compute_grand_total(spare=0, oil=0, labour=0, other=0, gst_percent=0) -> dict[str, float]:
    spare_f = to_float(spare)
    oil_f = to_float(oil)
    labour_f = to_float(labour)
    other_f = to_float(other)
    subtotal = spare_f + oil_f + labour_f + other_f
    gst_f = subtotal * (to_float(gst_percent) / 100.0)
    grand = subtotal + gst_f
    return {
        "spare": spare_f,
        "oil": oil_f,
        "labour": labour_f,
        "other": other_f,
        "subtotal": subtotal,
        "gst": gst_f,
        "grand_total": grand,
    }
