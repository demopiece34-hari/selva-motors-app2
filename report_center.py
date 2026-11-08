"""On-demand, role-aware Selva Motors report pages."""
from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Callable

import pandas as pd
import streamlit as st

from pdf_generator import format_inr, generate_professional_report_pdf

SERVICE_TYPES = ["All", "FSC", "Paid Service", "General", "Joyride", "Accident"]
REPORT_TZ = ZoneInfo("Asia/Kolkata")


def _now_report_time() -> datetime:
    return datetime.now(REPORT_TZ)


def _norm_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    date_value = pd.to_datetime(text.replace("/", "-"), dayfirst=True, errors="coerce")
    return text.replace("/", "-") if pd.isna(date_value) else date_value.strftime("%d-%m-%Y")


def _month_key(value: object) -> str:
    text = str(value or "").strip()
    try:
        parsed = pd.to_datetime(text, format="%m-%Y", errors="raise")
        return parsed.strftime("%m-%Y")
    except Exception:
        return ""


def _num_sum(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def _filter_technician(frame: pd.DataFrame, selected: str) -> pd.DataFrame:
    if not selected or selected == "All Technicians":
        return frame
    if "Technician Name" in frame.columns:
        return frame[frame["Technician Name"].astype(str).str.strip().str.casefold() == selected.strip().casefold()]
    return frame.iloc[0:0]


def _apply_own_scope(frame: pd.DataFrame, *, is_technician: bool, user_id: str) -> pd.DataFrame:
    if not is_technician:
        return frame
    if "User ID" not in frame.columns:
        return frame.iloc[0:0]
    return frame[frame["User ID"].astype(str).str.strip().str.casefold() == str(user_id).strip().casefold()]


def _show_report_result(kind: str, signature: str) -> None:
    result = st.session_state.get(f"_report_result_{kind}")
    if not result or result.get("signature") != signature:
        return
    freshness = "cached session snapshot" if result.get("cache_reused") else "freshly fetched snapshot"
    st.caption(
        f"Data fetched: {result['snapshot']} ({freshness}). "
        f"PDF generated: {result['generated_at']} (download does not fetch Google Sheets again)."
    )
    frame = result["frame"]
    st.dataframe(frame, use_container_width=True, hide_index=True)
    path = Path(result["pdf_path"])
    if path.exists():
        with path.open("rb") as pdf_file:
            st.download_button(
                "Download Hero PDF Report",
                data=pdf_file,
                file_name=path.name,
                mime="application/pdf",
                use_container_width=True,
                key=f"download_{kind}_{signature[:10]}",
            )


def _generate(
    *,
    kind: str,
    signature: str,
    read_report_sheet: Callable[..., pd.DataFrame],
    sheet_name: str,
    force_fresh: bool,
    read_columns: list[str],
    title: str,
    metadata: dict,
    kpis: list[tuple[str, object]],
    columns: list[str],
    filters: Callable[[pd.DataFrame], pd.DataFrame],
    pdf_dir: Path,
    report_kind: str,
) -> None:
    try:
        # This is the only call site that can request a business-data read.
        source = read_report_sheet(sheet_name, force_refresh=force_fresh, columns=read_columns)
        data_snapshot = source.attrs.get("sheets_fetched_at") or _now_report_time().strftime("%d-%m-%Y %I:%M:%S %p IST")
        cache_reused = bool(source.attrs.get("sheets_cache_reused", False))
        filtered = filters(source.copy())
        visible_columns = [column for column in columns if column in filtered.columns]
        visible = filtered[visible_columns].copy() if visible_columns else filtered.copy()
        computed_kpis = list(kpis or [])
        if kind == "service":
            computed_kpis = [
                ("Vehicle Entries", len(visible)),
                ("Total Revenue", _num_sum(visible, "Total Amount")),
                ("Total Labour", _num_sum(visible, "Labour Amount")),
                ("Total Spare", _num_sum(visible, "Spare Amount")),
            ]
        elif kind == "daily":
            computed_kpis = [
                ("Vehicle Entries", len(visible)),
                ("Total Labour Amount", _num_sum(visible, "Labour Amount")),
            ]
        elif kind == "attendance":
            status = visible.get("Attendance Status", pd.Series(dtype=str)).astype(str).str.strip().str.lower()
            computed_kpis = [
                ("Present", int((status == "present").sum())),
                ("Absent", int((status == "absent").sum())),
                ("Half Day", int(status.isin(["half day", "half-day", "halfday"]).sum())),
                ("Total Records", len(visible)),
            ]
        generated_at = _now_report_time().strftime("%d-%m-%Y %I:%M:%S %p IST")
        stamp = _now_report_time().strftime("%Y%m%d_%H%M%S")
        safe_kind = re.sub(r"[^a-z0-9_-]", "_", kind.lower())
        file_path = pdf_dir / f"selva_motors_{safe_kind}_{stamp}.pdf"
        pdf_path = generate_professional_report_pdf(
            visible,
            title,
            file_path,
            metadata=metadata,
            kpis=computed_kpis,
            columns=visible_columns,
            report_kind=report_kind,
        )
        st.session_state[f"_report_result_{kind}"] = {
            "signature": signature,
            "frame": visible,
            "pdf_path": pdf_path,
            "snapshot": data_snapshot,
            "generated_at": generated_at,
            "cache_reused": cache_reused,
        }
        st.success("Report generated. Download it below; downloading does not perform another Sheets read.")
    except PermissionError as exc:
        st.session_state.pop(f"_report_result_{kind}", None)
        st.error(str(exc))
    except Exception as exc:
        # Do not fall back to an older cached report after a failed fresh read.
        st.session_state.pop(f"_report_result_{kind}", None)
        st.error(f"Could not generate the report because the required Google Sheet could not be read: {exc}")


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
    """Render selection controls first; no Sheets read occurs on page open."""
    st.markdown(
        """
        <style>
        .selva-report-banner {padding:18px 20px;border-radius:18px;background:linear-gradient(115deg,#101318,#292d34);border-left:6px solid #e31837;color:#fff;margin:8px 0 16px 0;}
        .selva-report-banner h2 {margin:0 0 5px 0;font-size:22px;font-weight:900;}
        .selva-report-banner p {margin:0;color:#d1d5db;font-size:13px;}
        </style>
        <div class="selva-report-banner"><h2>HERO • SELVA MOTORS REPORT CENTER</h2><p>Select a report and filters, then press GENERATE REPORT. Opening this page does not read business records.</p></div>
        """,
        unsafe_allow_html=True,
    )

    can_view_service = is_admin or is_manager
    can_view_attendance = is_admin or is_manager or is_prathisha
    can_view_daily = is_admin or is_manager or is_technician

    tab_specs = []
    if can_view_service:
        tab_specs.append(("Service Report", "service"))
    if can_view_daily:
        tab_specs.append(("Daily Technician Report", "daily"))
    if can_view_attendance:
        tab_specs.append(("Monthly Attendance", "attendance"))
    tabs = st.tabs([item[0] for item in tab_specs])

    for (tab_title, tab_kind), tab in zip(tab_specs, tabs):
        with tab:
            if tab_kind == "service":
                st.subheader("Service Report")
                scope = st.radio(
                    "Technician scope", ["All Technicians", "Particular Technician"],
                    horizontal=True, key="report_service_scope",
                )
                tech = "All Technicians"
                if scope == "Particular Technician":
                    tech = st.text_input("Technician Name", key="report_service_technician").strip()
                date_filter = st.text_input("Date filter (DD-MM-YYYY, optional)", key="report_service_date")
                reg_filter = st.text_input("Registration number (optional)", key="report_service_registration")
                service_type = st.selectbox("Service type", SERVICE_TYPES, key="report_service_type")
                fresh = st.checkbox("Generate fresh data from Google Sheets", value=False, key="report_service_fresh")
                signature = "|".join([scope, tech, date_filter.strip(), reg_filter.strip().upper(), service_type])

                if st.button("GENERATE SERVICE REPORT", type="primary", use_container_width=True, key="generate_service_report"):
                    def filters(source: pd.DataFrame) -> pd.DataFrame:
                        frame = _apply_own_scope(source, is_technician=False, user_id=user_id)
                        if "Date" in frame.columns:
                            frame["Date"] = frame["Date"].astype(str).map(_norm_date)
                        if tech != "All Technicians":
                            frame = _filter_technician(frame, tech)
                        if date_filter.strip():
                            target = _norm_date(date_filter)
                            frame = frame[frame["Date"] == target] if "Date" in frame else frame.iloc[0:0]
                        if reg_filter.strip():
                            target_reg = re.sub(r"[^A-Z0-9]", "", reg_filter.upper())
                            if "Registration Number" in frame:
                                normalized = frame["Registration Number"].astype(str).str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
                                frame = frame[normalized == target_reg]
                            else:
                                frame = frame.iloc[0:0]
                        if service_type != "All" and "Service Type" in frame:
                            frame = frame[frame["Service Type"].astype(str).str.strip() == service_type]
                        return frame

                    # Summary KPI values are computed inside the filter callback after the one read.
                    # Recalculate them from the saved result below for a single source snapshot.
                    _generate(
                        kind="service", signature=signature, read_report_sheet=read_report_sheet,
                        sheet_name="invoices", force_fresh=fresh,
                        read_columns=[
                            "Date", "Technician Name", "Job Card Number", "Registration Number",
                            "Bike Model", "Service Type", "Labour Amount", "Spare Amount",
                            "Total Amount", "Status",
                        ],
                        title="SELVA MOTORS • SERVICE REPORT",
                        metadata={"Technician": tech, "Date filter": date_filter or "All dates", "Service Type": service_type},
                        kpis=[], columns=[
                            "Technician Name", "Date", "Job Card Number", "Registration Number",
                            "Bike Model", "Service Type", "Labour Amount", "Spare Amount", "Total Amount", "Status",
                        ], filters=filters, pdf_dir=pdf_dir, report_kind="service",
                    )
                result = st.session_state.get("_report_result_service")
                if result and result.get("signature") == signature:
                    frame = result["frame"]
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Vehicle Entries", len(frame))
                    c2.metric("Total Revenue", format_inr(_num_sum(frame, "Total Amount")))
                    c3.metric("Total Labour", format_inr(_num_sum(frame, "Labour Amount")))
                    c4.metric("Total Spare", format_inr(_num_sum(frame, "Spare Amount")))
                    _show_report_result("service", signature)

            elif tab_kind == "daily":
                st.subheader("Daily Technician Report")
                report_date = today_str() if is_technician else st.text_input(
                    "Report date (DD-MM-YYYY)", value=today_str(), key="report_daily_date"
                )
                if is_technician:
                    selected_tech = employee_name
                    st.info("Technician access is limited to your own service records.")
                else:
                    selected_tech_scope = st.radio(
                        "Technician", ["All Technicians", "Particular Technician"],
                        horizontal=True, key="report_daily_scope",
                    )
                    selected_tech = "All Technicians"
                    if selected_tech_scope == "Particular Technician":
                        selected_tech = st.text_input("Technician Name", key="report_daily_technician").strip()
                service_type = st.selectbox("Service type", SERVICE_TYPES, key="report_daily_type")
                reg_filter = st.text_input("Registration number (optional)", key="report_daily_registration")
                fresh = st.checkbox("Generate fresh data from Google Sheets", value=False, key="report_daily_fresh")
                signature = "|".join([report_date, selected_tech, service_type, reg_filter.strip().upper()])

                if st.button("GENERATE DAILY TECHNICIAN REPORT", type="primary", use_container_width=True, key="generate_daily_technician_report"):
                    def filters(source: pd.DataFrame) -> pd.DataFrame:
                        frame = _apply_own_scope(source, is_technician=is_technician, user_id=user_id)
                        if "Date" in frame.columns:
                            frame["Date"] = frame["Date"].astype(str).map(_norm_date)
                            frame = frame[frame["Date"] == _norm_date(report_date)]
                        else:
                            frame = frame.iloc[0:0]
                        if selected_tech != "All Technicians":
                            frame = _filter_technician(frame, selected_tech)
                        if service_type != "All" and "Service Type" in frame:
                            frame = frame[frame["Service Type"].astype(str).str.strip() == service_type]
                        if reg_filter.strip():
                            target = re.sub(r"[^A-Z0-9]", "", reg_filter.upper())
                            if "Registration Number" in frame:
                                actual = frame["Registration Number"].astype(str).str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
                                frame = frame[actual == target]
                        return frame

                    _generate(
                        kind="daily", signature=signature, read_report_sheet=read_report_sheet,
                        sheet_name="invoices", force_fresh=fresh,
                        read_columns=[
                            "Date", "Technician Name", "User ID", "Job Card Number",
                            "Registration Number", "Bike Model", "Service Type", "Labour Amount",
                        ],
                        title="SELVA MOTORS • DAILY TECHNICIAN REPORT",
                        metadata={"Date": _norm_date(report_date), "Technician": selected_tech},
                        kpis=[], columns=[
                            "Technician Name", "Date", "Job Card Number", "Registration Number",
                            "Bike Model", "Service Type", "Labour Amount",
                        ], filters=filters, pdf_dir=pdf_dir, report_kind="daily_technician",
                    )
                result = st.session_state.get("_report_result_daily")
                if result and result.get("signature") == signature:
                    frame = result["frame"]
                    st.metric("Vehicle Entries", len(frame))
                    st.metric("Total Labour Amount", format_inr(_num_sum(frame, "Labour Amount")))
                    _show_report_result("daily", signature)

            elif tab_kind == "attendance":
                st.subheader("Monthly Attendance Report")
                month_default = _now_report_time().strftime("%m-%Y")
                month = st.text_input("Month (MM-YYYY)", value=month_default, key="report_attendance_month")
                if is_technician or is_prathisha:
                    user_scope = "My Records"
                    selected_user = employee_name
                    st.info("Your role is limited to your own attendance records.")
                else:
                    user_scope = st.radio(
                        "User scope", ["All Users", "Particular User"],
                        horizontal=True, key="report_attendance_scope",
                    )
                    selected_user = "All Users"
                    if user_scope == "Particular User":
                        selected_user = st.text_input("User ID or Employee Name", key="report_attendance_user").strip()
                fresh = st.checkbox("Generate fresh data from Google Sheets", value=False, key="report_attendance_fresh")
                signature = "|".join([month.strip(), user_scope, selected_user])

                if st.button("GENERATE MONTHLY ATTENDANCE REPORT", type="primary", use_container_width=True, key="generate_monthly_attendance_report"):
                    valid_month = _month_key(month)
                    if not valid_month:
                        st.error("Enter a valid month in MM-YYYY format.")
                    else:
                        def filters(source: pd.DataFrame) -> pd.DataFrame:
                            frame = _apply_own_scope(
                                source,
                                is_technician=(is_technician or is_prathisha),
                                user_id=user_id,
                            )
                            if "Date" in frame.columns:
                                normalized_dates = frame["Date"].astype(str).map(_norm_date)
                                parsed = pd.to_datetime(normalized_dates, format="%d-%m-%Y", errors="coerce")
                                frame = frame[parsed.dt.strftime("%m-%Y") == valid_month]
                            else:
                                frame = frame.iloc[0:0]
                            if selected_user != "All Users" and user_scope != "My Records":
                                term = selected_user.strip().casefold()
                                name_match = frame.get("Technician Name", pd.Series(index=frame.index, dtype=str)).astype(str).str.casefold() == term
                                id_match = frame.get("User ID", pd.Series(index=frame.index, dtype=str)).astype(str).str.casefold() == term
                                frame = frame[name_match | id_match]
                            return frame

                        _generate(
                            kind="attendance", signature=signature, read_report_sheet=read_report_sheet,
                            sheet_name="attendance", force_fresh=fresh,
                            read_columns=[
                                "Date", "Time", "User ID", "Technician Name", "Role",
                                "Attendance Status", "Distance Meter", "Selfie Saved",
                            ],
                            title="SELVA MOTORS • MONTHLY ATTENDANCE REPORT",
                            metadata={"Month": valid_month, "User": selected_user},
                            kpis=[], columns=[
                                "Date", "Time", "User ID", "Technician Name", "Role",
                                "Attendance Status", "Distance Meter", "Selfie Saved",
                            ], filters=filters, pdf_dir=pdf_dir, report_kind="attendance",
                        )
                result = st.session_state.get("_report_result_attendance")
                if result and result.get("signature") == signature:
                    frame = result["frame"]
                    status = frame.get("Attendance Status", pd.Series(dtype=str)).astype(str).str.strip().str.lower()
                    present = int((status == "present").sum())
                    absent = int((status == "absent").sum())
                    half_day = int(status.isin(["half day", "half-day", "halfday"]).sum())
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Present", present)
                    c2.metric("Absent", absent)
                    c3.metric("Half Day", half_day)
                    c4.metric("Total Records", len(frame))
                    _show_report_result("attendance", signature)
