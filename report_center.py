"""On-demand, role-aware SELVA MOTORS monthly reports dashboard."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import re
import time
from typing import Callable

import pandas as pd
import streamlit as st

from pdf_generator import format_inr, generate_professional_report_pdf
from report_engine import (
    REPORT_COLUMNS,
    build_monthly_bundle,
    calculate_expense_totals,
    calculate_missing_jobcards,
    create_excel_report,
    create_missing_jobcard_workbook,
    technician_detail,
    build_daily_business_report,
    build_technician_daily_report,
    build_individual_monthly_report,
    create_single_report_workbook,
)

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
ATTENDANCE_COLUMNS = [
    "Date", "Time", "User ID", "Technician Name", "Role",
    "Attendance Status", "Distance Meter", "Selfie Saved",
]
# Daily screens read only identifiers and values needed for that daily report.
# Entry ID is included only as a safe deduplication key for rows without a Job Card Number.
DAILY_REPORT_COLUMNS = [
    "Entry ID", "Date", "Technician Name", "User ID", "Job Card Number",
    "Registration Number", "Service Type", "Labour Amount", "Spare Parts Count",
    "Spare Amount", "Oil Change Status", "Oil Amount", "Total Amount", "Status",
]


def _currency(value: object) -> str:
    return format_inr(float(value or 0))


def _progress_callback(bar, message_slot):
    started = time.perf_counter()
    def update(stage: str, percent: int, processed: int, total: int, remaining: float | None):
        elapsed = time.perf_counter() - started
        label = f"{stage} · {percent}% · Elapsed: {elapsed:.1f} sec"
        if total:
            count_label = "Sequence numbers checked" if "Sequence" in stage else "Records processed"
            label += f" · {count_label}: {processed:,} / {total:,}"
        if remaining is not None and remaining >= 1:
            label += f" · Estimated remaining: {remaining:.0f} sec"
        elif remaining is not None:
            label += " · Almost complete"
        bar.progress(percent, text=label)
        message_slot.caption(label)
    return update


def _filter_technician_scope(source: pd.DataFrame, is_technician: bool, user_id: str, employee_name: str) -> pd.DataFrame:
    if not is_technician:
        return source.copy()
    if "User ID" in source.columns and str(user_id).strip():
        return source[source["User ID"].astype(str).str.strip().str.casefold() == str(user_id).strip().casefold()].copy()
    if "Technician Name" in source.columns and str(employee_name).strip():
        return source[source["Technician Name"].astype(str).str.strip().str.casefold() == str(employee_name).strip().casefold()].copy()
    return source.iloc[0:0].copy()


def _expense_rows_from_widgets(state_key: str, rows: list[dict]) -> list[dict]:
    result = []
    for row in rows:
        row_id = row["id"]
        result.append({
            "id": row_id,
            "name": str(st.session_state.get(f"{state_key}_name_{row_id}", row.get("name", "")) or ""),
            "amount": float(st.session_state.get(f"{state_key}_amount_{row_id}", row.get("amount", 0)) or 0),
            "description": str(st.session_state.get(f"{state_key}_description_{row_id}", row.get("description", "")) or ""),
        })
    return result


def _show_attendance_report(
    read_report_sheet: Callable[..., pd.DataFrame],
    today_str: Callable[[], str],
    pdf_dir: Path,
    *, is_admin: bool, is_manager: bool, is_technician: bool, is_prathisha: bool,
    user_id: str, employee_name: str,
) -> None:
    st.subheader("Monthly Attendance Report")
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    c1, c2, c3 = st.columns([1, 1, 1.4])
    month = c1.selectbox("Attendance Month", range(1, 13), index=now.month - 1, format_func=lambda x: MONTH_NAMES[x - 1], key="report_attendance_month_select")
    year = c2.selectbox("Attendance Year", list(range(max(2000, now.year - 10), now.year + 2)), index=list(range(max(2000, now.year - 10), now.year + 2)).index(now.year), key="report_attendance_year_select")
    if is_technician or is_prathisha:
        selected_user = "My Records"
        st.info("Your role is limited to your own attendance records.")
    else:
        scope = c3.radio("User Scope", ["All Users", "Particular User"], horizontal=True, key="report_attendance_scope_new")
        selected_user = st.text_input("User ID or Employee Name", key="report_attendance_user_new").strip() if scope == "Particular User" else "All Users"
    fresh = st.checkbox("Read fresh attendance data from Google Sheets", value=False, key="report_attendance_fresh_new")
    signature = f"{month:02d}-{year}|{selected_user}"
    if st.button("GENERATE ATTENDANCE REPORT", type="primary", use_container_width=True, key="generate_attendance_report_new"):
        try:
            loading = st.empty()
            loading.info("Reading approved attendance columns from Google Sheets...")
            source = read_report_sheet("attendance", force_refresh=fresh, columns=ATTENDANCE_COLUMNS)
            loading.empty()
            if is_technician or is_prathisha:
                if "User ID" in source:
                    source = source[source["User ID"].astype(str).str.strip().str.casefold() == str(user_id).strip().casefold()]
                else:
                    source = source.iloc[0:0]
            if "Date" in source:
                parsed = pd.to_datetime(source["Date"].astype(str).str.replace("/", "-", regex=False), dayfirst=True, errors="coerce")
                source = source[(parsed.dt.month == month) & (parsed.dt.year == year)].copy()
            else:
                source = source.iloc[0:0].copy()
            if selected_user != "All Users" and selected_user != "My Records":
                term = selected_user.casefold()
                name = source.get("Technician Name", pd.Series(index=source.index, dtype=str)).astype(str).str.casefold() == term
                uid = source.get("User ID", pd.Series(index=source.index, dtype=str)).astype(str).str.casefold() == term
                source = source[name | uid]
            status = source.get("Attendance Status", pd.Series(dtype=str)).astype(str).str.strip().str.lower()
            kpis = [
                ("Present", int((status == "present").sum())),
                ("Absent", int((status == "absent").sum())),
                ("Half Day", int(status.isin(["half day", "half-day", "halfday"]).sum())),
                ("Total Records", len(source)),
            ]
            pdf_dir.mkdir(exist_ok=True)
            path = pdf_dir / f"selva_motors_attendance_{month:02d}_{year}_{int(time.time())}.pdf"
            path = generate_professional_report_pdf(
                source, "SELVA MOTORS • MONTHLY ATTENDANCE REPORT", path,
                metadata={"Month": f"{month:02d}-{year}", "User": selected_user},
                kpis=kpis,
                columns=[c for c in ATTENDANCE_COLUMNS if c in source.columns],
                report_kind="attendance",
            )
            st.session_state["_report_attendance_result_new"] = {"signature": signature, "frame": source, "pdf_path": path, "kpis": kpis}
            st.success("Attendance report generated.")
        except Exception as exc:
            st.session_state.pop("_report_attendance_result_new", None)
            st.error(f"Attendance report could not be generated: {exc}")
    result = st.session_state.get("_report_attendance_result_new")
    if result and result.get("signature") == signature:
        cols = st.columns(4)
        for col, (label, value) in zip(cols, result["kpis"]):
            col.metric(label, value)
        st.dataframe(result["frame"], use_container_width=True, hide_index=True)
        path = Path(result["pdf_path"])
        if path.exists():
            with path.open("rb") as handle:
                st.download_button("Download Attendance PDF", handle, file_name=path.name, mime="application/pdf", use_container_width=True, key="download_attendance_report_new")


def _render_month_end(bundle: dict, month_key: str, audit: dict | None) -> list[dict]:
    st.subheader("Month-End Salary & Expenses")
    st.caption("Expenses are deducted only from Gross Labour Collection. Spare Sales and Total Service Collection are not changed.")
    state_key = f"_report_expenses_{month_key.replace('-', '_')}"
    if state_key not in st.session_state:
        st.session_state[state_key] = [{"id": 1, "name": "", "amount": 0.0, "description": ""}]
    rows = st.session_state[state_key]
    next_id_key = f"{state_key}_next_id"
    if next_id_key not in st.session_state:
        st.session_state[next_id_key] = max([int(item.get("id", 0)) for item in rows] + [0]) + 1

    st.markdown("**Add expense entries**")
    rendered = []
    for row in rows:
        row_id = row["id"]
        a, b, c, d = st.columns([1.2, 0.8, 1.5, 0.55])
        name = a.text_input("Expense Name", value=row.get("name", ""), key=f"{state_key}_name_{row_id}", placeholder="Technician Salary / Electricity / Rent")
        amount = b.number_input("Amount (₹)", min_value=0.0, value=float(row.get("amount", 0) or 0), step=100.0, key=f"{state_key}_amount_{row_id}")
        description = c.text_input("Description (optional)", value=row.get("description", ""), key=f"{state_key}_description_{row_id}")
        rendered.append({"id": row_id, "name": name, "amount": amount, "description": description})
        if d.button("Remove", key=f"{state_key}_remove_{row_id}", help="Remove this expense row"):
            st.session_state[state_key] = [item for item in _expense_rows_from_widgets(state_key, rows) if item["id"] != row_id]
            st.rerun()

    if st.button("＋ ADD EXPENSE", key=f"{state_key}_add", use_container_width=True):
        next_id = int(st.session_state[next_id_key])
        st.session_state[next_id_key] = next_id + 1
        rendered.append({"id": next_id, "name": "", "amount": 0.0, "description": ""})
        st.session_state[state_key] = rendered
        st.rerun()
    st.session_state[state_key] = rendered

    expense = calculate_expense_totals(bundle["totals"]["labour"], rendered)
    c1, c2, c3 = st.columns(3)
    c1.metric("Gross Labour Collection", _currency(expense["gross_labour"]))
    c2.metric("Total Expenses", _currency(expense["total_expenses"]))
    c3.metric("Net Remaining Labour", _currency(expense["net_remaining"]), delta=None)
    financial = pd.DataFrame([
        {"Description": "Gross Labour Collection", "Amount": expense["gross_labour"]},
        {"Description": "Total Technician Salary", "Amount": expense["technician_salary"]},
        {"Description": "Total Other Expenses", "Amount": expense["other_expenses"]},
        {"Description": "Total Expenses", "Amount": expense["total_expenses"]},
        {"Description": "Net Remaining Labour Amount", "Amount": expense["net_remaining"]},
    ])
    st.dataframe(financial.style.format({"Amount": "₹{:,.2f}"}), use_container_width=True, hide_index=True)
    st.markdown("**Expense Details**")
    st.dataframe(expense["rows"].style.format({"Amount": "₹{:,.2f}"}), use_container_width=True, hide_index=True)
    if expense["net_remaining"] < 0:
        st.error(f"Expenses exceed gross labour collection by {_currency(abs(expense['net_remaining']))}.")
    st.info("Expense rows are kept in this Streamlit session and included in Excel export. This project has no approved dedicated expense-storage worksheet or persistence method, so rows are not written to Google Sheets.")
    return rendered


def _load_invoice_snapshot(read_report_sheet, *, force_refresh: bool = False, columns=None) -> pd.DataFrame:
    """Use the app's short-lived, session-local Sheets cache for report snapshots."""
    requested_columns = list(columns or REPORT_COLUMNS)
    source = read_report_sheet("invoices", force_refresh=force_refresh, columns=requested_columns)
    st.session_state["_advanced_report_source_snapshot"] = {
        "source": source.copy(),
        "fetched_at": source.attrs.get("sheets_fetched_at", "Refresh time not supplied"),
        "cache_reused": bool(source.attrs.get("sheets_cache_reused", False)),
    }
    return source


def _report_generation_ui(report_name: str, read_report_sheet, force_refresh: bool, builder, *, columns=None):
    """Run exactly one report builder against one required invoice snapshot."""
    status = st.empty()
    bar = st.progress(0, text=f"Starting {report_name}...")
    started = time.perf_counter()
    try:
        status.info("Loading required invoice columns from Google Sheets...")
        source = _load_invoice_snapshot(read_report_sheet, force_refresh=force_refresh, columns=columns)
        bar.progress(10, text=f"Required records loaded · {len(source):,} source rows")
        callback = _progress_callback(bar, status)
        result = builder(source, callback)
        elapsed = time.perf_counter() - started
        bar.progress(100, text=f"{report_name} generated · 100% · Elapsed: {elapsed:.1f} sec")
        status.success(f"{report_name} generated. Source snapshot: {source.attrs.get('sheets_fetched_at', 'available')}.")
        result["snapshot_time"] = source.attrs.get("sheets_fetched_at", "Not supplied")
        result["cache_reused"] = bool(source.attrs.get("sheets_cache_reused", False))
        result["elapsed_seconds"] = round(elapsed, 2)
        return result
    except Exception as exc:
        bar.empty()
        status.error(f"{report_name} could not be generated: {exc}")
        return None


def _display_report_download(title: str, summary: dict, details: pd.DataFrame, *, technician_summary: pd.DataFrame | None = None, key: str):
    """Render one report and export only its own detail rows."""
    st.markdown(f"### {title}")
    st.caption(f"Source snapshot: {summary.get('snapshot_time', 'Current read')} · {'45-second session cache reused' if summary.get('cache_reused') else 'source read refreshed'} · {summary.get('elapsed_seconds', 0):.1f}s")
    skip = {"snapshot_time", "cache_reused", "elapsed_seconds", "meta"}
    display_summary = {k: v for k, v in summary.items() if k not in skip and not isinstance(v, (dict, list, pd.DataFrame))}
    preferred = [
        ("total_job_cards", "Job Cards"), ("completed_job_cards", "Completed"),
        ("pending_job_cards", "Pending"), ("paid_service_count", "Paid Service"),
        ("fsc_count", "FSC"), ("spare_sales", "Spare Sales"),
        ("oil_amount", "Oil Amount"), ("labour_amount", "Labour"),
        ("service_collection", "Service Collection"),
    ]
    shown = 0
    metric_columns = None
    for field, label in preferred:
        if field in display_summary:
            if shown % 4 == 0:
                metric_columns = st.columns(4)
            value = display_summary[field]
            formatted = _currency(value) if field in {"spare_sales", "oil_amount", "labour_amount", "service_collection"} else f"{int(value):,}"
            metric_columns[shown % 4].metric(label, formatted)
            shown += 1
    if technician_summary is not None and not technician_summary.empty:
        st.markdown("**Technician-wise summary**")
        st.dataframe(technician_summary, use_container_width=True, hide_index=True)
    st.markdown("**Report details**")
    if details is None or details.empty:
        st.info("No matching records were found for this report filter.")
    else:
        money_cols = [c for c in details.columns if any(word in c.casefold() for word in ("amount", "sales", "labour", "oil"))]
        styler = details.style.format({c: "₹{:,.2f}" for c in money_cols}) if money_cols else details
        st.dataframe(styler, use_container_width=True, hide_index=True)
    try:
        xlsx = create_single_report_workbook(title, display_summary, details if details is not None else pd.DataFrame(), technician_summary)
        st.download_button(
            f"DOWNLOAD {title.upper()} (EXCEL)", data=xlsx,
            file_name=f"SELVA_MOTORS_{re.sub(r'[^A-Za-z0-9]+', '_', title).strip('_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True, key=f"{key}_export",
        )
    except Exception as exc:
        st.warning(f"Excel export could not be prepared: {exc}")


def _render_technician_daily_page(read_report_sheet, today_str, *, user_id: str, employee_name: str) -> None:
    """Dedicated technician-only screen; no monthly or other-employee records are rendered."""
    now = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    st.markdown(
        '<div class="selva-report-banner"><h2>SELVA MOTORS • TECHNICIAN DAILY REPORT</h2><p>Your daily job-card performance only · No other technician records</p></div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Signed-in technician: {employee_name or user_id}")
    selected_date = st.date_input("Report Date", value=now, key="technician_daily_report_date")
    force_refresh = st.checkbox("Refresh report data from Google Sheets", value=False, key="technician_daily_force_refresh")
    if st.button("GENERATE TECHNICIAN REPORT", type="primary", use_container_width=True, key="generate_technician_daily_only"):
        st.session_state.pop("_technician_daily_only_result", None)
        result = _report_generation_ui(
            "Technician Daily Report", read_report_sheet, force_refresh,
            lambda source, progress: build_technician_daily_report(
                source, selected_date, technician_name=employee_name, user_id=user_id, progress=progress,
            ),
            columns=DAILY_REPORT_COLUMNS,
        )
        if result is not None:
            result["signature"] = f"{selected_date}|{user_id}|{employee_name}"
            st.session_state["_technician_daily_only_result"] = result
    result = st.session_state.get("_technician_daily_only_result")
    signature = f"{selected_date}|{user_id}|{employee_name}"
    if result and result.get("signature") == signature:
        if result.get("no_records"):
            st.info("No Job Card records found for your account on the selected date.")
        summary = result["summary"]
        columns = st.columns(4)
        columns[0].metric("Job Cards Assigned", f"{summary['total_job_cards']:,}")
        columns[1].metric("Completed", f"{summary['completed_job_cards']:,}")
        columns[2].metric("Pending", f"{summary['pending_job_cards']:,}")
        columns[3].metric("Paid Service", f"{summary['paid_service_count']:,}")
        columns2 = st.columns(4)
        columns2[0].metric("FSC", f"{summary['fsc_count']:,}")
        columns2[1].metric("Spare Sales", _currency(summary["spare_sales"]))
        columns2[2].metric("Oil Amount", _currency(summary["oil_amount"]))
        columns2[3].metric("Labour Amount", _currency(summary["labour_amount"]))
        if summary["unclassified_status"]:
            st.warning(f"{summary['unclassified_status']} Job Card(s) have an unclassified status. Values such as Active are not assumed to mean Completed or Pending.")
        if result.get("data_quality_conflict_detected"):
            st.warning("Duplicate Job Card conflicts exist in the source for this date. Conflicting records are excluded from technician totals; Admin should review the Job Card audit.")
        details = result["jobcard_details"].drop(columns=["Data Quality"], errors="ignore")
        st.markdown("**Your Job Card Details**")
        if details.empty:
            st.info("No Job Card details are available for this date.")
        else:
            money_cols = [c for c in ["Spare Parts Amount", "Oil Amount", "Labour Amount", "Total Amount"] if c in details]
            st.dataframe(details.style.format({c: "₹{:,.2f}" for c in money_cols}), use_container_width=True, hide_index=True)
        workbook_summary = {k: v for k, v in summary.items() if k != "meta"}
        try:
            xlsx = create_single_report_workbook("Technician Daily Report", workbook_summary, details)
            st.download_button("DOWNLOAD MY DAILY REPORT (EXCEL)", xlsx, "SELVA_MOTORS_Technician_Daily_Report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key="download_technician_daily_only")
        except Exception as exc:
            st.warning(f"Technician report export could not be prepared: {exc}")


def _render_todays_business_report(read_report_sheet, *, force_refresh: bool, is_admin: bool, is_manager: bool, is_prathisha: bool) -> None:
    st.subheader("Today's Business Summary")
    st.caption("Date filter uses the existing invoices worksheet Date (record-entry date). Paid Service and FSC are counted only when Service Type explicitly identifies them; ambiguous service labels are not guessed.")
    selected_date = st.date_input("Business Report Date", value=datetime.now(ZoneInfo("Asia/Kolkata")).date(), key="todays_business_report_date")
    if st.button("GENERATE TODAY'S REPORT", type="primary", use_container_width=True, key="generate_todays_business_report"):
        st.session_state.pop("_todays_business_report_result", None)
        result = _report_generation_ui(
            "Today's Business Report", read_report_sheet, force_refresh,
            lambda source, progress: build_daily_business_report(source, selected_date, progress=progress),
            columns=DAILY_REPORT_COLUMNS,
        )
        if result is not None:
            result["signature"] = str(selected_date)
            st.session_state["_todays_business_report_result"] = result
    result = st.session_state.get("_todays_business_report_result")
    if result and result.get("signature") == str(selected_date):
        summary = result["summary"]
        metrics = st.columns(4)
        metrics[0].metric("Total Job Cards", f"{summary['total_job_cards']:,}")
        metrics[1].metric("Completed Job Cards", f"{summary['completed_job_cards']:,}")
        metrics[2].metric("Pending Job Cards", f"{summary['pending_job_cards']:,}")
        metrics[3].metric("Spare Parts Sales", _currency(summary["spare_sales"]))
        metrics2 = st.columns(4)
        metrics2[0].metric("Oil Amount", _currency(summary["oil_amount"]))
        metrics2[1].metric("Labour Amount", _currency(summary["labour_amount"]))
        metrics2[2].metric("Paid Service Count", f"{summary['paid_service_count']:,}")
        metrics2[3].metric("FSC Count", f"{summary['fsc_count']:,}")
        if summary.get("unassigned_job_cards", 0):
            st.info(f"{summary['unassigned_job_cards']} Job Card(s) have no technician assignment. They remain in overall totals but are not allocated to any technician.")
        st.caption(f"Date: {result['report_date']} · Source rows for this date: {result['source_rows']:,} · Duplicate rows removed: {summary['duplicate_rows_removed']:,}")
        if summary["conflicting_jobcards"] or summary["conflicting_entries"]:
            st.warning(f"Conflicting duplicates: {summary['conflicting_jobcards']} Job Card group(s), {summary['conflicting_entries']} unlinked entry group(s). Conflicting amounts are excluded.")
        if result["source_rows"] == 0:
            st.warning("No invoice rows were returned for this date. Verify the source and date field before treating zero totals as final.")
        st.markdown("**Technician-wise Daily Performance**")
        tech = result["technician_summary"]
        if tech.empty:
            st.info("No technician-assigned Job Cards were found for this date.")
        else:
            st.dataframe(tech.style.format({c: "₹{:,.2f}" for c in ["Spare Sales", "Oil Amount", "Labour"]}), use_container_width=True, hide_index=True)
            tech_names = tech["Technician"].tolist()
            selected_tech = st.selectbox("Technician Name", tech_names, key="todays_report_technician_detail")
            technician_signature = f"{selected_date}|{selected_tech}"
            if st.button("GENERATE SELECTED TECHNICIAN DAILY REPORT", use_container_width=True, key="generate_selected_technician_daily_detail"):
                st.session_state.pop("_todays_selected_technician_report_result", None)
                technician_result = _report_generation_ui(
                    f"{selected_tech} Daily Report", read_report_sheet, force_refresh,
                    lambda source, progress: build_technician_daily_report(
                        source, selected_date, technician_name=selected_tech, progress=progress,
                    ),
                    columns=DAILY_REPORT_COLUMNS,
                )
                if technician_result is not None:
                    technician_result["signature"] = technician_signature
                    st.session_state["_todays_selected_technician_report_result"] = technician_result
            technician_result = st.session_state.get("_todays_selected_technician_report_result")
            if technician_result and technician_result.get("signature") == technician_signature:
                st.markdown(f"**{selected_tech} — Daily Job Card Details**")
                technician_details = technician_result["jobcard_details"].drop(columns=["Data Quality"], errors="ignore")
                _display_report_download(
                    f"{selected_tech} Daily Report",
                    {**technician_result["summary"], "snapshot_time": technician_result.get("snapshot_time", "Current read"),
                     "cache_reused": technician_result.get("cache_reused", False),
                     "elapsed_seconds": technician_result.get("elapsed_seconds", 0)},
                    technician_details, key="selected_technician_daily_report",
                )
        export_summary = dict(summary)
        export_summary.update({
            "snapshot_time": result.get("snapshot_time", "Current read"),
            "cache_reused": result.get("cache_reused", False),
            "elapsed_seconds": result.get("elapsed_seconds", 0),
        })
        _display_report_download(
            "Today's Business Report", export_summary, result["jobcard_details"],
            technician_summary=tech, key="todays_business_report",
        )


def _render_individual_monthly_reports(read_report_sheet, month: int, year: int, *, force_refresh: bool):
    st.subheader("Independent Monthly Report Generation")
    st.caption("Each button generates only its selected report. A fresh Google Sheets snapshot is shared by the 45-second session cache.")
    report_buttons = [
        ("service", "GENERATE MONTHLY SERVICE REPORT"),
        ("technician", "GENERATE TECHNICIAN MONTHLY REPORT"),
        ("spare", "GENERATE SPARE SALES REPORT"),
        ("oil", "GENERATE OIL SALES REPORT"),
        ("labour", "GENERATE LABOUR COLLECTION REPORT"),
        ("paid", "GENERATE PAID SERVICE REPORT"),
        ("fsc", "GENERATE FSC REPORT"),
        ("jobcards", "GENERATE MONTHLY JOB CARD REPORT"),
        ("accounts", "GENERATE MONTH-END ACCOUNTS REPORT"),
        ("salary", "GENERATE SALARY & EXPENSES REPORT"),
    ]
    result_key = "_individual_monthly_report_result"
    cols = st.columns(2)
    for index, (report_type, label) in enumerate(report_buttons):
        if cols[index % 2].button(label, use_container_width=True, key=f"generate_individual_{report_type}_{month}_{year}"):
            st.session_state.pop(result_key, None)
            result = _report_generation_ui(
                label.title(), read_report_sheet, force_refresh,
                lambda source, progress, kind=report_type: build_individual_monthly_report(
                    source, month, year, kind, progress=progress,
                ),
            )
            if result is not None:
                result["signature"] = f"{report_type}|{month}|{year}"
                st.session_state[result_key] = result

    # Independent missing-number audit uses the entire invoice snapshot, without a date filter.
    with st.expander("Missing Job Card Number Report", expanded=False):
        a, b = st.columns(2)
        start_no = a.text_input("Month Start Job Card Number", placeholder="67381-03-RJC-1126-1289", key=f"individual_audit_start_{month}_{year}")
        end_no = b.text_input("Month End Job Card Number", placeholder="67381-03-RJC-1126-1399", key=f"individual_audit_end_{month}_{year}")
        if st.button("GENERATE MISSING JOB CARD REPORT", type="primary", use_container_width=True, key=f"generate_individual_missing_{month}_{year}"):
            st.session_state.pop(f"_individual_missing_audit_{month}_{year}", None)
            audit = _report_generation_ui(
                "Missing Job Card Report", read_report_sheet, force_refresh,
                lambda source, progress: calculate_missing_jobcards(source, start_no, end_no, progress=progress),
                columns=["Job Card Number"],
            )
            if audit is not None:
                audit["signature"] = f"{re.sub(r'\s+', '', start_no).upper()}|{re.sub(r'\s+', '', end_no).upper()}"
                st.session_state[f"_individual_missing_audit_{month}_{year}"] = audit
        audit = st.session_state.get(f"_individual_missing_audit_{month}_{year}")
        wanted_signature = f"{re.sub(r'\s+', '', start_no).upper()}|{re.sub(r'\s+', '', end_no).upper()}"
        if audit and audit.get("signature") == wanted_signature:
            kpis = st.columns(4)
            kpis[0].metric("Expected", f"{audit['expected_count']:,}")
            kpis[1].metric("Found", f"{audit['found_count']:,}")
            kpis[2].metric("Missing", f"{audit['missing_count']:,}")
            kpis[3].metric("Duplicate Rows", f"{audit['duplicate_count']:,}")
            st.caption(
                f"Source snapshot: {audit.get('snapshot_time', 'Refresh time not supplied')} · "
                f"{'45-second session cache reused' if audit.get('cache_reused') else 'source read refreshed'} · "
                f"Elapsed: {audit.get('elapsed_seconds', 0):.1f} sec · All dates checked"
            )
            if audit["verification"].startswith("VERIFIED"):
                st.success(audit["verification"])
            else:
                st.warning(audit["verification"] + " — the result is potential only until source completeness is reviewed.")
                for reason in audit.get("verification_reasons", []):
                    st.caption(reason)
            if audit["missing_numbers"]:
                st.dataframe(pd.DataFrame({"Missing Job Card Number": audit["missing_numbers"]}), use_container_width=True, hide_index=True)
            else:
                st.info("No gaps found in this range, subject to the verification status above.")
            if audit.get("duplicate_numbers"):
                with st.expander("Duplicate Job Card Numbers"):
                    st.dataframe(pd.DataFrame({"Duplicate Job Card Number": audit["duplicate_numbers"]}), use_container_width=True, hide_index=True)
            if isinstance(audit.get("invalid_records"), pd.DataFrame) and not audit["invalid_records"].empty:
                with st.expander("Invalid / Blank Source Job Cards"):
                    st.dataframe(audit["invalid_records"], use_container_width=True, hide_index=True)
            try:
                audit_file = create_missing_jobcard_workbook(audit)
                st.download_button("DOWNLOAD MISSING JOB CARD REPORT (EXCEL)", audit_file,
                    f"SELVA_MOTORS_Missing_Job_Cards_{month:02d}_{year}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key=f"individual_missing_export_{month}_{year}")
            except Exception as exc:
                st.warning(f"Missing Job Card Excel export failed: {exc}")

    result = st.session_state.get(result_key)
    if result and result.get("signature", "").split("|")[:3] == [result.get("report_type"), str(month), str(year)]:
        report_type = result["report_type"]
        title_map = {
            "service": "Monthly Service Report", "technician": "Technician-wise Monthly Service Report",
            "spare": "Spare Parts Sales Report", "oil": "Oil Sales Report",
            "labour": "Labour Collection Report", "paid": "Paid Service Report",
            "fsc": "FSC Report", "jobcards": "Monthly Job Card Report",
            "accounts": "Month-End Accounts Report", "salary": "Salary & Expenses Report",
        }
        title = title_map.get(report_type, "Monthly Report")
        summary = dict(result["summary"])
        summary.update({
            "snapshot_time": result.get("snapshot_time", "Current read"),
            "cache_reused": result.get("cache_reused", False),
            "elapsed_seconds": result.get("elapsed_seconds", 0),
        })
        details = result["details"]
        technician_summary = result.get("technician_summary")

        if report_type == "technician" and technician_summary is not None and not technician_summary.empty:
            technician_names = technician_summary["Technician Name"].tolist()
            selected_tech = st.selectbox("Technician Name", ["All Technicians"] + technician_names, key=f"individual_monthly_tech_pick_{month}_{year}")
            if selected_tech != "All Technicians":
                details = details[details["Technician Name"].astype(str).str.strip().str.casefold() == selected_tech.casefold()].copy()
                selected_row = technician_summary[technician_summary["Technician Name"].astype(str).str.strip().str.casefold() == selected_tech.casefold()]
                if not selected_row.empty:
                    row = selected_row.iloc[0]
                    summary.update({
                        "total_job_cards": int(row.get("Total Job Cards", 0)),
                        "completed_job_cards": int(row.get("Completed Job Cards", 0)),
                        "pending_job_cards": int(row.get("Pending Job Cards", 0)),
                        "paid_service_count": int(row.get("Paid Service Count", 0)),
                        "fsc_count": int(row.get("FSC Count", 0)),
                        "spare_sales": float(row.get("Spare Parts Sales", 0)),
                        "oil_amount": float(row.get("Oil Amount", 0)),
                        "labour_amount": float(row.get("Labour Collection", 0)),
                    })
                technician_summary = selected_row

        if report_type == "salary":
            st.markdown(f"### {title}")
            st.caption(
                f"Source snapshot: {result.get('snapshot_time', 'Current read')} · "
                f"{'45-second session cache reused' if result.get('cache_reused') else 'source read refreshed'} · "
                f"Elapsed: {result.get('elapsed_seconds', 0):.1f} sec"
            )
            month_key = f"{month:02d}-{year}"
            expenses = _render_month_end(
                {"totals": {"labour": float(result["summary"]["labour_amount"])}}, month_key, None,
            )
            expense_totals = calculate_expense_totals(result["summary"]["labour_amount"], expenses)
            salary_summary = {
                "Gross Labour Collection": expense_totals["gross_labour"],
                "Technician Salary": expense_totals["technician_salary"],
                "Other Expenses": expense_totals["other_expenses"],
                "Total Expenses": expense_totals["total_expenses"],
                "Net Remaining Labour": expense_totals["net_remaining"],
            }
            st.dataframe(pd.DataFrame([{"Description": k, "Amount": v} for k, v in salary_summary.items()]).style.format({"Amount": "₹{:,.2f}"}), use_container_width=True, hide_index=True)
            try:
                xlsx = create_single_report_workbook(title, salary_summary, expense_totals["rows"])
                st.download_button("DOWNLOAD SALARY & EXPENSES REPORT (EXCEL)", xlsx,
                    f"SELVA_MOTORS_Salary_Expenses_{month_key}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key=f"individual_salary_export_{month_key}")
            except Exception as exc:
                st.warning(f"Salary and expense export could not be prepared: {exc}")
        else:
            _display_report_download(
                title, summary, details,
                technician_summary=technician_summary,
                key=f"individual_{report_type}_{month}_{year}",
            )


def render_report_center(
    *,
    read_report_sheet: Callable[..., pd.DataFrame],
    today_str: Callable[[], str],
    pdf_dir: Path,
    is_admin: bool,
    is_manager: bool,
    is_technician: bool,
    is_prathisha: bool,
    user_id: str,
    employee_name: str,
    daily_only: bool = False,
) -> None:
    """Render reports using one explicit invoice-sheet read per generation."""
    if daily_only or is_technician:
        _render_technician_daily_page(
            read_report_sheet, today_str, user_id=user_id, employee_name=employee_name,
        )
        return
    st.markdown(
        """
        <style>
        .selva-report-banner{padding:19px 22px;border-radius:18px;background:linear-gradient(115deg,#101318,#292d34);border-left:6px solid #e31837;color:#fff;margin:8px 0 16px 0;}
        .selva-report-banner h2{margin:0 0 5px 0;font-size:23px;font-weight:900;}
        .selva-report-banner p{margin:0;color:#d1d5db;font-size:13px;}
        .selva-report-note{padding:10px 13px;background:#fff8e7;border:1px solid #f5d48a;border-radius:10px;color:#704d00;font-size:13px;margin:8px 0;}
        </style>
        <div class="selva-report-banner"><h2>SELVA MOTORS • ADVANCED REPORTS</h2><p>Monthly service performance · Technician reports · Spare sales · Labour collection · Job Card audit · Month-end accounts</p></div>
        """,
        unsafe_allow_html=True,
    )

    can_view_monthly = is_admin or is_manager or is_technician
    if not can_view_monthly and not (is_admin or is_manager or is_prathisha):
        st.error("Your role does not have permission to view these reports.")
        return

    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    month_year = list(range(max(2000, now.year - 10), now.year + 2))
    c1, c2, c3 = st.columns([1, 1, 1.4])
    month = c1.selectbox("Report Month", range(1, 13), index=now.month - 1, format_func=lambda x: MONTH_NAMES[x - 1], key="advanced_report_month")
    year = c2.selectbox("Report Year", month_year, index=month_year.index(now.year), key="advanced_report_year")
    fresh = c3.checkbox("Force fresh Google Sheets read", value=False, key="advanced_report_fresh")
    month_key = f"{month:02d}-{year}"

    # New daily report runs independently; no monthly calculations are performed here.
    if is_admin or is_manager or is_prathisha:
        with st.expander("Today's Business Report", expanded=True):
            _render_todays_business_report(
                read_report_sheet, force_refresh=fresh,
                is_admin=is_admin, is_manager=is_manager, is_prathisha=is_prathisha,
            )
        st.divider()

    if can_view_monthly:
        with st.expander("Independent Monthly Reports", expanded=True):
            _render_individual_monthly_reports(read_report_sheet, month, year, force_refresh=fresh)
        st.divider()
        st.caption("One selected-column invoice worksheet snapshot is reused for all monthly reports and the missing Job Card audit. No report calculations are written back to source records.")
        if st.button("GENERATE COMPLETE MONTHLY DASHBOARD (ALL EXISTING SECTIONS)", type="primary", use_container_width=True, key="generate_advanced_monthly_reports"):
            status_slot = st.empty()
            progress_bar = st.progress(0, text="Reading Job Card Records from Google Sheets...")
            status_slot.info("Reading the existing invoices worksheet using the approved report columns. This includes all dates for the Job Card audit.")
            try:
                source = read_report_sheet("invoices", force_refresh=fresh, columns=REPORT_COLUMNS)
                progress_bar.progress(15, text=f"Source read complete · {len(source):,} records received")
                status_slot.caption(f"Source read complete: {len(source):,} invoice records. Processing selected month {month_key}.")
                visible_source = _filter_technician_scope(source, is_technician, user_id, employee_name)
                callback = _progress_callback(progress_bar, status_slot)
                bundle = build_monthly_bundle(visible_source, month, year, progress=callback)
                progress_bar.progress(100, text="All monthly reports generated · 100%")
                status_slot.success("Monthly reports generated from one source snapshot.")
                st.session_state["_advanced_report_snapshot"] = {
                    "signature": month_key,
                    "bundle": bundle,
                    "source": source,
                    "source_record_count": len(source),
                    "snapshot_time": source.attrs.get("sheets_fetched_at", "Current report read"),
                    "cache_reused": bool(source.attrs.get("sheets_cache_reused", False)),
                }
                # An invoice write invalidates this result via app.clear_storage_cache.
                st.session_state.pop(f"_report_missing_audit_{month_key}", None)
            except Exception as exc:
                st.session_state.pop("_advanced_report_snapshot", None)
                status_slot.error(f"Report generation failed. The source could not be verified: {exc}")

        snapshot = st.session_state.get("_advanced_report_snapshot")
        if snapshot and snapshot.get("signature") == month_key:
            bundle = snapshot["bundle"]
            source = snapshot["source"]
            totals = bundle["totals"]
            st.caption(
                f"Source snapshot: {snapshot['snapshot_time']} · "
                f"{snapshot['source_record_count']:,} source rows · "
                f"{'45-second session cache reused' if snapshot['cache_reused'] else 'freshly fetched'}"
            )
            st.warning(
                "Data limits in the current ERP: the monthly filter uses the invoices worksheet Date (record-entry date); "
                "there is no separate Job Card Date, Customer Name, per-part line list, or Other Charges column. "
                "The separate manual_invoices worksheet has no Job Card Number and is not mixed into this Job Card report. "
                "Only explicit Completed/Pending source statuses are classified; 'Active' remains unclassified."
            )

            overview_tab, tech_tab, spare_tab, labour_tab, audit_tab, accounts_tab = st.tabs([
                "Monthly Overview", "Technician Performance", "Spare Parts Sales",
                "Labour Collection", "Job Card Audit", "Month-End Salary & Expenses",
            ])

            with overview_tab:
                st.subheader(f"Monthly Service Report — {MONTH_NAMES[month - 1]} {year}")
                metrics = st.columns(4)
                metrics[0].metric("Total Job Cards", f"{totals['jobcards']:,}")
                metrics[1].metric("Completed", f"{totals['completed']:,}")
                metrics[2].metric("Pending", f"{totals['pending']:,}")
                metrics[3].metric("Services / Records", f"{totals['services']:,}")
                metrics2 = st.columns(4)
                metrics2[0].metric("Spare Parts Sales", _currency(totals["spare"]))
                metrics2[1].metric("Oil Amount", _currency(totals["oil"]))
                metrics2[2].metric("Gross Labour", _currency(totals["labour"]))
                metrics2[3].metric("Service Collection", _currency(totals["service"]))
                if totals["unclassified"]:
                    st.warning(f"{totals['unclassified']} Job Card(s) have a source Status that cannot be classified as Completed or Pending. Values such as 'Active' are not assumed to mean Completed.")
                if bundle["meta"]["conflicting_jobcards"] or bundle["meta"].get("conflicting_entries", 0):
                    st.warning(
                        f"Conflicting duplicate records: {bundle['meta']['conflicting_jobcards']} Job Card group(s) and "
                        f"{bundle['meta'].get('conflicting_entries', 0)} unlinked Entry ID group(s). Their amounts are excluded from financial totals to avoid double counting."
                    )
                if bundle["meta"]["blank_jobcard_rows"]:
                    st.warning(f"{bundle['meta']['blank_jobcard_rows']} monthly invoice record(s) have no Job Card Number. They are excluded from Job Card counts but included in financial totals when their Entry ID is unique.")
                st.markdown("**Technician-wise monthly comparison**")
                if not bundle["technician_summary"].empty:
                    chart_data = bundle["technician_summary"].set_index("Technician Name")[["Labour Collection", "Spare Parts Sales"]]
                    st.bar_chart(chart_data)
                    st.dataframe(bundle["technician_summary"].style.format({
                        "Spare Parts Sales": "₹{:,.2f}", "Labour Collection": "₹{:,.2f}",
                        "Average Labour per Job Card": "₹{:,.2f}",
                    }), use_container_width=True, hide_index=True)
                else:
                    st.info("No technician service records were found for this month.")
                st.markdown("**Monthly totals**")
                st.dataframe(bundle["summary"].style.format({
                    "Spare Parts Sales (Oil excluded)": "₹{:,.2f}", "Oil Amount": "₹{:,.2f}",
                    "Gross Labour Collection": "₹{:,.2f}", "Total Service Collection": "₹{:,.2f}",
                }), use_container_width=True, hide_index=True)
                st.caption("Other Charges are not available in the current invoices worksheet. Total Service Collection uses the existing Total Amount field.")

            with tech_tab:
                st.subheader("Particular Technician Service Report")
                tech_names = bundle["technician_summary"].get("Technician Name", pd.Series(dtype=str)).tolist()
                if is_technician:
                    selected_tech = "All Technicians"
                    st.info(f"Showing only your own records: {employee_name or user_id}.")
                else:
                    choices = ["All Technicians"] + tech_names
                    selected_tech = st.selectbox("Technician Name", choices, index=0, key=f"advanced_technician_{month_key}")
                tech_data = technician_detail(bundle, selected_tech)
                t1, t2, t3, t4 = st.columns(4)
                t1.metric("Job Cards Assigned", f"{tech_data['jobcard_count']:,}")
                t2.metric("Completed", f"{tech_data['completed']:,}")
                t3.metric("Pending", f"{tech_data['pending']:,}")
                t4.metric("Service Count", f"{tech_data['service_count']:,}")
                t5, t6, t7 = st.columns(3)
                t5.metric("Spare Sales", _currency(tech_data["spare"]))
                t6.metric("Labour Collection", _currency(tech_data["labour"]))
                t7.metric("Average Labour / Job Card", _currency(tech_data["average_labour"]))
                if tech_data["unclassified"]:
                    st.warning(f"{tech_data['unclassified']} Job Card(s) have an unclassified source status.")
                detail = tech_data["jobcards"].copy()
                display_cols = [c for c in ["Date", "Job Card Number", "Registration Number", "Bike Model", "Service Type", "Status", "Labour Amount", "Spare Amount", "Oil Amount", "Total Amount"] if c in detail]
                st.markdown("**Individual Job Cards included**")
                if detail.empty:
                    st.info("No Job Card records are available for this technician in the selected month.")
                else:
                    st.dataframe(detail[display_cols].style.format({c: "₹{:,.2f}" for c in ["Labour Amount", "Spare Amount", "Oil Amount", "Total Amount"] if c in display_cols}), use_container_width=True, hide_index=True)

            with spare_tab:
                st.subheader("Monthly Spare Parts Sales Report")
                s1, s2 = st.columns(2)
                s1.metric("Total Spare Parts Sales (Oil Excluded)", _currency(totals["spare"]))
                s2.metric("Job Cards with Spare Sales", f"{totals['spare_jobcards']:,}")
                spare_count = pd.to_numeric(bundle["spare_details"].get("Spare Parts Count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
                st.metric("Stored Spare Parts Count", f"{spare_count:,.0f}")
                st.dataframe(bundle["spare_details"], use_container_width=True, hide_index=True)
                st.markdown('<div class="selva-report-note">Part Number, Part Description and individual Quantity are not stored in the current invoices worksheet. This screen therefore reports the actual stored Spare Parts Count and Spare Amount per Job Card; it does not fabricate a part-wise sales breakdown. The report uses the existing Spare Amount (which the current OCR save logic stores after separating oil) and does not subtract Oil Amount a second time.</div>', unsafe_allow_html=True)

            with labour_tab:
                st.subheader("Gross Labour Collection Report")
                labour_rows = bundle["labour_details"]
                jc_with_labour = labour_rows[(labour_rows["Job Card Number"].astype(str).str.strip() != "") & (pd.to_numeric(labour_rows["Labour Amount"], errors="coerce").fillna(0) > 0)] if not labour_rows.empty else labour_rows
                labour_jc_count = jc_with_labour["Job Card Number"].astype(str).str.strip().str.upper().nunique() if not jc_with_labour.empty else 0
                linked_labour = float(pd.to_numeric(jc_with_labour.get("Labour Amount", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not jc_with_labour.empty else 0.0
                unlinked_labour = max(float(totals["labour"]) - linked_labour, 0.0)
                l1, l2, l3, l4 = st.columns(4)
                l1.metric("Gross Labour Collection", _currency(totals["labour"]))
                l2.metric("Job Cards with Labour", f"{labour_jc_count:,}")
                l3.metric("Average Labour / Job Card", _currency(linked_labour / max(labour_jc_count, 1)))
                l4.metric("Labour Without Job Card", _currency(unlinked_labour))
                if not bundle["technician_summary"].empty:
                    st.dataframe(bundle["technician_summary"][["Technician Name", "Total Job Cards", "Labour Collection", "Average Labour per Job Card"]].style.format({"Labour Collection": "₹{:,.2f}", "Average Labour per Job Card": "₹{:,.2f}"}), use_container_width=True, hide_index=True)
                st.markdown("**Individual Job Card Labour Details**")
                st.dataframe(labour_rows, use_container_width=True, hide_index=True)
                st.caption("This is gross Labour Collection before any salary or expense deductions.")

            current_audit = st.session_state.get(f"_report_missing_audit_{month_key}")
            with audit_tab:
                if not (is_admin or is_manager):
                    st.info("Missing Job Card sequence audit is available to Admin / Manager roles only.")
                else:
                    st.subheader("Missing Job Card Number Detection")
                    st.caption("Enter the complete first and last Job Card Numbers manually. Verification uses the full invoice worksheet snapshot across all dates, not only the selected month.")
                    a, b = st.columns(2)
                    start_no = a.text_input("Month Start Job Card Number", placeholder="67381-03-RJC-1126-1289", key=f"audit_start_{month_key}")
                    end_no = b.text_input("Month End Job Card Number", placeholder="67381-03-RJC-1126-1399", key=f"audit_end_{month_key}")
                    if current_audit:
                        normalized_start = re.sub(r"\s+", "", str(start_no or "")).upper()
                        normalized_end = re.sub(r"\s+", "", str(end_no or "")).upper()
                        if normalized_start != current_audit.get("start") or normalized_end != current_audit.get("end"):
                            current_audit = None
                    if st.button("CHECK MISSING JOB CARDS", type="primary", use_container_width=True, key=f"check_missing_{month_key}"):
                        bar = st.progress(0, text="Validating Job Card Number range...")
                        message = st.empty()
                        message.info("Checking every returned invoice record. No month date filter is applied.")
                        try:
                            audit_progress = _progress_callback(bar, message)
                            audit = calculate_missing_jobcards(source, start_no, end_no, progress=audit_progress)
                            st.session_state[f"_report_missing_audit_{month_key}"] = audit
                            current_audit = audit
                            message.success("Job Card sequence comparison completed.")
                        except ValueError as exc:
                            st.session_state.pop(f"_report_missing_audit_{month_key}", None)
                            current_audit = None
                            st.error(str(exc))
                        except Exception as exc:
                            st.session_state.pop(f"_report_missing_audit_{month_key}", None)
                            current_audit = None
                            st.error(f"Job Card audit could not be completed. Verification is incomplete: {exc}")
                    if current_audit:
                        x1, x2, x3, x4 = st.columns(4)
                        x1.metric("Expected Job Cards", f"{current_audit['expected_count']:,}")
                        x2.metric("Found Job Cards", f"{current_audit['found_count']:,}")
                        x3.metric("Missing Job Cards", f"{current_audit['missing_count']:,}")
                        x4.metric("Duplicate Rows", f"{current_audit['duplicate_count']:,}")
                        if current_audit["verification"].startswith("VERIFIED"):
                            st.success(current_audit["verification"])
                        else:
                            st.warning(current_audit["verification"] + ". Do not treat the missing-number list as final until source records are reviewed.")
                            for reason in current_audit["verification_reasons"]:
                                st.caption("• " + reason)
                        st.markdown("**Missing Job Card Numbers**")
                        if current_audit["missing_numbers"]:
                            st.dataframe(pd.DataFrame({"Missing Job Card Number": current_audit["missing_numbers"]}), use_container_width=True, hide_index=True)
                        elif current_audit["verification"].startswith("VERIFIED"):
                            st.success("No missing numbers were found in the specified series and range.")
                        else:
                            st.warning("No gaps were found among valid records, but source completeness is not established. Review the invalid / blank records before treating this as final.")
                        if current_audit["duplicate_numbers"]:
                            with st.expander("Duplicate Job Card Numbers"):
                                st.dataframe(pd.DataFrame({"Duplicate Job Card Number": current_audit["duplicate_numbers"]}), use_container_width=True, hide_index=True)
                        if not current_audit["invalid_records"].empty:
                            with st.expander("Invalid Job Card Source Records"):
                                st.dataframe(current_audit["invalid_records"], use_container_width=True, hide_index=True)
                        st.caption(f"Source rows checked: {current_audit['source_record_count']:,}. Month date filter applied: No.")
                        try:
                            audit_xlsx = create_missing_jobcard_workbook(current_audit)
                            st.download_button(
                                "DOWNLOAD MISSING JOB CARD AUDIT (EXCEL)",
                                data=audit_xlsx,
                                file_name=f"SELVA_MOTORS_Missing_Job_Cards_{month_key}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True,
                                key=f"download_missing_jc_{month_key}",
                            )
                        except Exception as exc:
                            st.warning(f"Missing Job Card Excel export is unavailable: {exc}")

            with accounts_tab:
                if is_technician:
                    st.info("Month-end salary and expense calculations are restricted to Admin / Manager roles.")
                else:
                    individual_result = st.session_state.get("_individual_monthly_report_result", {})
                    salary_editor_active = (
                        individual_result.get("report_type") == "salary"
                        and individual_result.get("signature", "").split("|")[:3] == ["salary", str(month), str(year)]
                    )
                    expense_state_key = f"_report_expenses_{month_key.replace('-', '_')}"
                    if salary_editor_active:
                        st.info("Salary & Expenses are currently being edited in the Independent Monthly Reports section above.")
                        expenses = st.session_state.get(expense_state_key, [])
                    else:
                        expenses = _render_month_end(bundle, month_key, current_audit)
                    st.divider()
                    st.markdown("**Export Reports**")
                    try:
                        excel_bytes = create_excel_report(bundle, expenses, current_audit)
                        st.download_button(
                            "DOWNLOAD COMPLETE MONTHLY EXCEL REPORT",
                            data=excel_bytes,
                            file_name=f"SELVA_MOTORS_Monthly_Report_{month_key}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary",
                            use_container_width=True,
                            key=f"download_complete_excel_{month_key}",
                        )
                    except Exception as exc:
                        st.error(f"Excel export could not be prepared: {exc}")

    # Retain the existing monthly attendance report for authorized roles.
    if is_admin or is_manager or is_prathisha or is_technician:
        st.divider()
        with st.expander("Monthly Attendance Reports", expanded=False):
            _show_attendance_report(
                read_report_sheet, today_str, pdf_dir,
                is_admin=is_admin, is_manager=is_manager, is_technician=is_technician,
                is_prathisha=is_prathisha, user_id=user_id, employee_name=employee_name,
            )
