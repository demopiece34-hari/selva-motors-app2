
import re
import io
import uuid
import math
import zipfile
import json
from pathlib import Path
from datetime import datetime, time

import streamlit as st
import pandas as pd

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None
from PIL import Image
import qrcode

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas

try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from streamlit_js_eval import get_geolocation
except Exception:
    get_geolocation = None


# ============================================================
# SELVA MOTORS EXCEL STORAGE APP
# Excel only. No MySQL. No SQLAlchemy. No SQL database.
# ============================================================

st.set_page_config(
    page_title="Selva Motors Excel Storage App",
    page_icon="🏍️",
    layout="wide"
)

APP_TITLE = "SELVA MOTORS EXCEL STORAGE APP"
VERSION_TEXT = "Excel Storage Version"
SECRET_PASSWORD = "hari121"

DATA_DIR = Path("data")
UPLOAD_DIR = Path("uploads")
PDF_DIR = Path("generated_reports")
BACKUP_DIR = Path("backups")

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

EXCEL_FILE = DATA_DIR / "selva_motors_excel_storage.xlsx"
SYNC_STATE_FILE = DATA_DIR / "google_sync_state.json"

COMPANY_LAT = 10.759710
COMPANY_LON = 79.742772
ALLOWED_RADIUS_METER = 400


# ============================================================
# STYLE
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');

:root {
    --hero-dark: #070b13;
    --hero-navy: #0f172a;
    --hero-green: #22c55e;
    --hero-blue: #2563eb;
    --hero-red: #ef4444;
    --hero-gold: #f59e0b;
    --hero-card: rgba(255,255,255,.88);
    --hero-border: rgba(226,232,240,.85);
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at 3% 0%, rgba(34,197,94,.18), transparent 26%),
        radial-gradient(circle at 98% 3%, rgba(37,99,235,.16), transparent 28%),
        radial-gradient(circle at 70% 100%, rgba(245,158,11,.12), transparent 30%),
        linear-gradient(135deg, #f8fafc 0%, #eef2ff 48%, #f0fdf4 100%);
}

.block-container {
    padding-top: 1.05rem;
    padding-bottom: 2rem;
    max-width: 1420px;
}

[data-testid="stSidebar"] {
    background:
        linear-gradient(180deg, rgba(2,6,23,.98), rgba(15,23,42,.99) 58%, rgba(5,46,22,.98)),
        radial-gradient(circle at 50% 0%, rgba(34,197,94,.22), transparent 36%);
    border-right: 1px solid rgba(255,255,255,.08);
}

[data-testid="stSidebar"] * {
    color: #e5e7eb;
}

[data-testid="stSidebar"] .stRadio label {
    background: rgba(255,255,255,.04);
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 15px;
    margin: 6px 0;
    padding: 7px 8px;
    transition: all .18s ease;
}

[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(34,197,94,.18);
    border-color: rgba(34,197,94,.38);
    transform: translateX(3px);
}

[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
textarea {
    border-radius: 14px !important;
    border: 1px solid #cbd5e1 !important;
}

.app-title {
    font-size: 34px;
    font-weight: 900;
    letter-spacing: -.8px;
    color: #0f172a;
    margin-bottom: 2px;
}

.subtle {
    color: #64748b;
    font-size: 14px;
    margin-bottom: 12px;
}

.login-wrap {
    min-height: 77vh;
    display:flex;
    align-items:center;
    justify-content:center;
}

.login-hero {
    max-width: 620px;
    width: 100%;
    padding: 36px;
    border-radius: 32px;
    background:
        linear-gradient(145deg, rgba(255,255,255,.94), rgba(255,255,255,.78)),
        radial-gradient(circle at 0% 0%, rgba(34,197,94,.24), transparent 40%);
    box-shadow: 0 30px 80px rgba(15,23,42,.22);
    border: 1px solid rgba(255,255,255,.8);
    backdrop-filter: blur(18px);
    position: relative;
    overflow: hidden;
}

.login-hero:before {
    content:"";
    position:absolute;
    width:210px;
    height:210px;
    border-radius:50%;
    background:rgba(34,197,94,.16);
    right:-70px;
    top:-80px;
}

.brand-row {
    display:flex;
    align-items:center;
    gap:12px;
    margin-bottom: 12px;
}

.brand-logo {
    height:58px;
    width:58px;
    border-radius:20px;
    display:grid;
    place-items:center;
    background: linear-gradient(135deg, #111827, #16a34a);
    color:white;
    font-size:28px;
    box-shadow:0 16px 30px rgba(22,163,74,.28);
}

.brand-text h1 {
    margin:0;
    font-size:31px;
    font-weight:900;
    letter-spacing:-.7px;
    color:#0f172a;
}

.brand-text p {
    margin:0;
    color:#16a34a;
    font-weight:900;
    letter-spacing:3px;
    font-size:12px;
}

.feature-strip {
    display:flex;
    flex-wrap:wrap;
    gap:8px;
    margin: 14px 0 4px 0;
}

.feature-pill {
    padding: 7px 10px;
    border-radius: 999px;
    background:#ecfdf5;
    color:#166534;
    border:1px solid #bbf7d0;
    font-weight:800;
    font-size:12px;
}

.hero-panel {
    position:relative;
    overflow:hidden;
    padding: 24px;
    border-radius: 28px;
    background:
        radial-gradient(circle at 100% 0%, rgba(34,197,94,.28), transparent 34%),
        linear-gradient(135deg, #020617 0%, #0f172a 58%, #052e16 130%);
    color: white;
    box-shadow: 0 22px 54px rgba(2,6,23,.22);
    border: 1px solid rgba(255,255,255,.10);
    margin-bottom: 20px;
}

.hero-panel:after {
    content:"🏍️";
    position:absolute;
    right:24px;
    bottom:12px;
    font-size:74px;
    opacity:.10;
}

.hero-panel h1 {
    margin: 0;
    font-size: 31px;
    font-weight: 900;
    letter-spacing: -.7px;
}

.hero-panel p {
    margin: 7px 0 0 0;
    color: #cbd5e1;
}

.status-chip {
    display: inline-flex;
    align-items:center;
    gap:6px;
    padding: 6px 11px;
    border-radius: 999px;
    font-weight: 900;
    font-size: 12px;
    background: rgba(34,197,94,.16);
    color: #bbf7d0;
    border: 1px solid rgba(187,247,208,.25);
    margin-bottom: 10px;
}

.glow-card {
    background: rgba(255,255,255,.92);
    border: 1px solid var(--hero-border);
    border-radius: 24px;
    padding: 20px;
    box-shadow: 0 17px 42px rgba(15,23,42,.09);
    transition: transform .16s ease, box-shadow .16s ease;
}

.glow-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 24px 58px rgba(15,23,42,.13);
}

.metric-card {
    position: relative;
    overflow: hidden;
    min-height: 132px;
    border-radius: 26px;
    padding: 21px;
    color: white;
    background:
        radial-gradient(circle at 100% 0%, rgba(255,255,255,.18), transparent 30%),
        linear-gradient(135deg, #111827 0%, #1e293b 58%, #16a34a 145%);
    box-shadow: 0 20px 50px rgba(15,23,42,.20);
    border: 1px solid rgba(255,255,255,.13);
}

.metric-card:before {
    content: "";
    position: absolute;
    width: 135px;
    height: 135px;
    right: -46px;
    top: -48px;
    background: rgba(255,255,255,.12);
    border-radius: 999px;
}

.metric-card p {
    margin: 0;
    color: #dbeafe;
    font-size: 13px;
    font-weight: 800;
}

.metric-card h2 {
    margin: 8px 0 0 0;
    font-size: 31px;
    font-weight: 900;
    letter-spacing: -.6px;
}

.metric-card small {
    color: #bbf7d0;
    font-weight: 800;
}

.quick-card {
    padding:18px;
    border-radius:22px;
    background: linear-gradient(135deg, rgba(255,255,255,.95), rgba(240,253,244,.92));
    border:1px solid rgba(187,247,208,.7);
    box-shadow:0 14px 34px rgba(15,23,42,.08);
}

.quick-card h3 {
    margin:0;
    font-size:17px;
    color:#0f172a;
    font-weight:900;
}

.quick-card p {
    color:#64748b;
    margin:6px 0 0 0;
    font-size:13px;
}

.section-title {
    font-size: 20px;
    font-weight: 900;
    color: #0f172a;
    margin: 10px 0 11px 0;
    letter-spacing:-.2px;
}

.bill-preview {
    border-radius:26px;
    background:#fff;
    border:1px solid #e2e8f0;
    padding:22px;
    box-shadow:0 18px 44px rgba(15,23,42,.10);
    position:relative;
    overflow:hidden;
}

.bill-preview:before {
    content:"";
    height:7px;
    background:linear-gradient(90deg,#111827,#16a34a,#ef4444);
    position:absolute;
    top:0;
    left:0;
    right:0;
}

.bill-preview h2 {
    margin:8px 0 3px 0;
    font-weight:900;
    color:#0f172a;
}

.preview-grid {
    display:grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap:12px;
}

.preview-item {
    padding:13px;
    border-radius:17px;
    background:#f8fafc;
    border:1px solid #e2e8f0;
}

.preview-item b {
    display:block;
    color:#64748b;
    font-size:12px;
}

.preview-item span {
    display:block;
    color:#0f172a;
    font-weight:900;
    margin-top:4px;
}

.approve-box {
    border-radius:20px;
    background:#fff;
    padding:16px;
    border:1px solid #fee2e2;
    box-shadow:0 12px 28px rgba(239,68,68,.08);
    margin-bottom:12px;
}

.stButton>button {
    border-radius: 15px !important;
    font-weight: 900 !important;
    border: 0 !important;
    background: linear-gradient(135deg, #16a34a, #2563eb) !important;
    color: white !important;
    box-shadow: 0 12px 28px rgba(37,99,235,.19);
}

.stDownloadButton>button {
    border-radius: 15px !important;
    font-weight: 900 !important;
    border: 0 !important;
    background: linear-gradient(135deg, #0f172a, #16a34a) !important;
    color: white !important;
}

[data-testid="stDataFrame"] {
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 11px 30px rgba(15,23,42,.08);
}

[data-testid="stMetric"] {
    background: rgba(255,255,255,.88);
    padding:16px;
    border-radius:18px;
    border:1px solid #e2e8f0;
    box-shadow:0 10px 28px rgba(15,23,42,.07);
}

hr {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent, #cbd5e1, transparent);
    margin: 24px 0;
}

@media (max-width: 768px) {
    .preview-grid { grid-template-columns: repeat(1, minmax(0, 1fr)); }
    .hero-panel h1 { font-size: 24px; }
    .metric-card h2 { font-size: 25px; }
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# EXCEL STORAGE STRUCTURE
# ============================================================
SHEETS = {
    "employees": [
        "User ID", "Password", "Employee Name", "Role", "Status"
    ],
    "attendance": [
        "Date", "Time", "User ID", "Technician Name", "Role",
        "Attendance Status", "Latitude", "Longitude", "Distance Meter",
        "Selfie Saved"
    ],
    "invoices": [
        "Entry ID", "Date", "Technician Name", "User ID",
        "Invoice Number", "Registration Number", "Bike Model",
        "Labour Amount", "Spare Parts Count", "Oil Count", "Oil Details",
        "Total Amount", "Entry Type", "Status"
    ],
    "delete_requests": [
        "Request ID", "Date", "Time", "Entry ID", "Technician Name",
        "User ID", "Reason", "Request Status", "Admin Action Date"
    ],
    "manual_invoices": [
        "Manual Bill ID", "Date", "Technician Name", "User ID",
        "Customer Name", "Registration Number", "Bike Model",
        "Labour Amount", "Spare Parts Count", "Oil Count",
        "Total Amount", "PDF File", "Status"
    ],
    "settings": [
        "Key", "Value"
    ],
}

DEFAULT_EMPLOYEES = [
    ["admin", "admin123", "Admin", "Admin", "Active"],
    ["manager", "manager123", "Manager", "Manager", "Active"],
    ["mohan", "mohan", "Mohan", "Technician", "Active"],
    ["ajay", "ajay", "Ajay", "Technician", "Active"],
    ["vengadesh", "vengadesh", "Vengadesh", "Technician", "Active"],
    ["prathisha", "prathisha", "Prathisha", "Prathisha / System Staff", "Active"],
]


def today_str():
    return datetime.now().strftime("%d-%m-%Y")


def time_str():
    return datetime.now().strftime("%I:%M:%S %p")


def now_stamp():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def create_excel_if_missing():
    if EXCEL_FILE.exists():
        return

    with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl") as writer:
        for sheet, cols in SHEETS.items():
            df = pd.DataFrame(columns=cols)

            if sheet == "employees":
                df = pd.DataFrame(DEFAULT_EMPLOYEES, columns=cols)

            if sheet == "settings":
                df = pd.DataFrame([
                    ["Storage Type", "Excel Only"],
                    ["Version", VERSION_TEXT],
                    ["Excel File Path", str(EXCEL_FILE)],
                    ["Company Latitude", str(COMPANY_LAT)],
                    ["Company Longitude", str(COMPANY_LON)],
                    ["Allowed Radius Meter", str(ALLOWED_RADIUS_METER)],
                ], columns=cols)

            df.to_excel(writer, sheet_name=sheet, index=False)


def read_sheet(sheet_name):
    create_excel_if_missing()
    try:
        df = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        df = pd.DataFrame(columns=SHEETS[sheet_name])

    for col in SHEETS[sheet_name]:
        if col not in df.columns:
            df[col] = ""

    return df[SHEETS[sheet_name]].fillna("")


def write_sheet(sheet_name, df):
    create_excel_if_missing()

    all_sheets = {}
    for name in SHEETS:
        if name == sheet_name:
            temp = df.copy()
            for col in SHEETS[name]:
                if col not in temp.columns:
                    temp[col] = ""
            all_sheets[name] = temp[SHEETS[name]]
        else:
            all_sheets[name] = read_sheet(name)

    with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl", mode="w") as writer:
        for name, data in all_sheets.items():
            data.to_excel(writer, sheet_name=name, index=False)

    # Fast mode:
    # Save to Excel now, mark changed sheet for Google Sheet sync after 30 minutes.
    try:
        if "mark_sheet_dirty" in globals():
            mark_sheet_dirty(sheet_name)
    except Exception:
        pass


def append_row(sheet_name, row_dict):
    df = read_sheet(sheet_name)
    clean_row = {col: row_dict.get(col, "") for col in SHEETS[sheet_name]}
    df = pd.concat([df, pd.DataFrame([clean_row])], ignore_index=True)
    write_sheet(sheet_name, df)


create_excel_if_missing()



# ============================================================
# GOOGLE SHEET BACKUP SYNC
# Primary storage is still Excel. Google Sheet is only backup/sync.
# ============================================================
def google_sheet_client():
    if gspread is None or Credentials is None:
        return None, "gspread/google-auth not installed. Add gspread and google-auth in requirements.txt"

    try:
        if "gcp_service_account" not in st.secrets:
            return None, "Streamlit secrets missing: gcp_service_account"

        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scope
        )
        client = gspread.authorize(creds)
        return client, ""
    except Exception as e:
        return None, str(e)


def get_or_create_worksheet(spreadsheet, sheet_name, rows=1000, cols=30):
    try:
        return spreadsheet.worksheet(sheet_name)
    except Exception:
        return spreadsheet.add_worksheet(title=sheet_name, rows=rows, cols=cols)


def dataframe_to_sheet_values(df):
    clean_df = df.copy().fillna("")
    clean_df = clean_df.astype(str)
    return [clean_df.columns.tolist()] + clean_df.values.tolist()



def is_google_auto_sync_enabled():
    """
    Google Sheet auto store will work only when Streamlit secrets are configured.
    Excel remains primary storage, Google Sheet is automatic cloud copy.
    """
    return bool(st.secrets.get("SHEET_ID", "")) and ("gcp_service_account" in st.secrets)


def sync_single_excel_sheet_to_google_sheet(sheet_name):
    """
    Sync only the changed Excel sheet to Google Sheet immediately after saving.
    This is faster than syncing all sheets after every entry.
    """
    if not is_google_auto_sync_enabled():
        return False, "Google Sheet secrets not configured"

    try:
        sheet_id = st.secrets.get("SHEET_ID", "")
        client, err = google_sheet_client()
        if client is None:
            return False, err

        spreadsheet = client.open_by_key(sheet_id)
        df = read_sheet(sheet_name)

        ws = get_or_create_worksheet(
            spreadsheet,
            sheet_name,
            rows=max(len(df) + 20, 100),
            cols=max(len(df.columns) + 5, 20)
        )

        ws.clear()
        values = dataframe_to_sheet_values(df)
        if values:
            ws.update(values)

        return True, f"{sheet_name} synced to Google Sheet"
    except Exception as e:
        return False, str(e)




def load_sync_state():
    try:
        if SYNC_STATE_FILE.exists():
            return json.loads(SYNC_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass

    return {
        "dirty_sheets": [],
        "last_sync_ts": 0,
        "last_sync_time": "Not yet",
        "last_sync_status": "Not yet",
        "last_sync_message": "",
        "last_change_time": "Not yet"
    }


def save_sync_state(state):
    try:
        SYNC_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


def mark_sheet_dirty(sheet_name):
    state = load_sync_state()
    dirty = set(state.get("dirty_sheets", []))
    dirty.add(sheet_name)
    state["dirty_sheets"] = sorted(list(dirty))
    state["last_change_time"] = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
    save_sync_state(state)


def sync_dirty_sheets_to_google_sheet():
    state = load_sync_state()
    dirty_sheets = state.get("dirty_sheets", [])

    if not dirty_sheets:
        return True, "No changed sheets to sync."

    if not is_google_auto_sync_enabled():
        return False, "Google Sheet secrets not configured."

    synced = []
    failed = []

    for sheet_name in dirty_sheets:
        ok, msg = sync_single_excel_sheet_to_google_sheet(sheet_name)
        if ok:
            synced.append(sheet_name)
        else:
            failed.append(f"{sheet_name}: {msg}")

    now = datetime.now()

    if failed:
        state["last_sync_status"] = "Failed"
        state["last_sync_message"] = "; ".join(failed)[:500]
        state["last_sync_time"] = now.strftime("%d-%m-%Y %I:%M:%S %p")
        save_sync_state(state)
        return False, state["last_sync_message"]

    state["dirty_sheets"] = []
    state["last_sync_ts"] = now.timestamp()
    state["last_sync_time"] = now.strftime("%d-%m-%Y %I:%M:%S %p")
    state["last_sync_status"] = "Success"
    state["last_sync_message"] = "Synced sheets: " + ", ".join(synced)
    save_sync_state(state)

    return True, state["last_sync_message"]



def get_next_sync_wait_text():
    """
    Returns readable waiting time for next 30-minute Google Sheet sync.
    """
    try:
        state = load_sync_state()
        dirty_sheets = state.get("dirty_sheets", [])

        if not dirty_sheets:
            return "No pending sync"

        last_sync_ts = float(state.get("last_sync_ts", 0) or 0)
        now_ts = datetime.now().timestamp()
        interval = 30 * 60

        if last_sync_ts == 0:
            return "Ready to sync now"

        remaining = int(interval - (now_ts - last_sync_ts))

        if remaining <= 0:
            return "Ready to sync now"

        minutes = remaining // 60
        seconds = remaining % 60
        return f"{minutes} min {seconds} sec remaining"

    except Exception:
        return "Waiting time not available"


def get_sync_status_badge_text():
    state = load_sync_state()
    dirty_sheets = state.get("dirty_sheets", [])
    status = state.get("last_sync_status", "Not yet")

    if dirty_sheets:
        return "Waiting for Google Sheet update"

    if status == "Success":
        return "Updated to Google Sheet"

    return status


def auto_sync_google_sheet_30min():
    """
    Excel save is instant and fast.
    Google Sheet sync runs only once every 30 minutes when app opens/reruns.
    """
    try:
        state = load_sync_state()
        dirty_sheets = state.get("dirty_sheets", [])

        if not dirty_sheets:
            return

        now_ts = datetime.now().timestamp()
        last_sync_ts = float(state.get("last_sync_ts", 0) or 0)
        thirty_minutes = 30 * 60

        if now_ts - last_sync_ts < thirty_minutes:
            return

        sync_dirty_sheets_to_google_sheet()

    except Exception:
        pass



def sync_excel_to_google_sheet():
    """
    Copies all local Excel sheets to Google Sheet.
    This does not replace Excel storage. It is only a manual cloud backup.
    """
    if not EXCEL_FILE.exists():
        return False, "Excel file not found. Save some data first."

    sheet_id = st.secrets.get("SHEET_ID", "")
    if not sheet_id:
        return False, "Streamlit secrets missing: SHEET_ID"

    client, err = google_sheet_client()
    if client is None:
        return False, err

    try:
        spreadsheet = client.open_by_key(sheet_id)

        synced = []
        for sheet_name in SHEETS.keys():
            df = read_sheet(sheet_name)
            ws = get_or_create_worksheet(
                spreadsheet,
                sheet_name,
                rows=max(len(df) + 20, 100),
                cols=max(len(df.columns) + 5, 20)
            )

            ws.clear()
            values = dataframe_to_sheet_values(df)
            if values:
                ws.update(values)

            synced.append(f"{sheet_name} ({len(df)} rows)")

        return True, "Synced to Google Sheet: " + ", ".join(synced)

    except Exception as e:
        return False, str(e)




# ============================================================
# AUTO BACKUP CHECK - 10 PM
# Note: Streamlit cannot run a true background job by itself.
# This check runs whenever app opens/reruns after 10 PM.
# It syncs only once per date.
# ============================================================
def get_setting_value(key, default=""):
    try:
        df = read_sheet("settings")
        match = df[df["Key"].astype(str) == str(key)]
        if match.empty:
            return default
        return str(match.iloc[0]["Value"])
    except Exception:
        return default


def set_setting_value(key, value):
    df = read_sheet("settings")
    if (df["Key"].astype(str) == str(key)).any():
        idx = df[df["Key"].astype(str) == str(key)].index[0]
        df.loc[idx, "Value"] = str(value)
        write_sheet("settings", df)
    else:
        append_row("settings", {
            "Key": key,
            "Value": str(value)
        })


def auto_backup_check_10pm():
    """
    Auto sync Excel data to Google Sheet once per day after 10:00 PM.
    Works when the Streamlit app is opened or rerun after 10 PM.
    """
    try:
        now = datetime.now()
        today_key = now.strftime("%d-%m-%Y")
        current_minutes = now.hour * 60 + now.minute
        backup_minutes = 22 * 60  # 10:00 PM

        if current_minutes < backup_minutes:
            return

        last_backup_date = get_setting_value("Last Auto Backup Date", "")

        if last_backup_date == today_key:
            return

        ok, msg = sync_excel_to_google_sheet()

        if ok:
            set_setting_value("Last Auto Backup Date", today_key)
            set_setting_value("Last Auto Backup Time", now.strftime("%I:%M:%S %p"))
            set_setting_value("Last Auto Backup Status", "Success")
            set_setting_value("Last Auto Backup Message", msg[:500])
        else:
            set_setting_value("Last Auto Backup Status", "Failed")
            set_setting_value("Last Auto Backup Message", msg[:500])

    except Exception as e:
        try:
            set_setting_value("Last Auto Backup Status", "Failed")
            set_setting_value("Last Auto Backup Message", str(e)[:500])
        except Exception:
            pass



# ============================================================
# AUTH
# ============================================================
def login_user(user_id, password):
    users = read_sheet("employees")
    users["User ID"] = users["User ID"].astype(str)
    users["Password"] = users["Password"].astype(str)
    users["Status"] = users["Status"].astype(str)

    match = users[
        (users["User ID"].str.strip() == str(user_id).strip()) &
        (users["Password"].str.strip() == str(password).strip()) &
        (users["Status"].str.lower() == "active")
    ]

    if match.empty:
        return None

    return match.iloc[0].to_dict()


def role():
    return st.session_state.get("role", "")


def is_admin():
    return role() == "Admin"


def is_manager():
    return role() == "Manager"


def is_technician():
    return role() == "Technician"


def is_prathisha():
    return role() == "Prathisha / System Staff"


# ============================================================
# CLEANING
# ============================================================
def clean_customer_name(value):
    text = str(value or "").strip()
    text = re.sub(r"Invoice\s*(No|Number)?\s*[:\-]?\s*[A-Z0-9\-\/]+", "", text, flags=re.I)
    text = re.sub(r"Bill\s*(No|Number)?\s*[:\-]?\s*[A-Z0-9\-\/]+", "", text, flags=re.I)
    text = re.sub(r"\b[A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4}\b", "", text, flags=re.I)
    text = re.sub(r"\b[6-9]\d{9}\b", "", text)
    text = re.sub(r"\s+", " ", text).strip(" :-|")
    return text


def clean_bike_model(value):
    text = str(value or "").strip()
    text = re.sub(r"\bVIN\s*[:\-]?\s*[A-Z0-9]{8,30}\b", "", text, flags=re.I)
    text = re.sub(r"\bMBL[A-Z0-9]{8,30}\b", "", text, flags=re.I)
    text = re.sub(r"\b[6-9]\d{9}\b", "", text)
    text = re.sub(r"\s+", " ", text).strip(" :-|")
    return text


def clean_reg_no(value):
    text = str(value or "").upper().replace(" ", "")
    text = re.sub(r"[^A-Z0-9]", "", text)
    return text


def to_float(value):
    text = str(value or "").replace(",", "")
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    return float(nums[0]) if nums else 0.0


def find_one(patterns, text, default=""):
    for pat in patterns:
        m = re.search(pat, text, flags=re.I | re.M)
        if m:
            return str(m.group(1)).strip()
    return default


# ============================================================
# GPS
# ============================================================
def distance_meter(lat1, lon1, lat2, lon2):
    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    except Exception:
        return 999999.0

    radius = 6371000
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)



def bearing_to_company(user_lat, user_lon, company_lat=COMPANY_LAT, company_lon=COMPANY_LON):
    try:
        lat1 = math.radians(float(user_lat))
        lat2 = math.radians(float(company_lat))
        diff_lon = math.radians(float(company_lon) - float(user_lon))

        x = math.sin(diff_lon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(diff_lon)
        bearing = (math.degrees(math.atan2(x, y)) + 360) % 360
        return bearing
    except Exception:
        return None


def compass_direction(bearing):
    if bearing is None:
        return "Unknown"
    dirs = [
        "North", "North-East", "East", "South-East",
        "South", "South-West", "West", "North-West"
    ]
    idx = round(bearing / 45) % 8
    return dirs[idx]


def direction_hint(direction):
    hints = {
        "North": "Move straight towards North side.",
        "North-East": "Move towards right-front / North-East side.",
        "East": "Move towards right side / East side.",
        "South-East": "Move towards right-back / South-East side.",
        "South": "Move towards South side.",
        "South-West": "Move towards left-back / South-West side.",
        "West": "Move towards left side / West side.",
        "North-West": "Move towards left-front / North-West side.",
        "Unknown": "Direction not detected."
    }
    return hints.get(direction, "Direction not detected.")


def extract_gps_from_browser_location(loc):
    try:
        if not loc:
            return None, None, None

        coords = loc.get("coords", loc)
        lat = coords.get("latitude")
        lon = coords.get("longitude")
        accuracy = coords.get("accuracy", "")

        if lat is None or lon is None:
            return None, None, None

        return float(lat), float(lon), accuracy
    except Exception:
        return None, None, None


def auto_save_attendance_from_gps(lat, lon):
    user_id = st.session_state["user_id"]
    name = st.session_state["employee_name"]
    user_role = st.session_state["role"]

    dist = distance_meter(lat, lon, COMPANY_LAT, COMPANY_LON)

    if dist > ALLOWED_RADIUS_METER:
        return False, dist

    append_row("attendance", {
        "Date": today_str(),
        "Time": time_str(),
        "User ID": user_id,
        "Technician Name": name,
        "Role": user_role,
        "Attendance Status": "Present",
        "Latitude": lat,
        "Longitude": lon,
        "Distance Meter": dist,
        "Selfie Saved": "No"
    })

    return True, dist



def save_uploaded_file(uploaded_file, folder=UPLOAD_DIR):
    if uploaded_file is None:
        return ""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", uploaded_file.name)
    path = folder / f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe}"
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(path)


# ============================================================
# OCR
# ============================================================
def extract_text_from_pdf(file_path):
    text = ""

    if pdfplumber is not None:
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text += (page.extract_text() or "") + "\n"
        except Exception:
            pass

    if not text.strip() and PyPDF2 is not None:
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += (page.extract_text() or "") + "\n"
        except Exception:
            pass

    return text.strip()


def extract_text_from_image(file_path):
    if pytesseract is None:
        return ""
    try:
        image = Image.open(file_path)
        return pytesseract.image_to_string(image).strip()
    except Exception:
        return ""


def extract_invoice_text(file_path):
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
        return extract_text_from_image(file_path)
    return ""


def get_section(text, start_keywords, end_keywords):
    if not text:
        return ""

    lower_text = text.lower()
    start = -1

    for key in start_keywords:
        pos = lower_text.find(key.lower())
        if pos != -1:
            start = pos
            break

    if start == -1:
        return ""

    end = len(text)
    for key in end_keywords:
        pos = lower_text.find(key.lower(), start + 5)
        if pos != -1:
            end = min(end, pos)

    return text[start:end]


def clean_part_description(line):
    line = str(line or "").strip()
    line = re.sub(r"^\d+\s+", "", line)
    line = re.sub(r"\b[A-Z0-9]{6,}[-_]", "", line)
    line = re.sub(r"\b\d{8}\b", "", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def is_total_or_header_line(line):
    lower = str(line or "").lower().strip()
    if not lower:
        return True

    blocked_words = [
        "genuine parts details", "other parts details", "labour details",
        "other labour details", "description of goods", "hsn code",
        "billing", "taxable", "cgst", "sgst", "discount", "rate amount",
        "total value", "uom", "qty", "s.no"
    ]

    if lower == "total":
        return True

    if any(word in lower for word in blocked_words):
        return True

    if re.fullmatch(r"total\s+[\d.,\s]+", lower):
        return True

    return False


def count_genuine_spare_items(text):
    """
    Count only actual item rows from Genuine Parts Details / Spares Details.
    Do not count unrelated numbers, total, GST, mobile, VIN, job card.
    """
    section = get_section(
        text,
        ["Genuine Parts Details", "Genuine Part Details", "Spares Details", "Spare Details", "Parts Details"],
        ["Other Parts Details", "Labour Details", "Other Labour Details", "CGST", "SGST", "Net Amount", "Round Off", "Invoice Amount", "Total Invoice"]
    )

    if not section:
        return 0

    count = 0
    for line in section.splitlines():
        line = line.strip()
        if is_total_or_header_line(line):
            continue

        lower = line.lower()
        has_billing_type = bool(re.search(r"\b(paid|fsc|warranty|goodwill)\b", lower))
        has_qty_uom = bool(re.search(r"\b\d+\s*(pc|pcs|ltr|lt|nos|no)\b", lower))
        has_part_code = bool(re.search(r"\b[A-Z0-9]{6,}[-_]?[A-Z0-9]*\b", line))
        has_spare_word = bool(re.search(
            r"spark|plug|filter|oil|shoe|pad|cable|chain|lamp|bulb|bearing|gasket|lever|mirror|clutch|brake|tube|tyre|washer|nut|bolt|cover|seal",
            lower
        ))
        is_tax_line = bool(re.search(r"\bcgst\b|\bsgst\b|\btax\b|round off|net amount|invoice amount", lower))

        if not is_tax_line and ((has_billing_type and has_qty_uom) or (has_part_code and has_spare_word) or (has_spare_word and has_qty_uom)):
            count += 1

    return count


def extract_genuine_spare_details(text):
    section = get_section(
        text,
        ["Genuine Parts Details", "Genuine Part Details", "Spares Details", "Spare Details", "Parts Details"],
        ["Other Parts Details", "Labour Details", "Other Labour Details", "CGST", "SGST", "Net Amount", "Round Off", "Invoice Amount", "Total Invoice"]
    )

    if not section:
        return []

    items = []
    for line in section.splitlines():
        line = line.strip()
        if is_total_or_header_line(line):
            continue

        lower = line.lower()
        has_billing_type = bool(re.search(r"\b(paid|fsc|warranty|goodwill)\b", lower))
        has_qty_uom = bool(re.search(r"\b\d+\s*(pc|pcs|ltr|lt|nos|no)\b", lower))
        has_part_code = bool(re.search(r"\b[A-Z0-9]{6,}[-_]?[A-Z0-9]*\b", line))
        has_spare_word = bool(re.search(
            r"spark|plug|filter|oil|shoe|pad|cable|chain|lamp|bulb|bearing|gasket|lever|mirror|clutch|brake|tube|tyre|washer|nut|bolt|cover|seal",
            lower
        ))

        if (has_billing_type and has_qty_uom) or (has_part_code and has_spare_word) or (has_spare_word and has_qty_uom):
            items.append(clean_part_description(line))

    return items[:10]


def detect_oil(text):
    oil_lines = []

    for line in text.splitlines():
        if re.search(r"Hero\s*4T\s*PLUS|engine\s*oil|\boil\b", line, flags=re.I):
            if not re.search(r"policy|consent|whatsapp|marketing", line, flags=re.I):
                oil_lines.append(line.strip())

    if re.search(r"Hero\s*4T\s*PLUS", text, flags=re.I) and not any(re.search(r"Hero\s*4T\s*PLUS", x, flags=re.I) for x in oil_lines):
        oil_lines.append("Hero 4T PLUS")

    clean_lines = []
    seen = set()
    for line in oil_lines:
        key = line.lower()
        if key not in seen:
            clean_lines.append(line)
            seen.add(key)

    return len(clean_lines), "; ".join(clean_lines[:5]) if clean_lines else "-"


def section_amount(section):
    if not section:
        return 0.0

    lines = [x.strip() for x in section.splitlines() if x.strip()]
    total_lines = [line for line in lines if re.search(r"^total\b", line, flags=re.I)]

    if total_lines:
        nums = re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", total_lines[-1])
        if nums:
            return to_float(nums[-1])

    direct = find_one([
        r"Total\s*Labou?r\s*Amount\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Labou?r\s*Total\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Amount\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)"
    ], section)
    if direct:
        return to_float(direct)

    nums = re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", section)
    return to_float(nums[-1]) if nums else 0.0


def extract_labour_total(text):
    """
    Labour Amount = Labour Details total + Other Labour Details total
    """
    labour_section = get_section(
        text,
        ["Labour Details", "Labor Details"],
        ["Other Labour Details", "Other Labor Details", "CGST", "SGST", "Net Amount", "Round Off", "Invoice Amount", "Total Invoice"]
    )

    other_section = get_section(
        text,
        ["Other Labour Details", "Other Labor Details"],
        ["CGST", "SGST", "Net Amount", "Round Off", "Invoice Amount", "Total Invoice"]
    )

    return round(section_amount(labour_section) + section_amount(other_section), 2)


def extract_invoice_amount(text):
    flat = re.sub(r"\s+", " ", text)

    return to_float(find_one([
        r"Total\s*Invoice\s*Value\s*\(In figure\)\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Total\s*Invoice\s*Value\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Invoice\s*Amount\s*Payable\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Net\s*Amount\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)",
        r"Grand\s*Total\s*[:\-]?\s*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)"
    ], flat))


def parse_invoice(text):
    """
    Hero invoice parser.
    Saves only clean business fields.
    Does not save raw OCR, source file, confidence, GST, mobile, VIN, jobcard last 8.
    """
    flat = re.sub(r"\s+", " ", text)

    invoice_no = find_one([
        r"Invoice\s*(?:No|Number)?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        r"Bill\s*(?:No|Number)?\s*[:\-]?\s*([A-Z0-9\-\/]+)"
    ], flat)

    if not invoice_no:
        invoice_no = find_one([
            r"Job\s*Card\s*(?:No|Number)?\s*[:\-]?\s*([A-Z0-9\-\/]+)",
            r"JC\s*(?:No)?\s*[:\-]?\s*([A-Z0-9\-\/]+)"
        ], flat)

    reg_no = find_one([
        r"Vehicle\s*(?:Reg|Registration)?\s*(?:No|Number)?\s*[:\-]?\s*([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})",
        r"Reg\s*(?:No|Number)?\s*[:\-]?\s*([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})",
        r"\b([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{3,4})\b"
    ], flat)

    bike_model = find_one([
        r"Model\s*[:\-]?\s*([A-Za-z0-9 +._-]{2,45})\s+VIN\b",
        r"Vehicle\s*Model\s*[:\-]?\s*([A-Za-z0-9 +._-]{2,45})",
        r"Model\s*[:\-]?\s*([A-Za-z0-9 +._-]{2,45})"
    ], flat)

    customer_name = find_one([
        r"Customer\s*Name\s*[:\-]?\s*([A-Za-z .]{2,45})\s+Invoice\s*No",
        r"Customer\s*Name\s*[:\-]?\s*([A-Za-z .]{2,45})",
        r"Name\s*[:\-]?\s*([A-Za-z .]{2,45})"
    ], flat)

    spare_items = extract_genuine_spare_details(text)

    return {
        "Customer Name": clean_customer_name(customer_name),
        "Invoice Number": invoice_no,
        "Registration Number": clean_reg_no(reg_no),
        "Bike Model": clean_bike_model(bike_model),
        "Labour Amount": extract_labour_total(text),
        "Spare Parts Count": count_genuine_spare_items(text),
        "Oil Count": detect_oil(text)[0],
        "Oil Details": detect_oil(text)[1],
        "Spare Items Preview": "; ".join(spare_items) if spare_items else "-",
        "Total Amount": extract_invoice_amount(text),
    }


def duplicate_exists(invoice_no, reg_no, total_amount):
    inv = read_sheet("invoices")
    if inv.empty:
        return False

    if invoice_no:
        same_invoice = inv["Invoice Number"].astype(str).str.upper() == str(invoice_no).upper()
        if same_invoice.any():
            return True

    if reg_no and float(total_amount or 0) > 0:
        amount_series = pd.to_numeric(inv["Total Amount"], errors="coerce").fillna(0)
        same_vehicle_amount = (
            (inv["Registration Number"].astype(str).str.upper() == str(reg_no).upper()) &
            (amount_series == float(total_amount))
        )
        if same_vehicle_amount.any():
            return True

    return False


# ============================================================
# REPORT PDF
# ============================================================
def generate_report_pdf(df, title, file_name):
    pdf_path = PDF_DIR / file_name
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(f"<b>{title}</b>", styles["Title"]),
        Spacer(1, 12)
    ]

    if df.empty:
        elements.append(Paragraph("No records found.", styles["BodyText"]))
    else:
        summary = df.groupby(["Technician Name", "Date"], dropna=False).size().reset_index(name="Number of Vehicle Entries")
        elements.append(Paragraph("<b>Summary</b>", styles["Heading2"]))

        s_table = Table([summary.columns.tolist()] + summary.astype(str).values.tolist(), repeatRows=1)
        s_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.black),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        elements.append(s_table)
        elements.append(Spacer(1, 14))

        detail_cols = [
            "Technician Name", "Date", "Registration Number",
            "Bike Model", "Labour Amount", "Total Amount", "Entry Type", "Status"
        ]
        show_cols = [c for c in detail_cols if c in df.columns]
        details = df[show_cols].copy().astype(str)

        elements.append(Paragraph("<b>Entry Details</b>", styles["Heading2"]))
        d_table = Table([details.columns.tolist()] + details.values.tolist(), repeatRows=1)
        d_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.black),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(d_table)

    doc.build(elements)
    return str(pdf_path)


# ============================================================
# MANUAL BILL PDF
# ============================================================
def create_qr_image(text):
    qr = qrcode.make(text)
    path = PDF_DIR / f"qr_{uuid.uuid4().hex[:8]}.png"
    qr.save(path)
    return str(path)


def generate_manual_bill_pdf(customer_name, reg_no, bike_model, spare_rows, labour_amount):
    bill_id = "MB-" + datetime.now().strftime("%Y%m%d%H%M%S")
    pdf_path = PDF_DIR / f"{bill_id}.pdf"

    technician_name = st.session_state.get("employee_name", "")
    user_id = st.session_state.get("user_id", "")

    customer_name = clean_customer_name(customer_name)
    reg_no = clean_reg_no(reg_no)
    bike_model = clean_bike_model(bike_model)

    spare_total = sum(float(row["Amount"]) for row in spare_rows)
    labour_amount = float(labour_amount)
    total_amount = round(spare_total + labour_amount, 2)

    spare_count = len([row for row in spare_rows if str(row["Spare Name"]).strip()])
    oil_count = sum(1 for row in spare_rows if re.search(r"Hero\s*4T\s*PLUS|\boil\b", row["Spare Name"], flags=re.I))

    qr_path = create_qr_image(f"Manual Bill: {bill_id}, Reg: {reg_no}, Total: {total_amount}")

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    w, h = A4

    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, h - 45, "Manual Bill")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, h - 65, "SELVA MOTORS - HERO SERVICE BILL STYLE")
    c.line(40, h - 78, w - 40, h - 78)

    c.setFont("Helvetica", 10)
    c.drawString(40, h - 105, f"Bill ID: {bill_id}")
    c.drawString(350, h - 105, f"Date: {today_str()}")
    c.drawString(40, h - 125, f"Technician Name: {technician_name}")
    c.drawString(350, h - 125, f"User ID: {user_id}")

    c.drawString(40, h - 155, f"Customer Name: {customer_name}")
    c.drawString(40, h - 175, f"Registration Number: {reg_no}")
    c.drawString(350, h - 175, f"Bike Model: {bike_model}")

    y = h - 215
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Spare Parts Details")
    y -= 18

    c.setFont("Helvetica-Bold", 9)
    headers = [("S.No", 45), ("Spare Name", 90), ("Qty", 300), ("Rate", 360), ("Amount", 440)]
    for label, x in headers:
        c.drawString(x, y, label)
    c.line(40, y - 5, w - 40, y - 5)

    c.setFont("Helvetica", 9)
    y -= 22
    for i, row in enumerate(spare_rows, start=1):
        if not str(row["Spare Name"]).strip():
            continue
        c.drawString(45, y, str(i))
        c.drawString(90, y, str(row["Spare Name"])[:28])
        c.drawString(300, y, str(row["Qty"]))
        c.drawString(360, y, f"Rs.{float(row['Rate']):.2f}")
        c.drawString(440, y, f"Rs.{float(row['Amount']):.2f}")
        y -= 18

    y -= 10
    c.line(320, y, w - 40, y)
    y -= 20
    c.setFont("Helvetica-Bold", 10)
    c.drawString(340, y, f"Spare Total: Rs.{spare_total:.2f}")
    y -= 18
    c.drawString(340, y, f"Labour Amount: Rs.{labour_amount:.2f}")
    y -= 22
    c.setFont("Helvetica-Bold", 13)
    c.drawString(340, y, f"Grand Total: Rs.{total_amount:.2f}")

    c.drawImage(qr_path, 45, 70, width=80, height=80)
    c.setFont("Helvetica", 8)
    c.drawString(45, 55, "QR Verification")
    c.drawString(350, 90, "Technician Signature")
    c.line(350, 75, 520, 75)

    c.save()

    append_row("manual_invoices", {
        "Manual Bill ID": bill_id,
        "Date": today_str(),
        "Technician Name": technician_name,
        "User ID": user_id,
        "Customer Name": customer_name,
        "Registration Number": reg_no,
        "Bike Model": bike_model,
        "Labour Amount": labour_amount,
        "Spare Parts Count": spare_count,
        "Oil Count": oil_count,
        "Total Amount": total_amount,
        "PDF File": str(pdf_path),
        "Status": "Generated"
    })

    return str(pdf_path)


# ============================================================
# LOGIN
# ============================================================
def page_login():
    st.markdown("""
    <div class="login-wrap">
        <div class="login-hero">
            <div class="brand-row">
                <div class="brand-logo">🏍️</div>
                <div class="brand-text">
                    <h1>SELVA MOTORS</h1>
                    <p>SERVICE ERP</p>
                </div>
            </div>
            <div style="font-size:26px;font-weight:900;color:#0f172a;margin-top:8px;">Staff Login Portal</div>
            <div class="subtle">Premium service management dashboard for attendance, invoice entry, reports and manual bill workflow.</div>
            <div class="feature-strip">
                <div class="feature-pill">Excel Storage</div>
                <div class="feature-pill">Role Based</div>
                <div class="feature-pill">OCR Entry</div>
                <div class="feature-pill">PDF Reports</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1.05, 1])
    with c2:
        user_id = st.text_input("User ID", placeholder="Enter user id")
        password = st.text_input("Password", type="password", placeholder="Enter password")

        if st.button("Login", use_container_width=True):
            user = login_user(user_id, password)
            if user:
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = user["User ID"]
                st.session_state["employee_name"] = user["Employee Name"]
                st.session_state["role"] = user["Role"]
                st.success("Login success")
                st.rerun()
            else:
                st.error("Invalid login")

def menu_page():
    st.sidebar.markdown("""
    <div style="padding:12px 4px 10px 4px;">
        <div style="height:58px;width:58px;border-radius:22px;background:linear-gradient(135deg,#111827,#16a34a);
        display:grid;place-items:center;font-size:28px;box-shadow:0 16px 32px rgba(34,197,94,.25);">🏍️</div>
        <div style="font-size:29px;font-weight:900;color:#fff;line-height:1;margin-top:12px;">SELVA</div>
        <div style="font-size:13px;font-weight:900;letter-spacing:4px;color:#22c55e;">MOTORS</div>
        <div style="height:1px;background:rgba(255,255,255,.12);margin:15px 0;"></div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown(
        f"""
        <div style="background:rgba(255,255,255,.075);border:1px solid rgba(255,255,255,.10);
        padding:14px;border-radius:20px;margin-bottom:12px;">
            <div style="font-size:13px;color:#94a3b8;font-weight:800;">Logged in as</div>
            <div style="font-size:17px;font-weight:900;color:#fff;">{st.session_state.get('employee_name')}</div>
            <div style="display:inline-block;margin-top:7px;padding:5px 10px;border-radius:999px;
            background:rgba(34,197,94,.14);color:#bbf7d0;font-size:12px;font-weight:900;">
            {st.session_state.get('role')}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    if is_admin():
        pages = [
            "Dashboard", "Reports", "Search",
            "Customer Service History", "Manual Invoice Generator", "Admin Panel"
        ]
    elif is_manager():
        pages = [
            "Dashboard", "Attendance", "Upload Invoice", "Reports", "Search",
            "Customer Service History", "Manual Invoice Generator", "Manager Edit"
        ]
    elif is_technician():
        pages = [
            "Dashboard", "Attendance", "Upload Invoice",
            "Customer Service History", "Manual Invoice Generator",
            "Delete Invoice Request"
        ]
    elif is_prathisha():
        pages = ["Dashboard", "Attendance"]
    else:
        pages = ["Dashboard"]

    icons = {
        "Dashboard": "📊",
        "Attendance": "📍",
        "Upload Invoice": "📄",
        "Reports": "📑",
        "Search": "🔍",
        "Customer Service History": "🧾",
        "Manual Invoice Generator": "🧾",
        "Admin Panel": "⚙️",
        "Manager Edit": "✏️",
        "Delete Invoice Request": "🗑️",
    }
    labels = [f"{icons.get(p, '•')} {p}" for p in pages]
    selected_label = st.sidebar.radio("Menu", labels, label_visibility="collapsed")
    selected_page = selected_label.split(" ", 1)[1]

    st.sidebar.markdown("""
    <div style="margin-top:18px;padding:16px;border-radius:22px;background:rgba(34,197,94,.10);
    border:1px solid rgba(34,197,94,.22);">
        <div style="font-weight:900;color:#fff;">Hero Service Style</div>
        <div style="font-size:12px;color:#cbd5e1;margin-top:4px;">Fast entry • Clean reports • Smart approval</div>
    </div>
    """, unsafe_allow_html=True)

    return selected_page

def metric_card(title, value, caption=""):
    st.markdown(f"""
    <div class="metric-card">
        <p>{title}</p>
        <h2>{value}</h2>
        <small>{caption}</small>
    </div>
    """, unsafe_allow_html=True)



# ============================================================
# HERO EXTREME UI HELPERS
# ============================================================
def hero_badge(text):
    return f"<span class='status-chip'>⚡ {text}</span>" if text else ""


def page_hero(title, subtitle, chip=""):
    st.markdown(f"""
    <div class="hero-panel">
        {hero_badge(chip)}
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def quick_card(title, body, icon="✨"):
    st.markdown(f"""
    <div class="quick-card">
        <h3>{icon} {title}</h3>
        <p>{body}</p>
    </div>
    """, unsafe_allow_html=True)


def preview_item(label, value):
    st.markdown(f"""
    <div class="preview-item">
        <b>{label}</b>
        <span>{value}</span>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# DASHBOARD
# ============================================================
def page_dashboard():
    page_hero("Service Control Dashboard", "Role-based Selva Motors ERP command center with clean revenue, service entries and approvals.", st.session_state.get("role", ""))

    invoices = read_sheet("invoices")
    attendance = read_sheet("attendance")
    delete_req = read_sheet("delete_requests")

    invoices["Total Amount"] = pd.to_numeric(invoices["Total Amount"], errors="coerce").fillna(0)
    invoices["Labour Amount"] = pd.to_numeric(invoices["Labour Amount"], errors="coerce").fillna(0)

    today = today_str()
    user_id = st.session_state.get("user_id", "")

    if is_technician():
        view_df = invoices[
            (invoices["User ID"].astype(str) == user_id) &
            (invoices["Date"].astype(str) == today)
        ]
        pending_req = delete_req[
            (delete_req["User ID"].astype(str) == user_id) &
            (delete_req["Request Status"].astype(str) == "Pending")
        ]

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_card("Today Revenue", f"₹{view_df['Total Amount'].sum():,.0f}", "Your entries only")
        with c2:
            metric_card("Vehicle Entries", len(view_df), "Today completed")
        with c3:
            metric_card("Labour Amount", f"₹{view_df['Labour Amount'].sum():,.0f}", "Today labour")
        with c4:
            metric_card("Delete Requests", len(pending_req), "Pending approval")

        st.markdown("<div class='section-title'>Technician Quick Actions</div>", unsafe_allow_html=True)
        q1, q2, q3 = st.columns(3)
        with q1:
            quick_card("Upload Invoice", "OCR upload and view-only preview before entry.", "📄")
        with q2:
            quick_card("Manual Bill", "Generate Hero-style bill with technician name.", "🧾")
        with q3:
            quick_card("Delete Request", "Request Admin approval for invoice deletion.", "🗑️")

        st.markdown("<div class='section-title'>My Today Entries</div>", unsafe_allow_html=True)
        st.dataframe(view_df, use_container_width=True)
        return

    if is_prathisha():
        today_att = attendance[attendance["Date"].astype(str) == today]
        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card("Today Attendance", len(today_att), "System staff view")
        with c2:
            metric_card("Role Access", "Limited", "Attendance only")
        with c3:
            metric_card("Storage", "Excel", "Secure local sheet")

        st.markdown("<div class='section-title'>Today Attendance List</div>", unsafe_allow_html=True)
        st.dataframe(today_att, use_container_width=True)
        return

    if is_admin():
        month_key = datetime.now().strftime("%m-%Y")
        temp = invoices.copy()
        temp["Month"] = pd.to_datetime(temp["Date"], format="%d-%m-%Y", errors="coerce").dt.strftime("%m-%Y")
        month_df = temp[temp["Month"] == month_key]
        today_df = invoices[invoices["Date"].astype(str) == today]
        pending_req = delete_req[delete_req["Request Status"].astype(str) == "Pending"]

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_card("Monthly Revenue", f"₹{month_df['Total Amount'].sum():,.0f}", "Admin only")
        with c2:
            metric_card("Today Revenue", f"₹{today_df['Total Amount'].sum():,.0f}", "All technicians")
        with c3:
            metric_card("Today Entries", len(today_df), "All vehicles")
        with c4:
            metric_card("Delete Requests", len(pending_req), "Need action")

        st.markdown("<div class='section-title'>Admin Command Shortcuts</div>", unsafe_allow_html=True)
        q1, q2, q3 = st.columns(3)
        with q1:
            quick_card("Reports", "Generate all or particular technician PDF report.", "📑")
        with q2:
            quick_card("Approvals", "Approve or reject technician delete requests.", "✅")
        with q3:
            quick_card("Employee Control", "Add or update employees from Admin Panel.", "👥")

        st.markdown("<div class='section-title'>Technician-wise Revenue</div>", unsafe_allow_html=True)
        if not invoices.empty:
            tech = invoices.groupby("Technician Name", dropna=False)["Total Amount"].sum().reset_index()
            st.dataframe(tech, use_container_width=True)

        st.markdown("<div class='section-title'>Recent Service Entries</div>", unsafe_allow_html=True)
        st.dataframe(invoices.tail(20), use_container_width=True)
        return

    if is_manager():
        today_df = invoices[invoices["Date"].astype(str) == today]
        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card("Today Revenue", f"₹{today_df['Total Amount'].sum():,.0f}", "Manager view")
        with c2:
            metric_card("Today Entries", len(today_df), "All technicians")
        with c3:
            metric_card("Edit Access", "Protected", "Password required")

        st.markdown("<div class='section-title'>Manager Quick Actions</div>", unsafe_allow_html=True)
        q1, q2, q3 = st.columns(3)
        with q1:
            quick_card("Reports", "View all or particular technician entries.", "📑")
        with q2:
            quick_card("Manager Edit", "Update status with password protection.", "✏️")
        with q3:
            quick_card("Customer History", "Search service history by registration.", "🔍")

        st.markdown("<div class='section-title'>Today Entries</div>", unsafe_allow_html=True)
        st.dataframe(today_df, use_container_width=True)


# ============================================================
# ATTENDANCE
# ============================================================
def page_attendance():
    page_hero("Smart Attendance", "GPS auto attendance only. Inside company radius irundha automatic mark aagum.", "Auto GPS")

    user_id = st.session_state["user_id"]
    name = st.session_state["employee_name"]
    user_role = st.session_state["role"]

    today = today_str()
    att = read_sheet("attendance")
    exists = att[
        (att["Date"].astype(str) == today) &
        (att["User ID"].astype(str) == user_id)
    ]

    if not exists.empty:
        st.warning("Today attendance already marked.")
        st.dataframe(exists, use_container_width=True)
        return

    st.markdown("<div class='section-title'>GPS Auto Attendance</div>", unsafe_allow_html=True)

    st.info("Browser location permission Allow pannunga. Manual location and selfie removed.")

    if get_geolocation is None:
        st.error("GPS component not available. requirements.txt la streamlit-js-eval irukkanum.")
        st.code("pip install streamlit-js-eval")
        return

    loc = get_geolocation()

    if not loc:
        st.warning("Location permission allow pannunga. GPS location varala.")
        return

    lat, lon, accuracy = extract_gps_from_browser_location(loc)

    if lat is None or lon is None:
        st.warning("Location detected aagala. Browser permission allow pannunga.")
        with st.expander("Browser location response"):
            st.write(loc)
        return

    dist = distance_meter(lat, lon, COMPANY_LAT, COMPANY_LON)
    bearing = bearing_to_company(lat, lon)
    direction = compass_direction(bearing)
    hint = direction_hint(direction)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Your Latitude", f"{lat:.6f}")
    c2.metric("Your Longitude", f"{lon:.6f}")
    c3.metric("Distance", f"{dist} m")
    c4.metric("Direction", direction)

    if accuracy:
        st.caption(f"GPS Accuracy: {accuracy} meter approx.")

    if dist <= ALLOWED_RADIUS_METER:
        ok, saved_dist = auto_save_attendance_from_gps(lat, lon)
        if ok:
            st.success(f"Attendance auto-marked successfully. Distance: {saved_dist} meter.")
            st.rerun()
        else:
            st.error("Attendance auto-save failed.")
    else:
        st.error("You are outside company location radius. Attendance not marked.")
        st.markdown(f"""
        <div class="glow-card">
            <h3 style="margin:0;color:#991b1b;">Direction Guide</h3>
            <p style="margin:8px 0 0 0;color:#334155;">
                Company location is approximately <b>{dist} meter</b> away.
                Move towards <b>{direction}</b>. {hint}
            </p>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# UPLOAD INVOICE
# ============================================================
def page_upload_invoice():
    page_hero("Invoice OCR Upload", "Upload invoice, verify view-only extracted values and proceed the entry.", "OCR")
    st.caption("OCR Preview is view-only. Values are cleaned before Excel save. Raw OCR text is not saved.")

    uploaded = st.file_uploader("Upload Invoice PDF / Image", type=["pdf", "jpg", "jpeg", "png", "webp"])

    if uploaded:
        file_path = save_uploaded_file(uploaded)
        text = extract_invoice_text(file_path)

        if not text.strip():
            st.error("OCR text not detected. For scanned PDF/image, install Tesseract OCR or upload clearer file.")
            return

        parsed = parse_invoice(text)
        st.session_state["ocr_preview"] = parsed

    if st.button("Use Sample Invoice Data"):
        st.session_state["ocr_preview"] = {
            "Customer Name": "",
            "Invoice Number": "67381-03-RJC-1225-1094",
            "Registration Number": "TN51AT6661",
            "Bike Model": "Splendor Plus",
            "Labour Amount": 1906.88,
            "Spare Parts Count": 5,
            "Oil Count": 1,
            "Oil Details": "Hero 4T PLUS",
            "Spare Items Preview": "Hero 4T PLUS; Oil Filter",
            "Total Amount": 7811,
        }

    if "ocr_preview" not in st.session_state:
        return

    data = st.session_state["ocr_preview"]

    st.markdown("<div class='section-title'>View Only OCR Preview</div>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="glow-card">
        <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;">
            <div><b>Invoice</b><br><span style="color:#16a34a;font-weight:900;">{data.get("Invoice Number", "")}</span></div>
            <div><b>Registration</b><br><span style="color:#0f172a;font-weight:900;">{data.get("Registration Number", "")}</span></div>
            <div><b>Bike Model</b><br><span style="color:#0f172a;font-weight:900;">{data.get("Bike Model", "")}</span></div>
            <div><b>Total</b><br><span style="color:#16a34a;font-weight:900;">₹{data.get("Total Amount", 0)}</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"""
    <div class="bill-preview">
        <h2>OCR Entry Preview</h2>
        <div class="subtle">View-only cleaned values. Unwanted OCR data is not saved.</div>
        <div class="preview-grid">
            <div class="preview-item"><b>Invoice Number</b><span>{data.get("Invoice Number", "")}</span></div>
            <div class="preview-item"><b>Registration Number</b><span>{data.get("Registration Number", "")}</span></div>
            <div class="preview-item"><b>Bike Model</b><span>{data.get("Bike Model", "")}</span></div>
            <div class="preview-item"><b>Total Amount</b><span>₹{data.get("Total Amount", 0)}</span></div>
            <div class="preview-item"><b>Labour Amount</b><span>₹{data.get("Labour Amount", 0)}</span></div>
            <div class="preview-item"><b>Spare Parts Count</b><span>{data.get("Spare Parts Count", 0)}</span></div>
            <div class="preview-item"><b>Oil Count</b><span>{data.get("Oil Count", 0)}</span></div>
            <div class="preview-item"><b>Oil Details</b><span>{data.get("Oil Details", "")}</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    preview_df = pd.DataFrame([{
        "Invoice Number": data.get("Invoice Number", ""),
        "Registration Number": data.get("Registration Number", ""),
        "Bike Model": data.get("Bike Model", ""),
        "Labour Amount": data.get("Labour Amount", 0),
        "Spare Parts Count": data.get("Spare Parts Count", 0),
        "Oil Count": data.get("Oil Count", 0),
        "Oil Details": data.get("Oil Details", ""),
        "Spare Items Preview": data.get("Spare Items Preview", "-"),
        "Total Amount": data.get("Total Amount", 0),
        "Entry Type": "OCR Upload",
        "Status": "Active"
    }])
    st.dataframe(preview_df, use_container_width=True)

    missing = []
    for col in ["Invoice Number", "Registration Number", "Bike Model"]:
        if not str(data.get(col, "")).strip():
            missing.append(col)

    if missing:
        st.warning("Missing detected values: " + ", ".join(missing))
        st.info("Preview is view-only as per requirement. Upload a clearer invoice if values are missing.")

    duplicate = duplicate_exists(
        data.get("Invoice Number", ""),
        data.get("Registration Number", ""),
        data.get("Total Amount", 0)
    )
    if duplicate:
        st.error("Duplicate invoice/vehicle amount detected.")

    if st.button("Click to Proceed the Entry", use_container_width=True):
        if missing:
            st.error("Required values missing. Cannot proceed.")
            return

        entry_id = "E-" + uuid.uuid4().hex[:8].upper()
        append_row("invoices", {
            "Entry ID": entry_id,
            "Date": today_str(),
            "Technician Name": st.session_state.get("employee_name", ""),
            "User ID": st.session_state.get("user_id", ""),
            "Invoice Number": data.get("Invoice Number", ""),
            "Registration Number": data.get("Registration Number", ""),
            "Bike Model": clean_bike_model(data.get("Bike Model", "")),
            "Labour Amount": data.get("Labour Amount", 0),
            "Spare Parts Count": data.get("Spare Parts Count", 0),
            "Oil Count": data.get("Oil Count", 0),
            "Oil Details": data.get("Oil Details", ""),
            "Total Amount": data.get("Total Amount", 0),
            "Entry Type": "OCR Upload",
            "Status": "Active"
        })

        del st.session_state["ocr_preview"]
        st.success("Entry saved to Excel.")
        st.rerun()


# ============================================================
# REPORTS
# ============================================================
def page_reports():
    page_hero("Reports", "Generate all-technician or particular-technician PDF service reports.", "PDF")

    invoices = read_sheet("invoices")

    if invoices.empty:
        st.info("No invoice entries found.")
        return

    invoices["Total Amount"] = pd.to_numeric(invoices["Total Amount"], errors="coerce").fillna(0)
    invoices["Labour Amount"] = pd.to_numeric(invoices["Labour Amount"], errors="coerce").fillna(0)

    if is_technician():
        invoices = invoices[
            (invoices["User ID"].astype(str) == st.session_state.get("user_id", "")) &
            (invoices["Date"].astype(str) == today_str())
        ]
        st.info("Technician view: only today’s own entries are shown.")

    else:
        view_type = st.radio(
            "Report View Type",
            ["All Technicians", "Particular Technician"],
            horizontal=True
        )

        if view_type == "Particular Technician":
            tech_names = sorted([
                x for x in invoices["Technician Name"].astype(str).unique().tolist()
                if x.strip()
            ])
            selected_tech = st.selectbox("Select Technician", tech_names)
            invoices = invoices[invoices["Technician Name"].astype(str) == selected_tech]
        else:
            st.info("All technician entries are shown.")

        c1, c2 = st.columns(2)
        with c1:
            date_filter = st.text_input("Date Filter DD-MM-YYYY", value="")
        with c2:
            reg_filter = st.text_input("Registration Number Filter", value="")

        if date_filter.strip():
            invoices = invoices[invoices["Date"].astype(str) == date_filter.strip()]

        if reg_filter.strip():
            reg_clean = clean_reg_no(reg_filter)
            invoices = invoices[invoices["Registration Number"].astype(str).str.upper() == reg_clean]

    st.markdown("<div class='section-title'>Report Preview</div>", unsafe_allow_html=True)

    show_cols = [
        "Technician Name", "Date", "Registration Number",
        "Bike Model", "Labour Amount", "Total Amount", "Entry Type", "Status"
    ]

    preview = invoices[show_cols] if not invoices.empty else invoices
    st.dataframe(preview, use_container_width=True)

    total_entries = len(invoices)
    total_revenue = invoices["Total Amount"].sum() if "Total Amount" in invoices.columns else 0
    total_labour = invoices["Labour Amount"].sum() if "Labour Amount" in invoices.columns else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Vehicle Entries", total_entries)
    c2.metric("Total Revenue", f"₹{total_revenue:,.0f}")
    c3.metric("Labour Amount", f"₹{total_labour:,.0f}")

    st.divider()

    if st.button("Generate PDF Report", use_container_width=True):
        pdf = generate_report_pdf(
            invoices,
            "Selva Motors Service Report",
            "selva_motors_service_report.pdf"
        )
        st.session_state["generated_report_pdf"] = pdf
        st.success("PDF report generated. Click download below.")

    if st.session_state.get("generated_report_pdf"):
        pdf_path = st.session_state["generated_report_pdf"]
        if Path(pdf_path).exists():
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "Download PDF Report",
                    f,
                    file_name=Path(pdf_path).name,
                    mime="application/pdf",
                    use_container_width=True
                )


# ============================================================
# SEARCH
# ============================================================
def page_search():
    page_hero("Smart Search", "Search invoice entries by registration number, invoice number or technician.", "Search")

    invoices = read_sheet("invoices")
    query = st.text_input("Search by Registration Number / Invoice Number / Technician Name")

    if query:
        q = query.lower()
        result = invoices[
            invoices.astype(str).apply(lambda row: row.str.lower().str.contains(q, na=False).any(), axis=1)
        ]
    else:
        result = invoices

    safe_cols = [
        "Entry ID", "Date", "Technician Name", "User ID", "Invoice Number",
        "Registration Number", "Bike Model", "Labour Amount",
        "Spare Parts Count", "Oil Count", "Oil Details", "Total Amount",
        "Entry Type", "Status"
    ]
    st.dataframe(result[safe_cols], use_container_width=True)


# ============================================================
# CUSTOMER SERVICE HISTORY
# ============================================================
def page_customer_service_history():
    page_hero("Customer Service History", "Today service entries and registration-number based history search.", "History")

    invoices = read_sheet("invoices")
    today = today_str()

    if is_technician():
        today_entries = invoices[
            (invoices["Date"].astype(str) == today) &
            (invoices["User ID"].astype(str) == st.session_state.get("user_id", ""))
        ]
        st.info("Technician view: your today entries only.")
    else:
        today_entries = invoices[invoices["Date"].astype(str) == today]
        st.info("Admin/Manager view: all today's service entries are shown.")

    st.markdown("<div class='section-title'>Today’s Service Entry History</div>", unsafe_allow_html=True)
    st.dataframe(today_entries, use_container_width=True)

    st.markdown("<div class='section-title'>Registration Number Search</div>", unsafe_allow_html=True)
    reg = st.text_input("Enter Registration Number", placeholder="TN51AT6661")
    if reg:
        reg_clean = clean_reg_no(reg)
        result = invoices[invoices["Registration Number"].astype(str).str.upper() == reg_clean]
        st.dataframe(result, use_container_width=True)


# ============================================================
# MANUAL INVOICE GENERATOR
# ============================================================
def page_manual_invoice():
    page_hero("Manual Bill", "Generate Hero-style manual service bill PDF with serial numbered spare rows.", "PDF Bill")
    st.caption("Hero-style manual bill PDF. Technician name is taken from current logged-in user.")

    c1, c2 = st.columns(2)
    customer_name = c1.text_input("Customer Name")
    reg_no = c2.text_input("Registration Number")
    bike_model = c1.text_input("Bike Model")

    st.subheader("Spare Parts Rows")
    row_count = st.number_input("Number of Spare Part Rows", min_value=1, max_value=15, value=3)

    spare_rows = []
    for i in range(int(row_count)):
        c1, c2, c3, c4, c5 = st.columns([1, 3, 1, 1, 1])
        c1.text_input("S.No", value=str(i + 1), key=f"sno_{i}", disabled=True)
        name = c2.text_input(f"Spare Name {i+1}", key=f"spare_name_{i}")
        qty = c3.number_input(f"Qty {i+1}", min_value=0, value=1, key=f"qty_{i}")
        rate = c4.number_input(f"Rate {i+1}", min_value=0.0, value=0.0, key=f"rate_{i}")
        amount = qty * rate
        c5.metric("Amount", f"₹{amount:.2f}")

        spare_rows.append({
            "S.No": i + 1,
            "Spare Name": name,
            "Qty": qty,
            "Rate": rate,
            "Amount": amount
        })

    labour_amount = st.number_input("Labour Amount", min_value=0.0, value=0.0)

    st.markdown("""
    <div class="bill-preview">
        <h2>Live Manual Bill Preview</h2>
        <div class="subtle">PDF will show title as Manual Bill, serial rows, labour amount and logged-in technician name.</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Generate Manual Bill PDF", use_container_width=True):
        if not reg_no or not bike_model:
            st.error("Registration Number and Bike Model required.")
            return

        pdf = generate_manual_bill_pdf(customer_name, reg_no, bike_model, spare_rows, labour_amount)
        st.success("Manual Bill PDF generated.")

        with open(pdf, "rb") as f:
            st.download_button("Download Manual Bill PDF", f, file_name=Path(pdf).name, mime="application/pdf")


# ============================================================
# DELETE INVOICE REQUEST
# ============================================================
def page_delete_invoice_request():
    page_hero("Delete Invoice Request", "Technicians can request deletion; Admin approves or rejects.", "Approval")

    invoices = read_sheet("invoices")
    own = invoices[
        (invoices["User ID"].astype(str) == st.session_state.get("user_id", "")) &
        (invoices["Status"].astype(str).str.lower() == "active")
    ]

    st.info("Technician can only request delete. Direct delete is not allowed.")
    st.dataframe(own, use_container_width=True)

    if own.empty:
        return

    entry_id = st.selectbox("Select Entry ID", own["Entry ID"].astype(str).tolist())
    reason = st.text_area("Reason for delete request")

    if st.button("Submit Delete Request"):
        if not reason.strip():
            st.error("Reason required.")
            return

        existing = read_sheet("delete_requests")
        pending_exists = existing[
            (existing["Entry ID"].astype(str) == entry_id) &
            (existing["Request Status"].astype(str) == "Pending")
        ]

        if not pending_exists.empty:
            st.warning("Pending request already exists for this entry.")
            return

        row = own[own["Entry ID"].astype(str) == entry_id].iloc[0]

        append_row("delete_requests", {
            "Request ID": "DR-" + uuid.uuid4().hex[:8].upper(),
            "Date": today_str(),
            "Time": time_str(),
            "Entry ID": entry_id,
            "Technician Name": row["Technician Name"],
            "User ID": row["User ID"],
            "Reason": reason,
            "Request Status": "Pending",
            "Admin Action Date": ""
        })

        st.success("Delete request sent to Admin.")


# ============================================================
# ADMIN PANEL
# ============================================================
def page_admin_panel():
    page_hero("Admin Panel", "Employee edit, technician revenue, delete approvals and protected Excel access.", "Admin")

    invoices = read_sheet("invoices")
    invoices["Total Amount"] = pd.to_numeric(invoices["Total Amount"], errors="coerce").fillna(0)

    st.subheader("Admin Revenue View")
    month_key = datetime.now().strftime("%m-%Y")
    temp = invoices.copy()
    temp["Month"] = pd.to_datetime(temp["Date"], format="%d-%m-%Y", errors="coerce").dt.strftime("%m-%Y")
    month_df = temp[temp["Month"] == month_key]

    c1, c2 = st.columns(2)
    c1.metric("Monthly Revenue", f"₹{month_df['Total Amount'].sum():,.0f}")
    c2.metric("Total Active Entries", len(invoices[invoices["Status"].astype(str) == "Active"]))

    st.subheader("Technician-wise Revenue Details")
    if not invoices.empty:
        tech = invoices.groupby("Technician Name", dropna=False)["Total Amount"].sum().reset_index()
        st.dataframe(tech, use_container_width=True)

    st.divider()
    st.subheader("Employee Edit Options")
    employees = read_sheet("employees")
    st.dataframe(employees, use_container_width=True)

    with st.expander("Add / Edit Employee"):
        user_id = st.text_input("User ID")
        password = st.text_input("Password")
        emp_name = st.text_input("Employee Name")
        emp_role = st.selectbox("Role", ["Admin", "Manager", "Technician", "Prathisha / System Staff"])
        status = st.selectbox("Status", ["Active", "Inactive"])

        if st.button("Save Employee"):
            if not user_id or not password or not emp_name:
                st.error("All fields required.")
            else:
                df = read_sheet("employees")
                if (df["User ID"].astype(str) == user_id).any():
                    idx = df[df["User ID"].astype(str) == user_id].index[0]
                    df.loc[idx, "Password"] = password
                    df.loc[idx, "Employee Name"] = emp_name
                    df.loc[idx, "Role"] = emp_role
                    df.loc[idx, "Status"] = status
                    write_sheet("employees", df)
                    st.success("Employee updated.")
                else:
                    append_row("employees", {
                        "User ID": user_id,
                        "Password": password,
                        "Employee Name": emp_name,
                        "Role": emp_role,
                        "Status": status
                    })
                    st.success("Employee added.")
                st.rerun()

    st.divider()
    st.subheader("Technician Delete Invoice Requests")
    req = read_sheet("delete_requests")
    pending = req[req["Request Status"].astype(str) == "Pending"]

    if pending.empty:
        st.info("No pending delete requests.")
    else:
        for idx, row in pending.iterrows():
            with st.container():
                st.write(f"Request ID: **{row['Request ID']}** | Entry ID: **{row['Entry ID']}**")
                st.write(f"Technician: **{row['Technician Name']}** | Reason: {row['Reason']}")

                c1, c2 = st.columns(2)
                if c1.button("Approve Delete", key=f"approve_{idx}"):
                    inv = read_sheet("invoices")
                    inv_idx = inv[inv["Entry ID"].astype(str) == str(row["Entry ID"])].index
                    if len(inv_idx) > 0:
                        inv = inv.drop(inv_idx)
                        write_sheet("invoices", inv)

                    req.loc[idx, "Request Status"] = "Approved"
                    req.loc[idx, "Admin Action Date"] = now_stamp()
                    write_sheet("delete_requests", req)
                    st.success("Request approved and invoice deleted.")
                    st.rerun()

                if c2.button("Reject Request", key=f"reject_{idx}"):
                    req.loc[idx, "Request Status"] = "Rejected"
                    req.loc[idx, "Admin Action Date"] = now_stamp()
                    write_sheet("delete_requests", req)
                    st.warning("Request rejected.")
                    st.rerun()

    st.divider()
    st.subheader("Settings")
    settings = read_sheet("settings")
    st.dataframe(settings, use_container_width=True)


    st.subheader("Auto Backup Status - 10 PM")
    c1, c2, c3 = st.columns(3)
    c1.metric("Last Backup Date", get_setting_value("Last Auto Backup Date", "Not yet"))
    c2.metric("Last Backup Time", get_setting_value("Last Auto Backup Time", "Not yet"))
    c3.metric("Status", get_setting_value("Last Auto Backup Status", "Not yet"))
    st.caption("Auto backup runs once per day after 10:00 PM when the app is opened or rerun.")

    st.subheader("30 Minutes Auto Google Sheet Sync Status")
    if is_google_auto_sync_enabled():
        st.success("30 minutes auto sync is ON. Excel saves instantly first; changed sheets sync to Google Sheet once every 30 minutes.")
    else:
        st.warning("30 minutes auto sync is OFF. Add SHEET_ID and gcp_service_account in Streamlit Secrets.")

    sync_state = load_sync_state()
    dirty_sheets = sync_state.get("dirty_sheets", [])
    waiting_text = get_next_sync_wait_text()
    badge_text = get_sync_status_badge_text()

    if dirty_sheets:
        st.warning(f"Google Sheet update waiting: {len(dirty_sheets)} sheet(s) pending.")
    elif sync_state.get("last_sync_status") == "Success":
        st.success("Google Sheet updated successfully. No pending sheets.")
    else:
        st.info("Google Sheet sync not yet completed.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Google Sheet Status", badge_text)
    c2.metric("Waiting Sheets", len(dirty_sheets))
    c3.metric("Next Auto Sync", waiting_text)
    c4.metric("Last Sync Time", sync_state.get("last_sync_time", "Not yet"))

    if dirty_sheets:
        st.caption("Waiting sheets: " + ", ".join(dirty_sheets))

    if sync_state.get("last_sync_message"):
        st.caption("Last sync message: " + str(sync_state.get("last_sync_message", "")))

    if st.button("Sync Changed Sheets Now", use_container_width=True):
        with st.spinner("Syncing changed sheets to Google Sheet..."):
            ok, msg = sync_dirty_sheets_to_google_sheet()

        if ok:
            st.success("Google Sheet updated now. " + msg)
            st.rerun()
        else:
            st.error(msg)

    st.subheader("Google Sheet Cloud Backup")
    st.caption("Excel storage is primary. This button copies all Excel sheets to Google Sheet only when Admin clicks it.")

    if st.button("Sync All Excel Data to Google Sheet", use_container_width=True):
        with st.spinner("Syncing Excel data to Google Sheet..."):
            ok, msg = sync_excel_to_google_sheet()

        if ok:
            st.success(msg)
        else:
            st.error(msg)


    st.subheader("Password Protected Excel Sheet Direct Link")
    pwd = st.text_input("Enter password to view Excel link", type="password")
    if pwd == SECRET_PASSWORD:
        st.success("Password correct.")
        st.write(f"Excel file path: `{EXCEL_FILE}`")
        if EXCEL_FILE.exists():
            with open(EXCEL_FILE, "rb") as f:
                st.download_button(
                    "Download / Visit Excel Sheet",
                    f,
                    file_name="selva_motors_excel_storage.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    elif pwd:
        st.error("Wrong password.")


# ============================================================
# MANAGER EDIT
# ============================================================
def page_manager_edit():
    page_hero("Manager Edit", "Password protected entry status edit options.", "Protected")

    pwd = st.text_input("Enter edit password", type="password")
    if pwd != SECRET_PASSWORD:
        if pwd:
            st.error("Wrong password.")
        st.info("Manager edit requires password.")
        return

    st.success("Edit access granted.")

    invoices = read_sheet("invoices")
    st.dataframe(invoices, use_container_width=True)

    if invoices.empty:
        return

    entry_id = st.selectbox("Select Entry ID to edit status", invoices["Entry ID"].astype(str).tolist())
    new_status = st.selectbox("New Status", ["Active", "Hold", "Completed", "Cancelled"])

    if st.button("Update Status"):
        idx = invoices[invoices["Entry ID"].astype(str) == entry_id].index
        if len(idx) > 0:
            invoices.loc[idx[0], "Status"] = new_status
            write_sheet("invoices", invoices)
            st.success("Status updated.")
            st.rerun()


# ============================================================
# BACKUP OPTIONAL
# ============================================================
def make_backup_zip():
    name = f"selva_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    path = BACKUP_DIR / name

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        if EXCEL_FILE.exists():
            z.write(EXCEL_FILE, EXCEL_FILE.name)
        for pdf in PDF_DIR.glob("*.pdf"):
            z.write(pdf, f"generated_reports/{pdf.name}")

    return path


# ============================================================
# MAIN
# ============================================================
def main():
    if not st.session_state.get("logged_in"):
        page_login()
        return

    auto_backup_check_10pm()

    page = menu_page()

    if page == "Dashboard":
        page_dashboard()
    elif page == "Attendance":
        page_attendance()
    elif page == "Upload Invoice":
        page_upload_invoice()
    elif page == "Reports":
        page_reports()
    elif page == "Search":
        page_search()
    elif page == "Customer Service History":
        page_customer_service_history()
    elif page == "Manual Invoice Generator":
        page_manual_invoice()
    elif page == "Delete Invoice Request":
        page_delete_invoice_request()
    elif page == "Admin Panel":
        if is_admin():
            page_admin_panel()
        else:
            st.error("Admin access only.")
    elif page == "Manager Edit":
        if is_manager():
            page_manager_edit()
        else:
            st.error("Manager access only.")


if __name__ == "__main__":
    main()
