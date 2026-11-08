from __future__ import annotations
import pandas as pd
import streamlit as st

def get_sheet_id() -> str:
    return str(st.secrets.get("SHEET_ID", "")).strip()

def client():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception:
        return None

def read_sheet(spreadsheet_id: str, sheet_name: str, columns=None) -> pd.DataFrame:
    cli = client()
    if cli is None or not spreadsheet_id:
        return pd.DataFrame(columns=columns or [])
    ss = cli.open_by_key(spreadsheet_id)
    try:
        ws = ss.worksheet(sheet_name)
    except Exception:
        ws = ss.add_worksheet(title=sheet_name, rows=100, cols=max(len(columns or []) + 5, 20))
        if columns:
            ws.update([columns], value_input_option="USER_ENTERED")
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame(columns=columns or [])
    df = pd.DataFrame(values[1:], columns=values[0])
    if columns:
        for c in columns:
            if c not in df.columns:
                df[c] = ""
        df = df[[c for c in columns if c in df.columns]]
    return df.fillna("")

def write_sheet(spreadsheet_id: str, sheet_name: str, df: pd.DataFrame, columns=None) -> tuple[bool, str]:
    try:
        cli = client()
        if cli is None or not spreadsheet_id:
            return False, "Google client not available"
        ss = cli.open_by_key(spreadsheet_id)
        try:
            ws = ss.worksheet(sheet_name)
        except Exception:
            ws = ss.add_worksheet(title=sheet_name, rows=max(len(df) + 20, 100), cols=max(len(columns or []) + 5, 20))
        ws.clear()
        out = df.copy().fillna("").astype(str)
        if columns:
            for c in columns:
                if c not in out.columns:
                    out[c] = ""
            out = out[[c for c in columns if c in out.columns]]
        values = [out.columns.tolist()] + out.values.tolist()
        if values:
            ws.update(values, value_input_option="USER_ENTERED")
        return True, "Saved"
    except Exception as e:
        return False, str(e)
