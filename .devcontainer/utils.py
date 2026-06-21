from __future__ import annotations
import pandas as pd
import re

def clean_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return df
    try:
        return df.loc[:, ~df.columns.duplicated()].copy()
    except Exception:
        return df.copy()

def safe_columns(df: pd.DataFrame, required: list[str]) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame(columns=required)
    out = df.copy()
    for c in required:
        if c not in out.columns:
            out[c] = ""
    return out[[c for c in required if c in out.columns]]
