from __future__ import annotations

from typing import Any, Iterable
import pandas as pd
import streamlit as st

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:  # pragma: no cover
    gspread = None
    Credentials = None


# Existing workbook structure is preserved; new sheets are only added when needed.
SHEET_SCHEMAS: dict[str, list[str]] = {
    "employees": ["User ID", "Password", "Employee Name", "Role", "Status"],
    "attendance": [
        "Date", "Time", "User ID", "Technician Name", "Role",
        "Attendance Status", "Latitude", "Longitude", "Distance Meter", "Selfie Saved"
    ],
    "invoices": [
        "Entry ID", "Date", "Technician Name", "User ID",
        "Invoice Number", "Job Card Number", "Registration Number", "Bike Model", "Service Type",
        "Labour Amount", "Spare Parts Count", "Spare Amount", "Oil Change Status",
        "Total Amount", "Entry Type", "Status"
    ],
    "delete_requests": [
        "Request ID", "Date", "Time", "Entry ID", "Technician Name",
        "User ID", "Reason", "Request Status", "Admin Action Date"
    ],
    "pending_invoice_requests": [
        "Request ID", "Date", "Time", "Technician Name", "User ID",
        "Invoice Number", "Job Card Number", "Registration Number", "Bike Model", "Service Type",
        "Labour Amount", "Spare Parts Count", "Spare Amount", "Oil Change Status",
        "Total Amount", "Entry Type", "Request Status", "Admin Action Date"
    ],
    "manual_invoices": [
        "Manual Bill ID", "Date", "Technician Name", "User ID",
        "Customer Name", "Mobile Number", "Registration Number", "Bike Model", "Service Type",
        "Labour Amount", "Spare Parts Count", "Oil Amount", "Other Charges", "GST %", "Grand Total",
        "PDF File", "Status"
    ],
    "settings": ["Key", "Value"],

    # New dealership sheets (created lazily)
    "customers": ["Customer ID", "Customer Name", "Mobile Number", "Address", "Created On", "Last Visit"],
    "vehicles": ["Vehicle ID", "Customer Name", "Mobile Number", "Registration Number", "Bike Model", "Chassis No", "Engine No", "Created On", "Last Visit"],
    "service_jobs": [
        "Job Card Number", "Date", "Time", "Customer Name", "Mobile Number", "Registration Number",
        "Bike Model", "Service Type", "Complaint", "Advisor Name", "Technician Name", "Status",
        "Estimate Amount", "Odometer", "Promised Date", "Closed On"
    ],
    "billing_records": [
        "Invoice Number", "Date", "Time", "Customer Name", "Mobile Number", "Registration Number",
        "Bike Model", "Job Card Number", "Spare Amount", "Oil Amount", "Labour Amount", "Other Charges",
        "GST %", "Grand Total", "Entry Type", "Status"
    ],
    "technicians": ["Technician ID", "Technician Name", "Role", "Status", "Mobile Number", "Join Date"],
}

DEFAULT_EMPTY_SHEETS = list(SHEET_SCHEMAS.keys())


def get_sheet_id() -> str:
    return str(st.secrets.get("SHEET_ID", "")).strip()


def _service_account_info() -> dict[str, Any] | None:
    try:
        info = st.secrets["gcp_service_account"]
        if isinstance(info, dict):
            return info
    except Exception:
        pass
    return None


def client():
    if gspread is None or Credentials is None:
        return None
    info = _service_account_info()
    if not info:
        return None
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return gspread.authorize(creds)
    except Exception:
        return None


def open_spreadsheet():
    sheet_id = get_sheet_id()
    cli = client()
    if not cli or not sheet_id:
        return None
    return cli.open_by_key(sheet_id)


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    try:
        out = out.loc[:, ~out.columns.duplicated()].copy()
    except Exception:
        pass
    out = out.fillna("")
    return out


def _ensure_columns(df: pd.DataFrame, columns: Iterable[str] | None) -> pd.DataFrame:
    out = _normalize_df(df)
    if columns:
        for col in columns:
            if col not in out.columns:
                out[col] = ""
        ordered = [c for c in columns if c in out.columns]
        extras = [c for c in out.columns if c not in ordered]
        out = out[ordered + extras]
    return out.fillna("")


@st.cache_data(ttl=10, show_spinner=False)
def _cached_read(sheet_id: str, sheet_name: str, columns_key: tuple[str, ...]) -> pd.DataFrame:
    ss = open_spreadsheet()
    if ss is None:
        return pd.DataFrame(columns=list(columns_key))
    try:
        try:
            ws = ss.worksheet(sheet_name)
        except Exception:
            ws = ss.add_worksheet(
                title=sheet_name,
                rows=100,
                cols=max(len(columns_key) + 5, 20),
            )
            if columns_key:
                ws.update([list(columns_key)], value_input_option="USER_ENTERED")
            return pd.DataFrame(columns=list(columns_key))
        values = ws.get_all_values()
        if not values:
            return pd.DataFrame(columns=list(columns_key))
        header = values[0]
        data = values[1:]
        df = pd.DataFrame(data, columns=header)
        return _ensure_columns(df, columns_key)
    except Exception:
        return pd.DataFrame(columns=list(columns_key))


def read_sheet(sheet_name: str, columns: list[str] | None = None, force_refresh: bool = False) -> pd.DataFrame:
    if force_refresh:
        clear_sheet_cache()
    columns_key = tuple(columns or SHEET_SCHEMAS.get(sheet_name, []))
    sheet_id = get_sheet_id()
    if not sheet_id:
        return pd.DataFrame(columns=list(columns_key))
    return _cached_read(sheet_id, sheet_name, columns_key).copy()


def ensure_sheet(sheet_name: str, columns: list[str] | None = None) -> tuple[bool, str]:
    try:
        ss = open_spreadsheet()
        if ss is None:
            return False, "Google Sheets client not available"
        schema = columns or SHEET_SCHEMAS.get(sheet_name, [])
        try:
            ws = ss.worksheet(sheet_name)
        except Exception:
            ws = ss.add_worksheet(title=sheet_name, rows=100, cols=max(len(schema) + 5, 20))
            if schema:
                ws.update([schema], value_input_option="USER_ENTERED")
            return True, "Created"
        if schema:
            values = ws.get_all_values()
            if not values:
                ws.update([schema], value_input_option="USER_ENTERED")
        return True, "Ready"
    except Exception as e:
        return False, str(e)


def write_sheet(sheet_name: str, df: pd.DataFrame, columns: list[str] | None = None) -> tuple[bool, str]:
    try:
        ss = open_spreadsheet()
        if ss is None:
            return False, "Google Sheets client not available"
        schema = columns or SHEET_SCHEMAS.get(sheet_name, list(df.columns))
        try:
            ws = ss.worksheet(sheet_name)
        except Exception:
            ws = ss.add_worksheet(title=sheet_name, rows=max(len(df) + 20, 100), cols=max(len(schema) + 5, 20))
        out = _ensure_columns(df, schema).astype(str)
        ws.clear()
        if schema:
            if len(out.index) == 0:
                ws.update([schema], value_input_option="USER_ENTERED")
            else:
                rows = [schema] + out[schema].values.tolist()
                ws.update(rows, value_input_option="USER_ENTERED")
        else:
            if len(out.index) == 0:
                ws.update([list(out.columns)], value_input_option="USER_ENTERED")
            else:
                rows = [list(out.columns)] + out.values.tolist()
                ws.update(rows, value_input_option="USER_ENTERED")
        clear_sheet_cache()
        return True, f"{sheet_name} saved"
    except Exception as e:
        return False, str(e)


def append_row(sheet_name: str, row: dict[str, Any], columns: list[str] | None = None) -> tuple[bool, str]:
    try:
        schema = columns or SHEET_SCHEMAS.get(sheet_name, list(row.keys()))
        ensure_sheet(sheet_name, schema)
        ss = open_spreadsheet()
        if ss is None:
            return False, "Google Sheets client not available"
        ws = ss.worksheet(sheet_name)
        values = [str(row.get(c, "")) for c in schema]
        ws.append_row(values, value_input_option="USER_ENTERED")
        clear_sheet_cache()
        return True, "Appended"
    except Exception as e:
        return False, str(e)


def update_sheet(sheet_name: str, df: pd.DataFrame, columns: list[str] | None = None) -> tuple[bool, str]:
    return write_sheet(sheet_name, df, columns=columns)


def delete_where(sheet_name: str, predicate) -> tuple[bool, str]:
    try:
        df = read_sheet(sheet_name)
        if df.empty:
            return True, "Empty"
        keep = df.loc[~df.apply(predicate, axis=1)].copy()
        return write_sheet(sheet_name, keep)
    except Exception as e:
        return False, str(e)


def clear_sheet_cache() -> None:
    try:
        _cached_read.clear()
    except Exception:
        pass


def safe_sheet(sheet_name: str) -> pd.DataFrame:
    return read_sheet(sheet_name, SHEET_SCHEMAS.get(sheet_name, []))
