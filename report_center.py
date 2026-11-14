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
)

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
ATTENDANCE_COLUMNS = [
    "Date", "Time", "User ID", "Technician Name", "Role",
    "Attendance Status", "Distance Meter", "Selfie Saved",
]


def _currency(value: object) -> str:
    return format_inr(float(value or 0))


def _progress_callback(bar, message_slot):
    def update(stage: str, percent: int, processed: int, total: int, remaining: float | None):
        label = f"{stage} · {percent}%"
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
) -> None:
    """Render reports using one explicit invoice-sheet read per generation."""
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

    if can_view_monthly:
        st.caption("One selected-column invoice worksheet snapshot is reused for all monthly reports and the missing Job Card audit. No report calculations are written back to source records.")
        if st.button("GENERATE MONTHLY REPORTS", type="primary", use_container_width=True, key="generate_advanced_monthly_reports"):
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
