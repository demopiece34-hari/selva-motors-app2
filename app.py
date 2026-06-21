from __future__ import annotations

from datetime import datetime, date
from pathlib import Path
import io
import pandas as pd
import streamlit as st

from google_sheet import SHEET_SCHEMAS, append_row, clear_sheet_cache, read_sheet, update_sheet
from hero_loader import show_loader
from ocr_module import load_and_parse
from pdf_generator import attendance_pdf, invoice_pdf, job_card_pdf, report_pdf
from utils import (
    date_key,
    detect_duplicates,
    ensure_columns,
    filter_contains,
    haversine_meters,
    make_id,
    money,
    month_key,
    now_india,
    now_time_str,
    safe_str,
    to_float,
    today_str,
    compute_grand_total,
)

# ------------------------------ CONFIG ------------------------------
st.set_page_config(
    page_title="SELVA MOTORS | HERO Dealership ERP",
    page_icon="🏍️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

APP_NAME = "SELVA MOTORS"
BRAND = "HERO Dealership ERP"
COMPANY_LAT = 10.759710
COMPANY_LON = 79.742772
ALLOWED_RADIUS_M = 400

PAGES = [
    "Dashboard",
    "Attendance",
    "Service Jobs",
    "Invoices",
    "Manual Bill",
    "OCR Upload",
    "Customer History",
    "Technician",
    "Reports",
    "Global Search",
    "Duplicate Check",
    "Settings",
]

ROLE_PAGES = {
    "Owner": PAGES,
    "Admin": PAGES,
    "Service Advisor": ["Dashboard", "Attendance", "Service Jobs", "Customer History", "Global Search", "Reports", "Duplicate Check"],
    "Technician": ["Dashboard", "Attendance", "Service Jobs", "Customer History", "Global Search"],
    "Billing": ["Dashboard", "Invoices", "Manual Bill", "OCR Upload", "Global Search", "Reports"],
}

ROLE_ALIASES = {
    "advisor": "Service Advisor",
    "service advisor": "Service Advisor",
    "technician": "Technician",
    "billing": "Billing",
    "admin": "Admin",
    "owner": "Owner",
}

ACTIVE_VALUES = {"active", "yes", "y", "1", "enabled", "true"}

# ------------------------------ STYLE ------------------------------
def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --hero-red: #e31837;
            --hero-red-dark: #b0122a;
            --hero-black: #111827;
            --hero-bg: #f8fafc;
            --hero-border: rgba(226,232,240,.95);
            --hero-card: rgba(255,255,255,.92);
        }
        html, body, [class*="css"] { font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
        .stApp {
            background:
                radial-gradient(circle at 4% 2%, rgba(227,24,55,.12), transparent 22%),
                radial-gradient(circle at 96% 6%, rgba(227,24,55,.08), transparent 18%),
                linear-gradient(135deg, #f8fafc 0%, #eef2ff 50%, #fff 100%);
        }
        .block-container { padding-top: 1rem; padding-bottom: 1.5rem; max-width: 1450px; }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #111827 0%, #0f172a 100%);
            border-right: 1px solid rgba(255,255,255,.08);
        }
        [data-testid="stSidebar"] * { color: #e5e7eb; }
        [data-testid="stTextInput"] input,
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stNumberInput"] input,
        textarea {
            border-radius: 14px !important;
            border: 1px solid #cbd5e1 !important;
        }
        .hero-shell {
            border: 1px solid var(--hero-border);
            border-radius: 28px;
            background: linear-gradient(145deg, rgba(255,255,255,.95), rgba(255,255,255,.8));
            box-shadow: 0 28px 70px rgba(15,23,42,.10);
            padding: 18px;
        }
        .hero-title { font-size: 34px; font-weight: 1000; letter-spacing: -1px; color: #111827; margin: 0; }
        .hero-subtitle { color: #64748b; margin-top: 4px; font-size: 14px; }
        .hero-badge {
            display:inline-block; padding: 7px 12px; border-radius: 999px;
            background: rgba(227,24,55,.08); color: var(--hero-red);
            border: 1px solid rgba(227,24,55,.16); font-weight: 800; font-size: 12px;
        }
        .metric-card {
            border-radius: 22px;
            background: var(--hero-card);
            border: 1px solid var(--hero-border);
            box-shadow: 0 16px 36px rgba(15,23,42,.08);
            padding: 16px 16px 14px 16px;
            height: 100%;
        }
        .metric-label { font-size: 12px; letter-spacing: 1px; text-transform: uppercase; color: #64748b; font-weight: 900; }
        .metric-value { font-size: 28px; font-weight: 1000; color: #111827; margin-top: 6px; line-height: 1.1; }
        .metric-note { font-size: 13px; color: #64748b; margin-top: 4px; }
        .quick-card {
            border-radius: 20px;
            background: white;
            border: 1px solid var(--hero-border);
            padding: 14px;
            box-shadow: 0 12px 26px rgba(15,23,42,.06);
        }
        .section-title {
            font-size: 18px; font-weight: 950; color: #111827; margin: 0 0 8px 0;
        }
        .small-muted { color: #64748b; font-size: 13px; }
        .table-wrap { overflow-x: auto; }
        .stButton>button {
            border-radius: 14px !important;
            border: none !important;
            background: linear-gradient(135deg, var(--hero-red), var(--hero-red-dark)) !important;
            color: white !important;
            font-weight: 800 !important;
            padding: .62rem 1rem !important;
        }
        .stDownloadButton>button {
            border-radius: 14px !important;
            font-weight: 800 !important;
        }
        .login-card {
            max-width: 640px;
            margin: 3rem auto 2rem auto;
            border-radius: 30px;
            border: 1px solid rgba(255,255,255,.9);
            background: linear-gradient(145deg, rgba(255,255,255,.97), rgba(255,255,255,.82));
            box-shadow: 0 30px 90px rgba(15,23,42,.18);
            padding: 30px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ------------------------------ HELPERS ------------------------------
def init_state() -> None:
    defaults = {
        "authenticated": False,
        "user": {},
        "page": "Dashboard",
        "pending_page": None,
        "toast": "",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def get_users_df() -> pd.DataFrame:
    return read_sheet("employees", SHEET_SCHEMAS["employees"])


def normalize_role(role: str) -> str:
    role = safe_str(role)
    return ROLE_ALIASES.get(role.strip().lower(), role if role else "Admin")


def allowed_pages(role: str) -> list[str]:
    role = normalize_role(role)
    return ROLE_PAGES.get(role, ["Dashboard"])


def user_is_active(status: str) -> bool:
    return safe_str(status).strip().lower() in ACTIVE_VALUES


def find_user(user_id: str, password: str) -> dict | None:
    users = get_users_df()
    if users.empty:
        return None
    df = ensure_columns(users, SHEET_SCHEMAS["employees"]).copy()
    uid = safe_str(user_id).strip().lower()
    pwd = safe_str(password).strip()
    match = df[
        df["User ID"].astype(str).str.strip().str.lower().eq(uid)
        & df["Password"].astype(str).str.strip().eq(pwd)
    ]
    if match.empty:
        return None
    row = match.iloc[0].to_dict()
    role = normalize_role(row.get("Role", "Admin"))
    return {
        "user_id": safe_str(row.get("User ID")),
        "name": safe_str(row.get("Employee Name")) or safe_str(row.get("User ID")),
        "role": role,
        "status": safe_str(row.get("Status")),
    }


def login_screen() -> None:
    inject_css()
    st.markdown(
        """
        <div class="hero-shell login-card">
            <div class="hero-badge">HERO DEALERSHIP ERP</div>
            <h1 class="hero-title" style="margin-top:12px;">SELVA MOTORS</h1>
            <p class="hero-subtitle">Production-ready showroom software for service, billing, attendance and reporting.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns([1, 1])
    with col1:
        st.info("Login reads only the Employees sheet. Other sheets stay closed until you open a module.")
    with col2:
        st.info("Google Sheet is the only source of truth. No Excel sync, no local workbook, no background jobs.")

    with st.form("login_form", clear_on_submit=False):
        user_id = st.text_input("User ID", placeholder="Enter your user ID")
        password = st.text_input("Password", type="password", placeholder="Enter password")
        submitted = st.form_submit_button("Login")
        if submitted:
            user = find_user(user_id, password)
            if not user:
                st.error("Invalid credentials.")
                return
            if not user_is_active(user["status"]):
                st.error("This account is inactive.")
                return
            st.session_state.authenticated = True
            st.session_state.user = user
            st.session_state.page = "Dashboard"
            st.session_state.pending_page = None
            st.rerun()

    st.caption("If the Employees sheet is empty, add at least one active account with User ID, Password, Employee Name, Role and Status.")


def logout() -> None:
    st.session_state.authenticated = False
    st.session_state.user = {}
    st.session_state.page = "Dashboard"
    st.rerun()


def set_page(page: str) -> None:
    st.session_state.page = page
    st.rerun()


def df_today(df: pd.DataFrame, date_col: str = "Date") -> pd.DataFrame:
    if df is None or df.empty or date_col not in df.columns:
        return pd.DataFrame(columns=getattr(df, "columns", []))
    return df[df[date_col].astype(str).str.startswith(today_str())].copy()


def df_month(df: pd.DataFrame, date_col: str = "Date", month_value: str | None = None) -> pd.DataFrame:
    if df is None or df.empty or date_col not in df.columns:
        return pd.DataFrame(columns=getattr(df, "columns", []))
    mv = month_value or month_key(today_str())
    return df[df[date_col].astype(str).str.startswith(mv)].copy()


def render_topbar(user: dict) -> None:
    left, right = st.columns([3, 1])
    with left:
        st.markdown(
            f"""
            <div class="hero-shell">
                <div class="hero-badge">SELVA MOTORS</div>
                <h1 class="hero-title">{BRAND}</h1>
                <div class="hero-subtitle">Logged in as <b>{user.get("name", "")}</b> · {user.get("role", "")}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        if st.button("Logout", use_container_width=True):
            logout()


def nav_items(role: str) -> list[str]:
    role = normalize_role(role)
    base = allowed_pages(role)
    return base if base else ["Dashboard"]


def sidebar_nav(user: dict) -> None:
    pages = nav_items(user.get("role", "Admin"))
    st.sidebar.markdown("## SELVA MOTORS")
    st.sidebar.caption("Hero dealership ERP")
    selection = st.sidebar.radio("Navigation", pages, index=pages.index(st.session_state.page) if st.session_state.page in pages else 0)
    if selection != st.session_state.page:
        st.session_state.page = selection
        st.rerun()
    st.sidebar.markdown("---")
    st.sidebar.write(f"**User:** {user.get('name', '')}")
    st.sidebar.write(f"**Role:** {user.get('role', '')}")
    st.sidebar.write(f"**Date:** {today_str()}")
    if st.sidebar.button("Logout", use_container_width=True):
        logout()


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def display_df(df: pd.DataFrame, height: int = 380) -> None:
    if df is None or df.empty:
        st.info("No records found.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)


def show_loader_and_read(sheet_name: str, columns: list[str] | None = None, message: str = "Loading data", wait_text: str = "Please wait") -> pd.DataFrame:
    show_loader(message=message, wait_text=wait_text, duration=0.9)
    return read_sheet(sheet_name, columns or SHEET_SCHEMAS.get(sheet_name, []), force_refresh=True)


def today_revenue() -> float:
    inv = df_today(read_sheet("invoices", SHEET_SCHEMAS["invoices"]))
    bill = df_today(read_sheet("manual_invoices", SHEET_SCHEMAS["manual_invoices"]))
    total = 0.0
    if not inv.empty and "Total Amount" in inv.columns:
        total += inv["Total Amount"].map(to_float).sum()
    if not bill.empty and "Grand Total" in bill.columns:
        total += bill["Grand Total"].map(to_float).sum()
    return total


def dashboard_summary() -> dict:
    service = read_sheet("service_jobs", SHEET_SCHEMAS["service_jobs"])
    attend = read_sheet("attendance", SHEET_SCHEMAS["attendance"])
    invoices = read_sheet("invoices", SHEET_SCHEMAS["invoices"])
    service_today = df_today(service)
    attend_today = df_today(attend)
    inv_today = df_today(invoices)
    pending = 0
    completed = 0
    if not service.empty and "Status" in service.columns:
        status = service["Status"].astype(str).str.lower()
        pending = int(service[~status.str.contains("completed|closed|delivered", na=False)].shape[0])
        completed = int(service[status.str.contains("completed|closed|delivered", na=False)].shape[0])
    revenue = today_revenue()
    technician_perf = pd.DataFrame(columns=["Technician Name", "Jobs"])
    if not service_today.empty and "Technician Name" in service_today.columns:
        technician_perf = service_today.groupby("Technician Name").size().reset_index(name="Jobs").sort_values("Jobs", ascending=False)
    present = 0
    if not attend_today.empty and "Attendance Status" in attend_today.columns:
        present = int(attend_today["Attendance Status"].astype(str).str.contains("check in|present", case=False, na=False).sum())
    return {
        "today_service": int(service_today.shape[0]),
        "today_invoice": int(inv_today.shape[0]),
        "today_revenue": revenue,
        "pending_jobs": pending,
        "completed_jobs": completed,
        "attendance_today": present,
        "technician_perf": technician_perf,
    }


# ------------------------------ DASHBOARD ------------------------------
def render_dashboard(user: dict) -> None:
    summary = dashboard_summary()
    st.markdown('<div class="section-title">Smart Dashboard</div>', unsafe_allow_html=True)
    st.caption("Today's summary is loaded from only the required sheets.")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Today's Service Count", str(summary["today_service"]), "Open job cards created today")
    with c2:
        metric_card("Today's Revenue", money(summary["today_revenue"]), "Invoices and manual bills")
    with c3:
        metric_card("Pending Jobs", str(summary["pending_jobs"]), "Awaiting completion")
    with c4:
        metric_card("Completed Jobs", str(summary["completed_jobs"]), "Closed or delivered")

    c5, c6 = st.columns(2)
    with c5:
        metric_card("Attendance Summary", str(summary["attendance_today"]), "Check-ins recorded today")
    with c6:
        top_perf = summary["technician_perf"].head(1)
        note = top_perf.iloc[0]["Technician Name"] if not top_perf.empty else "No technician activity yet"
        metric_card("Technician Performance", str(int(top_perf.iloc[0]["Jobs"])) if not top_perf.empty else "0", note)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">Quick Actions</div>', unsafe_allow_html=True)
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        if st.button("Create Job Card", use_container_width=True):
            set_page("Service Jobs")
    with q2:
        if st.button("Create Invoice", use_container_width=True):
            set_page("Invoices")
    with q3:
        if st.button("Open Reports", use_container_width=True):
            set_page("Reports")
    with q4:
        if st.button("Search Records", use_container_width=True):
            set_page("Global Search")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    left, right = st.columns([1.1, 1])
    with left:
        st.markdown("<div class=\"section-title\">Today's Technician Performance</div>", unsafe_allow_html=True)
        perf = summary["technician_perf"]
        if perf is not None and not perf.empty:
            st.dataframe(perf.head(10), use_container_width=True, hide_index=True)
        else:
            st.info("No job cards recorded today.")
    with right:
        st.markdown('<div class="section-title">Workflow Notes</div>', unsafe_allow_html=True)
        st.success("Google Sheet only architecture is active.")
        st.info("Heavy pages use a show button before loading data.")
        st.info("Login reads only the Employees sheet.")
        st.info("Cache clears automatically after save, update, or delete.")


# ------------------------------ ATTENDANCE ------------------------------
def record_attendance(status: str, user: dict, latitude: str = "", longitude: str = "", distance: str = "", selfie_saved: str = "No") -> tuple[bool, str]:
    row = {
        "Date": today_str(),
        "Time": now_time_str(),
        "User ID": user.get("user_id", ""),
        "Technician Name": user.get("name", ""),
        "Role": user.get("role", ""),
        "Attendance Status": status,
        "Latitude": latitude,
        "Longitude": longitude,
        "Distance Meter": distance,
        "Selfie Saved": selfie_saved,
    }
    ok, msg = append_row("attendance", row, SHEET_SCHEMAS["attendance"])
    return ok, msg


def render_attendance(user: dict) -> None:
    st.markdown('<div class="section-title">Attendance Module</div>', unsafe_allow_html=True)
    st.caption("Check-in / Check-out, monthly view and PDF export.")

    geo = {"latitude": "", "longitude": "", "distance": ""}
    try:
        from streamlit_js_eval import get_geolocation
        loc = get_geolocation()
        if loc and isinstance(loc, dict):
            lat = loc.get("coords", {}).get("latitude")
            lon = loc.get("coords", {}).get("longitude")
            if lat is not None and lon is not None:
                geo["latitude"] = str(lat)
                geo["longitude"] = str(lon)
                geo["distance"] = str(int(haversine_meters(COMPANY_LAT, COMPANY_LON, lat, lon)))
    except Exception:
        pass

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Check In", use_container_width=True):
            dist = to_float(geo["distance"], 0.0)
            if geo["distance"] and dist > ALLOWED_RADIUS_M:
                st.error("Outside allowed location radius. Attendance blocked.")
            else:
                show_loader("Recording Attendance", "Saving check-in", 0.9)
                ok, msg = record_attendance("Check In", user, geo["latitude"], geo["longitude"], geo["distance"], "No")
                if ok:
                    st.success("Check-in saved.")
                else:
                    st.error(msg)
    with c2:
        if st.button("Check Out", use_container_width=True):
            show_loader("Recording Attendance", "Saving check-out", 0.9)
            ok, msg = record_attendance("Check Out", user, geo["latitude"], geo["longitude"], geo["distance"], "No")
            if ok:
                st.success("Check-out saved.")
            else:
                st.error(msg)
    with c3:
        if st.button("Load Monthly Attendance", use_container_width=True):
            st.session_state.load_attendance = True

    st.info(f"Current location distance from showroom: {geo['distance'] or 'N/A'} meters")

    if st.session_state.get("load_attendance"):
        att = show_loader_and_read("attendance", SHEET_SCHEMAS["attendance"], "Loading attendance", "Reading attendance sheet")
        month_value = st.date_input("Attendance month filter", value=date.today())
        month_prefix = month_value.strftime("%Y-%m")
        att = att[att["Date"].astype(str).str.startswith(month_prefix)].copy() if not att.empty else att
        display_df(att.sort_values(["Date", "Time"], ascending=False), 420)
        if not att.empty:
            file_name = Path("generated_reports/attendance_report.pdf")
            file_name.parent.mkdir(exist_ok=True)
            attendance_pdf(file_name, att, title=f"Attendance Report ({month_prefix})")
            st.download_button("Download Attendance PDF", data=file_name.read_bytes(), file_name=file_name.name, use_container_width=True)


# ------------------------------ SERVICE JOBS ------------------------------
def service_jobs_defaults() -> dict:
    return {
        "Job Card Number": make_id("JC"),
        "Date": today_str(),
        "Time": now_time_str(),
        "Customer Name": "",
        "Mobile Number": "",
        "Registration Number": "",
        "Bike Model": "",
        "Service Type": "General Service",
        "Complaint": "",
        "Advisor Name": "",
        "Technician Name": "",
        "Status": "Open",
        "Estimate Amount": "0",
        "Odometer": "",
        "Promised Date": "",
        "Closed On": "",
    }


def save_customer_vehicle(customer: str, mobile: str, reg: str, model: str) -> None:
    customer = safe_str(customer)
    mobile = safe_str(mobile)
    reg = safe_str(reg)
    model = safe_str(model)
    if customer and mobile:
        customers = read_sheet("customers", SHEET_SCHEMAS["customers"])
        if customers.empty or not ((customers["Mobile Number"].astype(str) == mobile) | (customers["Customer Name"].astype(str) == customer)).any():
            append_row("customers", {
                "Customer ID": make_id("CUS"),
                "Customer Name": customer,
                "Mobile Number": mobile,
                "Address": "",
                "Created On": today_str(),
                "Last Visit": today_str(),
            }, SHEET_SCHEMAS["customers"])
        else:
            customers.loc[customers["Mobile Number"].astype(str) == mobile, "Last Visit"] = today_str()
            update_sheet("customers", customers, SHEET_SCHEMAS["customers"])
    if reg:
        vehicles = read_sheet("vehicles", SHEET_SCHEMAS["vehicles"])
        if vehicles.empty or not (vehicles["Registration Number"].astype(str) == reg).any():
            append_row("vehicles", {
                "Vehicle ID": make_id("VEH"),
                "Customer Name": customer,
                "Mobile Number": mobile,
                "Registration Number": reg,
                "Bike Model": model,
                "Chassis No": "",
                "Engine No": "",
                "Created On": today_str(),
                "Last Visit": today_str(),
            }, SHEET_SCHEMAS["vehicles"])
        else:
            vehicles.loc[vehicles["Registration Number"].astype(str) == reg, "Last Visit"] = today_str()
            update_sheet("vehicles", vehicles, SHEET_SCHEMAS["vehicles"])


def render_service_jobs(user: dict) -> None:
    st.markdown('<div class="section-title">Service Job Card Entry</div>', unsafe_allow_html=True)
    st.session_state.setdefault("service_job_default", make_id("JC"))
    st.caption("Open a job card, assign advisor/technician and track status.")
    if st.button("Load Job Cards", use_container_width=True):
        st.session_state.load_jobs = True

    if st.session_state.get("load_jobs"):
        jobs = show_loader_and_read("service_jobs", SHEET_SCHEMAS["service_jobs"], "Loading job cards", "Reading job sheet")
        display_df(jobs.sort_values("Date", ascending=False), 350)

    with st.form("service_job_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            job_card = st.text_input("Job Card Number", value=st.session_state.get("service_job_default", make_id("JC")))
            customer = st.text_input("Customer Name")
            mobile = st.text_input("Mobile Number")
            reg = st.text_input("Registration Number")
        with c2:
            model = st.text_input("Bike Model")
            service_type = st.selectbox("Service Type", ["General Service", "Periodic Service", "Accident Repair", "Warranty", "Free Service", "Other"])
            advisor = st.text_input("Advisor Name", value=user.get("name", ""))
            technician = st.text_input("Technician Name")
        with c3:
            status = st.selectbox("Status", ["Open", "In Progress", "Waiting Parts", "Completed", "Delivered"])
            estimate = st.text_input("Estimate Amount", value="0")
            odometer = st.text_input("Odometer")
            promised = st.date_input("Promised Date")
        complaint = st.text_area("Complaint / Work Notes", height=110)
        submitted = st.form_submit_button("Save Job Card")
        if submitted:
            row = {
                "Job Card Number": job_card,
                "Date": today_str(),
                "Time": now_time_str(),
                "Customer Name": customer,
                "Mobile Number": mobile,
                "Registration Number": reg,
                "Bike Model": model,
                "Service Type": service_type,
                "Complaint": complaint,
                "Advisor Name": advisor,
                "Technician Name": technician,
                "Status": status,
                "Estimate Amount": estimate,
                "Odometer": odometer,
                "Promised Date": str(promised),
                "Closed On": today_str() if status in {"Completed", "Delivered"} else "",
            }
            show_loader("Saving Job Card", "Writing to Google Sheet", 0.9)
            ok, msg = append_row("service_jobs", row, SHEET_SCHEMAS["service_jobs"])
            if ok:
                save_customer_vehicle(customer, mobile, reg, model)
                st.session_state["service_job_default"] = make_id("JC")
                st.success("Job card saved.")
            else:
                st.error(msg)


# ------------------------------ INVOICES ------------------------------
def render_invoices(user: dict) -> None:
    st.markdown('<div class="section-title">Invoice Entry</div>', unsafe_allow_html=True)
    prefill = st.session_state.get("ocr_fill", {}) or {}
    st.session_state.setdefault("invoice_number_default", prefill.get("invoice_number", make_id("INV")))
    st.caption("GST-ready billing with spare parts, oil, labour and other charges.")
    if st.button("Load Invoice Records", use_container_width=True):
        st.session_state.load_invoices = True

    if st.session_state.get("load_invoices"):
        invoices = show_loader_and_read("invoices", SHEET_SCHEMAS["invoices"], "Loading invoices", "Reading invoice sheet")
        display_df(invoices.sort_values("Date", ascending=False), 340)

    with st.form("invoice_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            invoice_no = st.text_input("Invoice Number", value=st.session_state.get("invoice_number_default", make_id("INV")))
            job_card = st.text_input("Job Card Number", value=safe_str(prefill.get("job_card_number", "")))
            customer = st.text_input("Customer Name", value=safe_str(prefill.get("customer_name", "")))
            mobile = st.text_input("Mobile Number", value=safe_str(prefill.get("mobile_number", "")))
        with c2:
            reg = st.text_input("Registration Number", value=safe_str(prefill.get("registration_number", "")))
            model = st.text_input("Bike Model", value=safe_str(prefill.get("bike_model", "")))
            service_type = st.text_input("Service Type", value="General Service")
            technician = st.text_input("Technician Name", value=user.get("name", ""))
        with c3:
            spare = st.number_input("Spare Amount", min_value=0.0, step=50.0)
            oil = st.number_input("Oil Amount", min_value=0.0, step=50.0)
            labour = st.number_input("Labour Amount", min_value=0.0, step=50.0)
            other = st.number_input("Other Charges", min_value=0.0, step=50.0)
        gst_pct = st.number_input("GST %", min_value=0.0, step=0.5, value=0.0)
        status = st.selectbox("Status", ["Billed", "Paid", "Pending", "Cancelled"])
        submitted = st.form_submit_button("Save Invoice")

        if submitted:
            totals = compute_grand_total(spare=spare, oil=oil, labour=labour, other=other, gst_percent=gst_pct)
            row = {
                "Entry ID": make_id("ENT"),
                "Date": today_str(),
                "Technician Name": technician,
                "User ID": user.get("user_id", ""),
                "Invoice Number": invoice_no,
                "Job Card Number": job_card,
                "Registration Number": reg,
                "Bike Model": model,
                "Service Type": service_type,
                "Labour Amount": f"{totals['labour']:.2f}",
                "Spare Parts Count": "0",
                "Spare Amount": f"{totals['spare']:.2f}",
                "Oil Change Status": "Yes" if totals["oil"] > 0 else "No",
                "Total Amount": f"{totals['grand_total']:.2f}",
                "Entry Type": "Manual",
                "Status": status,
            }
            show_loader("Saving Invoice", "Writing invoice to Google Sheet", 0.9)
            ok, msg = append_row("invoices", row, SHEET_SCHEMAS["invoices"])
            if ok:
                bill_row = {
                    "Invoice Number": invoice_no,
                    "Date": today_str(),
                    "Time": now_time_str(),
                    "Customer Name": customer,
                    "Mobile Number": mobile,
                    "Registration Number": reg,
                    "Bike Model": model,
                    "Job Card Number": job_card,
                    "Spare Amount": f"{totals['spare']:.2f}",
                    "Oil Amount": f"{totals['oil']:.2f}",
                    "Labour Amount": f"{totals['labour']:.2f}",
                    "Other Charges": f"{totals['other']:.2f}",
                    "GST %": f"{gst_pct:.2f}",
                    "Grand Total": f"{totals['grand_total']:.2f}",
                    "Entry Type": "Invoice",
                    "Status": status,
                }
                append_row("billing_records", bill_row, SHEET_SCHEMAS["billing_records"])
                st.success("Invoice saved.")
                st.session_state["ocr_fill"] = {}
                st.session_state["invoice_number_default"] = make_id("INV")
                pdf_path = Path("generated_reports")
                pdf_path.mkdir(exist_ok=True)
                pdf_file = pdf_path / f"{invoice_no}.pdf"
                invoice_pdf(pdf_file, {
                    "Invoice Number": invoice_no,
                    "Job Card Number": job_card,
                    "Customer Name": customer,
                    "Mobile Number": mobile,
                    "Registration Number": reg,
                    "Bike Model": model,
                    "Date": today_str(),
                    "Spare Amount": totals["spare"],
                    "Oil Amount": totals["oil"],
                    "Labour Amount": totals["labour"],
                    "Other Charges": totals["other"],
                    "Grand Total": totals["grand_total"],
                })
                st.download_button("Download Invoice PDF", data=pdf_file.read_bytes(), file_name=pdf_file.name, use_container_width=True)
            else:
                st.error(msg)


# ------------------------------ MANUAL BILL ------------------------------
def render_manual_bill(user: dict) -> None:
    st.markdown('<div class="section-title">Manual Bill</div>', unsafe_allow_html=True)
    prefill = st.session_state.get("ocr_fill", {}) or {}
    st.session_state.setdefault("manual_bill_default", make_id("MB"))
    st.caption("Professional printable bill layout with GST support.")
    with st.form("manual_bill_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            bill_id = st.text_input("Manual Bill ID", value=st.session_state.get("manual_bill_default", make_id("MB")))
            customer = st.text_input("Customer Name", value=safe_str(prefill.get("customer_name", "")))
            mobile = st.text_input("Mobile Number", value=safe_str(prefill.get("mobile_number", "")))
            reg = st.text_input("Registration Number", value=safe_str(prefill.get("registration_number", "")))
        with c2:
            model = st.text_input("Bike Model", value=safe_str(prefill.get("bike_model", "")))
            service_type = st.text_input("Service Type", value="General Service")
            technician = st.text_input("Technician Name", value=user.get("name", ""))
            job_card = st.text_input("Job Card Number", value=safe_str(prefill.get("job_card_number", "")))
        with c3:
            spare = st.number_input("Spare Amount", min_value=0.0, step=50.0)
            oil = st.number_input("Oil Amount", min_value=0.0, step=50.0)
            labour = st.number_input("Labour Amount", min_value=0.0, step=50.0)
            other = st.number_input("Other Charges", min_value=0.0, step=50.0)
        gst_pct = st.number_input("GST %", min_value=0.0, step=0.5, value=0.0)
        submitted = st.form_submit_button("Create Manual Bill")
        if submitted:
            totals = compute_grand_total(spare=spare, oil=oil, labour=labour, other=other, gst_percent=gst_pct)
            row = {
                "Manual Bill ID": bill_id,
                "Date": today_str(),
                "Technician Name": technician,
                "User ID": user.get("user_id", ""),
                "Customer Name": customer,
                "Mobile Number": mobile,
                "Registration Number": reg,
                "Bike Model": model,
                "Service Type": service_type,
                "Labour Amount": f"{labour:.2f}",
                "Spare Parts Count": "0",
                "Oil Amount": f"{oil:.2f}",
                "Other Charges": f"{other:.2f}",
                "GST %": f"{gst_pct:.2f}",
                "Grand Total": f"{totals['grand_total']:.2f}",
                "PDF File": "",
                "Status": "Created",
            }
            show_loader("Generating Bill", "Preparing printable PDF", 1.0)
            ok, msg = append_row("manual_invoices", row, SHEET_SCHEMAS["manual_invoices"])
            if ok:
                st.session_state["manual_bill_default"] = make_id("MB")
                pdf_dir = Path("generated_reports")
                pdf_dir.mkdir(exist_ok=True)
                pdf_file = pdf_dir / f"{bill_id}.pdf"
                invoice_pdf(pdf_file, {
                    "Invoice Number": bill_id,
                    "Customer Name": customer,
                    "Mobile Number": mobile,
                    "Registration Number": reg,
                    "Bike Model": model,
                    "Job Card Number": job_card,
                    "Date": today_str(),
                    "Spare Amount": totals["spare"],
                    "Oil Amount": totals["oil"],
                    "Labour Amount": totals["labour"],
                    "Other Charges": totals["other"],
                    "Grand Total": totals["grand_total"],
                })
                st.success("Manual bill created.")
                st.download_button("Download Bill PDF", data=pdf_file.read_bytes(), file_name=pdf_file.name, use_container_width=True)
            else:
                st.error(msg)


# ------------------------------ OCR ------------------------------
def render_ocr(user: dict) -> None:
    st.markdown('<div class="section-title">OCR Invoice Upload</div>', unsafe_allow_html=True)
    st.caption("Upload a PDF/image invoice. OCR will try to pre-fill billing fields.")
    uploaded = st.file_uploader("Upload invoice PDF/image", type=["pdf", "png", "jpg", "jpeg"])
    if uploaded and st.button("Extract and Parse", use_container_width=True):
        show_loader("Running OCR", "Extracting invoice details", 1.1)
        text, parsed = load_and_parse(uploaded)
        st.session_state.ocr_parsed = parsed
        st.session_state.ocr_text = text
    parsed = st.session_state.get("ocr_parsed", {})
    if parsed:
        st.success("OCR extraction complete.")
        st.json(parsed, expanded=False)
        if st.button("Use extracted data in invoice form", use_container_width=True):
            st.session_state.ocr_fill = parsed
            st.success("Extracted values are ready for invoice entry.")
    if st.session_state.get("ocr_fill"):
        st.info("Open Invoice Entry to use the parsed values automatically.")
        st.write(st.session_state["ocr_fill"])


# ------------------------------ CUSTOMER HISTORY ------------------------------
def render_customer_history(user: dict) -> None:
    st.markdown('<div class="section-title">Customer / Vehicle History</div>', unsafe_allow_html=True)
    st.caption("Search customer, mobile number, vehicle number or invoice references.")
    if st.button("Load History Data", use_container_width=True):
        st.session_state.load_history = True

    if st.session_state.get("load_history"):
        service = show_loader_and_read("service_jobs", SHEET_SCHEMAS["service_jobs"], "Loading history", "Reading service jobs")
        invoices = read_sheet("invoices", SHEET_SCHEMAS["invoices"])
        manual = read_sheet("manual_invoices", SHEET_SCHEMAS["manual_invoices"])
        customers = read_sheet("customers", SHEET_SCHEMAS["customers"])
        vehicles = read_sheet("vehicles", SHEET_SCHEMAS["vehicles"])

        q = st.text_input("Search")
        if q:
            result = []
            for name, df, cols in [
                ("Service Jobs", service, ["Customer Name", "Mobile Number", "Registration Number", "Bike Model", "Job Card Number"]),
                ("Invoices", invoices, ["Invoice Number", "Registration Number", "Bike Model", "Job Card Number"]),
                ("Manual Bills", manual, ["Customer Name", "Mobile Number", "Registration Number", "Bike Model", "Manual Bill ID"]),
                ("Customers", customers, ["Customer Name", "Mobile Number"]),
                ("Vehicles", vehicles, ["Registration Number", "Bike Model", "Mobile Number"]),
            ]:
                found = filter_contains(df, cols, q)
                if not found.empty:
                    found = found.copy()
                    found.insert(0, "Source", name)
                    result.append(found)
            if result:
                merged = pd.concat(result, ignore_index=True, sort=False)
                display_df(merged, 450)
            else:
                st.info("No matching history found.")


# ------------------------------ TECHNICIAN ------------------------------
def render_technician(user: dict) -> None:
    st.markdown('<div class="section-title">Technician Module</div>', unsafe_allow_html=True)
    st.caption("Track technician assignments, work summary and performance.")
    jobs = read_sheet("service_jobs", SHEET_SCHEMAS["service_jobs"])
    att = read_sheet("attendance", SHEET_SCHEMAS["attendance"])

    if jobs.empty:
        st.info("No job cards available yet.")
        return

    if "Technician Name" in jobs.columns:
        summary = jobs.groupby("Technician Name").agg(
            Jobs=("Job Card Number", "count") if "Job Card Number" in jobs.columns else ("Technician Name", "count")
        ).reset_index().sort_values("Jobs", ascending=False)
        st.dataframe(summary, use_container_width=True, hide_index=True)

    tech_name = st.selectbox("Technician filter", ["All"] + [x for x in jobs["Technician Name"].dropna().astype(str).unique().tolist() if x.strip()])
    df = jobs.copy()
    if tech_name != "All":
        df = df[df["Technician Name"].astype(str) == tech_name]

    display_df(df.sort_values("Date", ascending=False), 360)

    if st.button("Generate Technician Report PDF", use_container_width=True):
        pdf_dir = Path("generated_reports")
        pdf_dir.mkdir(exist_ok=True)
        pdf_file = pdf_dir / f"technician_report_{today_str()}.pdf"
        summary_rows = []
        if tech_name == "All":
            for _, r in summary.head(10).iterrows():
                summary_rows.append([str(r["Technician Name"]), str(r["Jobs"])])
        else:
            summary_rows.append(["Technician", tech_name])
            summary_rows.append(["Jobs", str(df.shape[0])])
        report_pdf(pdf_file, "Technician Report", summary_rows, detail_df=df.head(25))
        st.download_button("Download Technician PDF", data=pdf_file.read_bytes(), file_name=pdf_file.name, use_container_width=True)


# ------------------------------ REPORTS ------------------------------
def render_reports(user: dict) -> None:
    st.markdown('<div class="section-title">Reports</div>', unsafe_allow_html=True)
    st.caption("Daily, monthly, revenue, attendance, service and technician reports.")
    report_type = st.selectbox("Report type", ["Daily Report", "Monthly Report", "Revenue Report", "Attendance Report", "Service Report", "Technician Report"])
    dt = st.date_input("Report date", value=date.today())
    if st.button("Generate Report", use_container_width=True):
        show_loader("Generating Report", "Reading required sheets only", 1.0)
        pdf_dir = Path("generated_reports")
        pdf_dir.mkdir(exist_ok=True)
        out = pdf_dir / f"{report_type.replace(' ', '_').lower()}_{dt}.pdf"

        if report_type == "Daily Report":
            inv = df_today(read_sheet("invoices", SHEET_SCHEMAS["invoices"]))
            service = df_today(read_sheet("service_jobs", SHEET_SCHEMAS["service_jobs"]))
            att = df_today(read_sheet("attendance", SHEET_SCHEMAS["attendance"]))
            summary = [
                ["Today's Invoices", str(inv.shape[0])],
                ["Today's Service Jobs", str(service.shape[0])],
                ["Today's Attendance", str(att.shape[0])],
                ["Today's Revenue", money(today_revenue())],
            ]
            report_pdf(out, "Daily Report", summary, detail_df=service.head(20))
            st.download_button("Download PDF", data=out.read_bytes(), file_name=out.name, use_container_width=True)

        elif report_type == "Monthly Report":
            prefix = dt.strftime("%Y-%m")
            service = read_sheet("service_jobs", SHEET_SCHEMAS["service_jobs"])
            inv = read_sheet("invoices", SHEET_SCHEMAS["invoices"])
            service_m = service[service["Date"].astype(str).str.startswith(prefix)].copy() if not service.empty else service
            inv_m = inv[inv["Date"].astype(str).str.startswith(prefix)].copy() if not inv.empty else inv
            summary = [
                ["Month", prefix],
                ["Service Jobs", str(service_m.shape[0])],
                ["Invoices", str(inv_m.shape[0])],
                ["Revenue", money(inv_m["Total Amount"].map(to_float).sum() if not inv_m.empty and "Total Amount" in inv_m.columns else 0)],
            ]
            report_pdf(out, "Monthly Report", summary, detail_df=service_m.head(20))
            st.download_button("Download PDF", data=out.read_bytes(), file_name=out.name, use_container_width=True)

        elif report_type == "Revenue Report":
            inv = read_sheet("invoices", SHEET_SCHEMAS["invoices"])
            manual = read_sheet("manual_invoices", SHEET_SCHEMAS["manual_invoices"])
            total = 0.0
            if not inv.empty and "Total Amount" in inv.columns:
                total += inv["Total Amount"].map(to_float).sum()
            if not manual.empty and "Grand Total" in manual.columns:
                total += manual["Grand Total"].map(to_float).sum()
            summary = [["Total Revenue", money(total)], ["Invoices", str(inv.shape[0])], ["Manual Bills", str(manual.shape[0])]]
            report_pdf(out, "Revenue Report", summary, detail_df=inv.head(20))
            st.download_button("Download PDF", data=out.read_bytes(), file_name=out.name, use_container_width=True)

        elif report_type == "Attendance Report":
            att = read_sheet("attendance", SHEET_SCHEMAS["attendance"])
            month_prefix = dt.strftime("%Y-%m")
            att = att[att["Date"].astype(str).str.startswith(month_prefix)].copy() if not att.empty else att
            summary = [["Month", month_prefix], ["Attendance Records", str(att.shape[0])]]
            attendance_pdf(out, att, title="Attendance Report")
            st.download_button("Download PDF", data=out.read_bytes(), file_name=out.name, use_container_width=True)

        elif report_type == "Service Report":
            service = read_sheet("service_jobs", SHEET_SCHEMAS["service_jobs"])
            prefix = dt.strftime("%Y-%m")
            service_m = service[service["Date"].astype(str).str.startswith(prefix)].copy() if not service.empty else service
            summary = [["Month", prefix], ["Jobs", str(service_m.shape[0])]]
            report_pdf(out, "Service Report", summary, detail_df=service_m.head(20))
            st.download_button("Download PDF", data=out.read_bytes(), file_name=out.name, use_container_width=True)

        elif report_type == "Technician Report":
            service = read_sheet("service_jobs", SHEET_SCHEMAS["service_jobs"])
            if not service.empty and "Technician Name" in service.columns:
                grouped = service.groupby("Technician Name").size().reset_index(name="Jobs").sort_values("Jobs", ascending=False)
            else:
                grouped = pd.DataFrame(columns=["Technician Name", "Jobs"])
            summary = [["Month", dt.strftime("%Y-%m")], ["Technicians", str(grouped.shape[0])]]
            report_pdf(out, "Technician Report", summary, detail_df=grouped.head(20))
            st.download_button("Download PDF", data=out.read_bytes(), file_name=out.name, use_container_width=True)


# ------------------------------ GLOBAL SEARCH ------------------------------
def render_global_search(user: dict) -> None:
    st.markdown('<div class="section-title">Global Search</div>', unsafe_allow_html=True)
    st.caption("Search by customer, mobile number, vehicle number, invoice number or job card number.")
    term = st.text_input("Search term")
    if st.button("Show Results", use_container_width=True):
        show_loader("Searching", "Reading required sheets only", 0.9)
        data_sets = [
            ("Service Jobs", read_sheet("service_jobs", SHEET_SCHEMAS["service_jobs"]), ["Customer Name", "Mobile Number", "Registration Number", "Bike Model", "Job Card Number"]),
            ("Invoices", read_sheet("invoices", SHEET_SCHEMAS["invoices"]), ["Invoice Number", "Registration Number", "Bike Model", "Job Card Number"]),
            ("Manual Bills", read_sheet("manual_invoices", SHEET_SCHEMAS["manual_invoices"]), ["Customer Name", "Mobile Number", "Registration Number", "Bike Model", "Manual Bill ID"]),
            ("Customers", read_sheet("customers", SHEET_SCHEMAS["customers"]), ["Customer Name", "Mobile Number"]),
            ("Vehicles", read_sheet("vehicles", SHEET_SCHEMAS["vehicles"]), ["Registration Number", "Bike Model", "Mobile Number"]),
        ]
        results = []
        for source, df, cols in data_sets:
            found = filter_contains(df, cols, term)
            if not found.empty:
                found = found.copy()
                found.insert(0, "Source", source)
                results.append(found)
        if results:
            merged = pd.concat(results, ignore_index=True, sort=False)
            display_df(merged, 460)
        else:
            st.info("No results found.")


# ------------------------------ DUPLICATES ------------------------------
def render_duplicates(user: dict) -> None:
    st.markdown('<div class="section-title">Duplicate Check</div>', unsafe_allow_html=True)
    st.caption("Detect duplicate vehicle numbers, invoices and customers.")
    if st.button("Check Duplicates", use_container_width=True):
        show_loader("Checking Duplicates", "Reading required sheets only", 0.9)
        service = read_sheet("service_jobs", SHEET_SCHEMAS["service_jobs"])
        invoices = read_sheet("invoices", SHEET_SCHEMAS["invoices"])
        manual = read_sheet("manual_invoices", SHEET_SCHEMAS["manual_invoices"])
        customers = read_sheet("customers", SHEET_SCHEMAS["customers"])

        dup_service = detect_duplicates(service, ["Registration Number"])
        dup_inv = detect_duplicates(invoices, ["Invoice Number"])
        dup_manual = detect_duplicates(manual, ["Manual Bill ID"])
        dup_cust = detect_duplicates(customers, ["Customer Name", "Mobile Number"])

        st.write("### Duplicate Vehicles")
        display_df(dup_service, 240)
        st.write("### Duplicate Invoices")
        display_df(dup_inv, 240)
        st.write("### Duplicate Manual Bills")
        display_df(dup_manual, 240)
        st.write("### Duplicate Customers")
        display_df(dup_cust, 240)


# ------------------------------ SETTINGS ------------------------------
def settings_to_df() -> pd.DataFrame:
    return read_sheet("settings", SHEET_SCHEMAS["settings"])


def settings_value(key: str, default: str = "") -> str:
    df = settings_to_df()
    if df.empty or "Key" not in df.columns or "Value" not in df.columns:
        return default
    match = df[df["Key"].astype(str) == key]
    if match.empty:
        return default
    return safe_str(match.iloc[0]["Value"])


def upsert_setting(key: str, value: str) -> None:
    df = settings_to_df()
    if df.empty:
        df = pd.DataFrame(columns=SHEET_SCHEMAS["settings"])
    if "Key" not in df.columns:
        df["Key"] = ""
    if "Value" not in df.columns:
        df["Value"] = ""
    if (df["Key"].astype(str) == key).any():
        df.loc[df["Key"].astype(str) == key, "Value"] = value
    else:
        df = pd.concat([df, pd.DataFrame([{"Key": key, "Value": value}])], ignore_index=True)
    update_sheet("settings", df, SHEET_SCHEMAS["settings"])


def render_settings(user: dict) -> None:
    st.markdown('<div class="section-title">Settings</div>', unsafe_allow_html=True)
    st.caption("Manage show details and stored configuration values.")
    company_name = st.text_input("Company Name", value=settings_value("Company Name", APP_NAME))
    show_code = st.text_input("Showroom Code", value=settings_value("Showroom Code", "SELVA"))
    radius = st.number_input("Allowed Attendance Radius (meters)", min_value=50, max_value=5000, value=int(float(settings_value("Allowed Radius", str(ALLOWED_RADIUS_M)))), step=10)
    if st.button("Save Settings", use_container_width=True):
        upsert_setting("Company Name", company_name)
        upsert_setting("Showroom Code", show_code)
        upsert_setting("Allowed Radius", str(radius))
        clear_sheet_cache()
        st.success("Settings saved.")


# ------------------------------ ROUTER ------------------------------
def render_page(page: str, user: dict) -> None:
    if page == "Dashboard":
        render_dashboard(user)
    elif page == "Attendance":
        render_attendance(user)
    elif page == "Service Jobs":
        render_service_jobs(user)
    elif page == "Invoices":
        render_invoices(user)
    elif page == "Manual Bill":
        render_manual_bill(user)
    elif page == "OCR Upload":
        render_ocr(user)
    elif page == "Customer History":
        render_customer_history(user)
    elif page == "Technician":
        render_technician(user)
    elif page == "Reports":
        render_reports(user)
    elif page == "Global Search":
        render_global_search(user)
    elif page == "Duplicate Check":
        render_duplicates(user)
    elif page == "Settings":
        render_settings(user)
    else:
        render_dashboard(user)


def main() -> None:
    init_state()
    inject_css()

    if not st.session_state.authenticated:
        login_screen()
        return

    user = st.session_state.user
    sidebar_nav(user)
    render_topbar(user)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    render_page(st.session_state.page, user)


if __name__ == "__main__":
    main()
