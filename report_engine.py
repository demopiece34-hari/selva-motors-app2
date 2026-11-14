"""Pure calculation and export helpers for SELVA MOTORS monthly reports.

This module reads no files and performs no Google Sheets calls. All inputs are
explicit DataFrames returned by the existing, permission-checked report reader.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from io import BytesIO
import re
import time
from typing import Callable, Iterable

import pandas as pd

REPORT_COLUMNS = [
    "Entry ID", "Date", "Technician Name", "User ID", "Job Card Number",
    "Registration Number", "Bike Model", "Service Type", "Labour Amount",
    "Spare Parts Count", "Spare Amount", "Oil Change Status", "Oil Amount",
    "Total Amount", "Entry Type", "Status",
]

MONEY_COLUMNS = ["Labour Amount", "Spare Amount", "Oil Amount", "Total Amount"]
FINGERPRINT_COLUMNS = [
    "Date", "Technician Name", "User ID", "Job Card Number", "Registration Number",
    "Bike Model", "Service Type", "Labour Amount", "Spare Parts Count", "Spare Amount",
    "Oil Change Status", "Oil Amount", "Total Amount", "Entry Type", "Status",
]


def _as_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def normalize_jobcard(value: object) -> str:
    text = _as_text(value).strip().upper().replace("\u00a0", "")
    text = re.sub(r"\s+", "", text)
    if text in {"", "NAN", "NONE", "NULL", "-", "0"}:
        return ""
    return text


def parse_jobcard_series(value: object) -> tuple[str, int, int] | None:
    """Return (complete prefix including final '-', integer sequence, width)."""
    text = normalize_jobcard(value)
    match = re.fullmatch(r"(.+-)(\d+)", text)
    if not match:
        return None
    return match.group(1), int(match.group(2)), len(match.group(2))


def _money(value: object) -> float:
    text = _as_text(value).replace(",", "").replace("₹", "").strip()
    if text.lower() in {"", "nan", "none", "null", "-"}:
        return 0.0
    try:
        return float(text)
    except (TypeError, ValueError):
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group(0)) if match else 0.0


def _date(value: object) -> pd.Timestamp:
    text = _as_text(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "<na>"}:
        return pd.NaT
    return pd.to_datetime(text.replace("/", "-"), dayfirst=True, errors="coerce")


def _fingerprint(record: dict) -> tuple[str, ...]:
    values = []
    for column in FINGERPRINT_COLUMNS:
        value = record.get(column, "")
        if column == "Job Card Number":
            values.append(normalize_jobcard(value))
        elif column in MONEY_COLUMNS:
            values.append(f"{_money(value):.2f}")
        elif column == "Date":
            parsed = _date(value)
            values.append(parsed.strftime("%Y-%m-%d") if not pd.isna(parsed) else _as_text(value).strip())
        else:
            values.append(re.sub(r"\s+", " ", _as_text(value).strip()).casefold())
    return tuple(values)


def _status_group(value: object) -> str:
    text = re.sub(r"[^a-z]+", " ", _as_text(value).strip().lower()).strip()
    if text in {"completed", "complete", "closed", "delivered", "done"}:
        return "Completed"
    if text in {"pending", "open", "in progress", "inprocess", "not completed"}:
        return "Pending"
    return "Not classified"


def _emit_progress(
    callback: Callable[[str, int, int, int, float | None], None] | None,
    stage: str,
    percent: int,
    processed: int,
    total: int,
    started: float,
) -> None:
    if callback:
        elapsed = time.perf_counter() - started
        remaining = None
        if processed > 0 and total > processed and elapsed >= 0.5:
            speed = processed / max(elapsed, 0.001)
            if speed > 0:
                remaining = (total - processed) / speed
        callback(stage, min(max(int(percent), 0), 100), processed, total, remaining)


def _deduplicate_records(
    frame: pd.DataFrame,
    progress: Callable[[str, int, int, int, float | None], None] | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Deduplicate by Job Card Number; conflicting copies are excluded from totals."""
    if frame.empty:
        empty = frame.copy()
        empty["_JC_NORMALIZED"] = pd.Series(dtype=str)
        empty["_STATUS_GROUP"] = pd.Series(dtype=str)
        empty["_DATA_QUALITY"] = pd.Series(dtype=str)
        return empty, {"duplicate_rows": 0, "conflicting_jobcards": 0, "conflicting_entries": 0, "blank_jobcard_rows": 0, "invalid_jobcard_rows": 0}

    records = frame.to_dict("records")
    chosen: dict[str, dict] = {}
    fingerprints: dict[str, tuple[str, ...]] = {}
    conflicting: set[str] = set()
    duplicate_rows = 0
    blank_jobcard_rows = 0
    invalid_jobcard_rows = 0
    started = time.perf_counter()
    total = len(records)

    for index, record in enumerate(records, start=1):
        jc = normalize_jobcard(record.get("Job Card Number", ""))
        record["_JC_NORMALIZED"] = jc
        record["_STATUS_GROUP"] = _status_group(record.get("Status", ""))
        if not jc:
            blank_jobcard_rows += 1
            entry_id = _as_text(record.get("Entry ID", "")).strip()
            # Entry ID is already part of the existing worksheet schema.
            key = f"ENTRY:{entry_id}" if entry_id else f"BLANKROW:{index}:{_fingerprint(record)}"
        else:
            if parse_jobcard_series(jc) is None:
                invalid_jobcard_rows += 1
            key = f"JC:{jc}"

        fp = _fingerprint(record)
        if key in chosen:
            duplicate_rows += 1
            if fingerprints[key] != fp and key.startswith(("JC:", "ENTRY:")):
                conflicting.add(key)
        else:
            chosen[key] = dict(record)
            fingerprints[key] = fp

        if index % 250 == 0 or index == total:
            # Stage progress is based on actual rows visited, not a timer.
            percent = 25 + int(45 * index / max(total, 1))
            _emit_progress(progress, "Deduplicating Job Card Records", percent, index, total, started)

    output = list(chosen.values())
    for record in output:
        jc = record.get("_JC_NORMALIZED", "")
        key = f"JC:{jc}" if jc else f"ENTRY:{_as_text(record.get('Entry ID', '')).strip()}"
        record["_DATA_QUALITY"] = "Conflicting duplicate - excluded from totals" if key in conflicting else "OK"
        for column in MONEY_COLUMNS:
            record[column] = _money(record.get(column, 0))
        record["_DATE_PARSED"] = _date(record.get("Date", ""))

    result = pd.DataFrame(output)
    meta = {
        "duplicate_rows": duplicate_rows,
        "conflicting_jobcards": sum(1 for key in conflicting if key.startswith("JC:")),
        "conflicting_entries": sum(1 for key in conflicting if key.startswith("ENTRY:")),
        "blank_jobcard_rows": blank_jobcard_rows,
        "invalid_jobcard_rows": invalid_jobcard_rows,
    }
    return result, meta


def build_monthly_bundle(
    source: pd.DataFrame,
    month: int,
    year: int,
    progress: Callable[[str, int, int, int, float | None], None] | None = None,
) -> dict:
    """Build all monthly views from one complete invoice-sheet snapshot."""
    started = time.perf_counter()
    frame = source.copy() if isinstance(source, pd.DataFrame) else pd.DataFrame(source)
    for column in REPORT_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    if frame.empty:
        _emit_progress(progress, "No source records returned", 20, 0, 0, started)
        unique = frame.copy()
        unique["_JC_NORMALIZED"] = ""
        unique["_STATUS_GROUP"] = "Not classified"
        unique["_DATA_QUALITY"] = "OK"
        unique["_DATE_PARSED"] = pd.NaT
        meta = {"duplicate_rows": 0, "conflicting_jobcards": 0, "conflicting_entries": 0, "blank_jobcard_rows": 0, "invalid_jobcard_rows": 0}
    else:
        raw_dates = frame["Date"].map(_date)
        month_mask = raw_dates.notna() & (raw_dates.dt.month == int(month)) & (raw_dates.dt.year == int(year))
        monthly_source = frame.loc[month_mask].copy()
        _emit_progress(progress, "Filtering Selected Month", 20, len(frame), len(frame), started)
        unique, meta = _deduplicate_records(monthly_source, progress)
        _emit_progress(progress, "Validating Job Card Numbers", 74, len(monthly_source), len(monthly_source), started)

    if not unique.empty:
        valid_money_rows = unique[unique["_DATA_QUALITY"] == "OK"].copy()
    else:
        valid_money_rows = unique.copy()

    jobcard_rows = unique[unique["_JC_NORMALIZED"].astype(str).str.len() > 0].copy() if not unique.empty else unique.copy()
    jobcard_rows["Customer Name"] = "Not stored in source sheet"
    jobcard_rows["Job Card Date"] = jobcard_rows.get("Date", pd.Series(dtype=str))
    jobcard_rows["Service Status Classification"] = jobcard_rows.get("_STATUS_GROUP", pd.Series(dtype=str))

    total_jobcards = int(jobcard_rows["_JC_NORMALIZED"].nunique()) if not jobcard_rows.empty else 0
    completed_count = int(jobcard_rows.loc[jobcard_rows["_STATUS_GROUP"] == "Completed", "_JC_NORMALIZED"].nunique()) if not jobcard_rows.empty else 0
    pending_count = int(jobcard_rows.loc[jobcard_rows["_STATUS_GROUP"] == "Pending", "_JC_NORMALIZED"].nunique()) if not jobcard_rows.empty else 0
    unclassified_count = max(total_jobcards - completed_count - pending_count, 0)

    _emit_progress(progress, "Calculating Spare Sales", 80, len(monthly_source) if not frame.empty else 0, len(monthly_source) if not frame.empty else 0, started)
    spare_sales = round(float(valid_money_rows.get("Spare Amount", pd.Series(dtype=float)).sum()), 2)
    oil_amount = round(float(valid_money_rows.get("Oil Amount", pd.Series(dtype=float)).sum()), 2)
    service_collection = round(float(valid_money_rows.get("Total Amount", pd.Series(dtype=float)).sum()), 2)
    _emit_progress(progress, "Calculating Labour Collection", 86, len(monthly_source) if not frame.empty else 0, len(monthly_source) if not frame.empty else 0, started)
    gross_labour = round(float(valid_money_rows.get("Labour Amount", pd.Series(dtype=float)).sum()), 2)
    if not jobcard_rows.empty:
        spare_count_values = pd.to_numeric(jobcard_rows.get("Spare Parts Count", pd.Series(0, index=jobcard_rows.index)), errors="coerce").fillna(0)
        spare_amount_values = pd.to_numeric(jobcard_rows.get("Spare Amount", pd.Series(0, index=jobcard_rows.index)), errors="coerce").fillna(0)
        has_spares = (spare_count_values > 0) | (spare_amount_values > 0)
        spare_jobcards = int(jobcard_rows.loc[has_spares, "_JC_NORMALIZED"].nunique())
    else:
        spare_jobcards = 0

    jobcard_money_rows = valid_money_rows[valid_money_rows["_JC_NORMALIZED"].astype(str).str.len() > 0] if not valid_money_rows.empty else valid_money_rows
    technician_names = sorted({_as_text(x).strip() for x in jobcard_money_rows.get("Technician Name", pd.Series(dtype=str)).tolist() if _as_text(x).strip()}, key=str.casefold)
    technician_rows = []
    for technician in technician_names:
        rows = jobcard_money_rows[jobcard_money_rows["Technician Name"].astype(str).str.strip().str.casefold() == technician.casefold()]
        tech_jc = rows[rows["_JC_NORMALIZED"].astype(str).str.len() > 0]
        jc_count = int(tech_jc["_JC_NORMALIZED"].nunique())
        labour = round(float(rows["Labour Amount"].sum()), 2)
        technician_rows.append({
            "Technician Name": technician,
            "Total Job Cards": jc_count,
            "Completed Job Cards": int(tech_jc.loc[tech_jc["_STATUS_GROUP"] == "Completed", "_JC_NORMALIZED"].nunique()),
            "Pending Job Cards": int(tech_jc.loc[tech_jc["_STATUS_GROUP"] == "Pending", "_JC_NORMALIZED"].nunique()),
            "Spare Parts Sales": round(float(rows["Spare Amount"].sum()), 2),
            "Labour Collection": labour,
            "Average Labour per Job Card": round(labour / max(jc_count, 1), 2),
        })
    technician_summary = pd.DataFrame(technician_rows)

    _emit_progress(progress, "Generating Final Monthly Report", 96, len(monthly_source) if not frame.empty else 0, len(monthly_source) if not frame.empty else 0, started)
    details_columns = [
        "Date", "Job Card Number", "Customer Name", "Registration Number", "Technician Name",
        "Bike Model", "Service Type", "Status", "Labour Amount", "Spare Amount", "Oil Amount", "Total Amount", "_DATA_QUALITY",
    ]
    jobcard_details = jobcard_rows[[c for c in details_columns if c in jobcard_rows.columns]].copy()
    jobcard_details = jobcard_details.rename(columns={"_DATA_QUALITY": "Data Quality"})

    spare_details = valid_money_rows[[c for c in ["Date", "Job Card Number", "Technician Name", "Registration Number", "Spare Parts Count", "Spare Amount", "Oil Amount"] if c in valid_money_rows.columns]].copy()
    labour_details = valid_money_rows[[c for c in ["Date", "Job Card Number", "Technician Name", "Registration Number", "Labour Amount", "Status"] if c in valid_money_rows.columns]].copy()

    summary = pd.DataFrame([{
        "Month": f"{int(month):02d}-{int(year)}",
        "Total Job Cards Created": total_jobcards,
        "Completed Job Cards": completed_count,
        "Pending Job Cards": pending_count,
        "Status Not Classified": unclassified_count,
        "Service Records (unique)": len(unique),
        "Spare Parts Sales (Oil excluded)": spare_sales,
        "Oil Amount": oil_amount,
        "Gross Labour Collection": gross_labour,
        "Total Service Collection": service_collection,
        "Duplicate Rows Removed": meta["duplicate_rows"],
        "Conflicting Job Cards Excluded": meta["conflicting_jobcards"],
        "Conflicting Unlinked Entries Excluded": meta["conflicting_entries"],
    }])

    _emit_progress(progress, "Monthly Reports Ready", 100, len(frame), len(frame), started)
    return {
        "source": frame,
        "month": int(month),
        "year": int(year),
        "records": unique,
        "money_records": valid_money_rows,
        "jobcard_details": jobcard_details,
        "spare_details": spare_details,
        "labour_details": labour_details,
        "technician_summary": technician_summary,
        "summary": summary,
        "meta": meta,
        "totals": {
            "jobcards": total_jobcards,
            "completed": completed_count,
            "pending": pending_count,
            "unclassified": unclassified_count,
            "services": len(unique),
            "spare": spare_sales,
            "oil": oil_amount,
            "labour": gross_labour,
            "service": service_collection,
            "spare_jobcards": spare_jobcards,
        },
        "limitations": {
            "customer_name": "Customer Name is not a column in the existing invoices worksheet.",
            "part_lines": "Individual Part Number, Part Description and Quantity rows are not stored in the existing invoices worksheet. Only Spare Parts Count and Spare Amount are available.",
            "other_charges": "Other Charges is not a column in the existing invoices worksheet.",
            "completion": "The existing Status values must explicitly say Completed/Closed/Delivered or Pending/Open/In Progress. Values such as Active are not interpreted as completion.",
            "jobcard_date": "Date is the invoice record date; there is no separate Job Card Date column.",
        },
    }


def technician_detail(bundle: dict, technician: str) -> dict:
    records = bundle.get("money_records", pd.DataFrame()).copy()
    if not records.empty:
        records = records[records["_JC_NORMALIZED"].astype(str).str.len() > 0].copy()
    if technician and technician != "All Technicians" and not records.empty:
        records = records[records["Technician Name"].astype(str).str.strip().str.casefold() == technician.strip().casefold()]
    jobcards = records.copy()
    jobcard_count = int(jobcards["_JC_NORMALIZED"].nunique()) if not jobcards.empty else 0
    labour = round(float(records.get("Labour Amount", pd.Series(dtype=float)).sum()), 2)
    spare = round(float(records.get("Spare Amount", pd.Series(dtype=float)).sum()), 2)
    completed = int(jobcards.loc[jobcards["_STATUS_GROUP"] == "Completed", "_JC_NORMALIZED"].nunique()) if not jobcards.empty else 0
    pending = int(jobcards.loc[jobcards["_STATUS_GROUP"] == "Pending", "_JC_NORMALIZED"].nunique()) if not jobcards.empty else 0
    return {
        "records": records,
        "jobcards": jobcards,
        "jobcard_count": jobcard_count,
        "completed": completed,
        "pending": pending,
        "unclassified": max(jobcard_count - completed - pending, 0),
        "spare": spare,
        "labour": labour,
        "average_labour": round(labour / max(jobcard_count, 1), 2),
        "service_count": jobcard_count,
    }


def calculate_missing_jobcards(
    source: pd.DataFrame,
    start_value: str,
    end_value: str,
    progress: Callable[[str, int, int, int, float | None], None] | None = None,
    maximum_expected: int = 250_000,
) -> dict:
    start = parse_jobcard_series(start_value)
    end = parse_jobcard_series(end_value)
    if start is None:
        raise ValueError("Enter a valid Month Start Job Card Number ending in a numeric sequence.")
    if end is None:
        raise ValueError("Enter a valid Month End Job Card Number ending in a numeric sequence.")
    if start[0] != end[0]:
        raise ValueError("Start and End Job Card Numbers belong to different prefixes/series.")
    if start[1] > end[1]:
        raise ValueError("Month Start Job Card Number must be less than or equal to Month End Job Card Number.")
    expected_count = end[1] - start[1] + 1
    if expected_count > maximum_expected:
        raise ValueError(f"The requested range contains {expected_count:,} numbers. Please check a smaller range (maximum {maximum_expected:,}).")

    frame = source.copy() if isinstance(source, pd.DataFrame) else pd.DataFrame(source)
    if "Job Card Number" not in frame.columns:
        raise ValueError("The source report snapshot does not contain the Job Card Number column.")
    found_occurrences: dict[int, int] = defaultdict(int)
    blank_rows = 0
    invalid_rows = []
    started = time.perf_counter()
    records = frame["Job Card Number"].tolist()
    total = len(records)
    for index, value in enumerate(records, start=1):
        normalized = normalize_jobcard(value)
        if not normalized:
            blank_rows += 1
        else:
            parsed = parse_jobcard_series(normalized)
            if parsed is None:
                invalid_rows.append({"Source Row": index + 1, "Job Card Number": str(value), "Issue": "Invalid format - sequence suffix not found"})
            elif parsed[0] == start[0] and start[1] <= parsed[1] <= end[1]:
                found_occurrences[parsed[1]] += 1
        if index % 250 == 0 or index == total:
            percent = 10 + int(55 * index / max(total, 1))
            _emit_progress(progress, "Checking Full Source Job Card Records", percent, index, total, started)

    for index, value in enumerate(records, start=1):
        if not normalize_jobcard(value):
            invalid_rows.append({"Source Row": index + 1, "Job Card Number": "", "Issue": "Blank Job Card Number"})

    missing_values = []
    compare_started = time.perf_counter()
    for processed, number in enumerate(range(start[1], end[1] + 1), start=1):
        if number not in found_occurrences:
            missing_values.append(number)
        if processed % 500 == 0 or processed == expected_count:
            percent = 70 + int(25 * processed / max(expected_count, 1))
            _emit_progress(progress, "Comparing Expected Job Card Sequence", percent, processed, expected_count, compare_started)
    width = max(start[2], end[2])
    missing_numbers = [f"{start[0]}{number:0{width}d}" for number in missing_values]
    duplicate_values = [f"{start[0]}{number:0{width}d}" for number, count in found_occurrences.items() if count > 1]
    duplicate_count = sum(count - 1 for count in found_occurrences.values() if count > 1)
    found_count = len(found_occurrences)
    incomplete_reasons = []
    if total == 0:
        incomplete_reasons.append("the invoice source returned zero records")
    if blank_rows:
        incomplete_reasons.append(f"{blank_rows} source row(s) have a blank Job Card Number")
    if invalid_rows:
        incomplete_reasons.append(f"{len(invalid_rows)} source row(s) have an invalid Job Card Number")
    verification = "VERIFIED AGAINST RETURNED SOURCE" if not incomplete_reasons else "INCOMPLETE — POTENTIAL MISSING NUMBERS ONLY"
    _emit_progress(progress, "Missing Job Card Comparison Complete", 100, total, total, started)

    return {
        "start": normalize_jobcard(start_value),
        "end": normalize_jobcard(end_value),
        "prefix": start[0],
        "expected_count": expected_count,
        "found_count": found_count,
        "missing_count": len(missing_numbers),
        "duplicate_count": duplicate_count,
        "missing_numbers": missing_numbers,
        "duplicate_numbers": duplicate_values,
        "blank_source_rows": blank_rows,
        "invalid_records": pd.DataFrame(invalid_rows, columns=["Source Row", "Job Card Number", "Issue"]),
        "verification": verification,
        "verification_reasons": incomplete_reasons,
        "source_record_count": total,
        "date_range_applied": False,
    }


def calculate_expense_totals(gross_labour: float, expenses: Iterable[dict]) -> dict:
    rows = []
    for entry in expenses:
        name = _as_text(entry.get("name", "")).strip()
        amount = _money(entry.get("amount", 0))
        description = _as_text(entry.get("description", "")).strip()
        if name or amount or description:
            rows.append({"Expense Name": name, "Amount": round(amount, 2), "Description": description})
    total_expenses = round(sum(row["Amount"] for row in rows), 2)
    gross = round(_money(gross_labour), 2)
    def is_salary(name: str) -> bool:
        lowered = name.casefold()
        return "salary" in lowered or ("technician" in lowered and ("pay" in lowered or "wage" in lowered))
    salary_total = round(sum(row["Amount"] for row in rows if is_salary(row["Expense Name"])), 2)
    return {
        "gross_labour": gross,
        "total_expenses": total_expenses,
        "technician_salary": salary_total,
        "other_expenses": round(total_expenses - salary_total, 2),
        "net_remaining": round(gross - total_expenses, 2),
        "rows": pd.DataFrame(rows, columns=["Expense Name", "Amount", "Description"]),
    }


def create_excel_report(bundle: dict, expenses: Iterable[dict], audit: dict | None = None) -> bytes:
    """Create a formatted, multi-sheet XLSX without touching source worksheets."""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    expense = calculate_expense_totals(bundle["totals"]["labour"], expenses)
    financial = pd.DataFrame([
        {"Description": "Gross Labour Collection", "Amount": expense["gross_labour"]},
        {"Description": "Total Technician Salary", "Amount": expense["technician_salary"]},
        {"Description": "Total Other Expenses", "Amount": expense["other_expenses"]},
        {"Description": "Total Expenses", "Amount": expense["total_expenses"]},
        {"Description": "Net Remaining Labour Amount", "Amount": expense["net_remaining"]},
    ])
    buffer = BytesIO()
    notes = pd.DataFrame([
        {"Data Field": "Monthly Date Filter", "Available Data / Limitation": "Uses the Date field on the invoices worksheet (record-entry date); there is no separate Job Card Date."},
        {"Data Field": "Customer Name", "Available Data / Limitation": "Not stored in the existing invoices worksheet."},
        {"Data Field": "Part-wise Sales", "Available Data / Limitation": "Part Number, Part Description and individual Quantity lines are not stored; only Spare Parts Count and Spare Amount are available. The existing Spare Amount is used as stored; Oil Amount is not subtracted a second time."},
        {"Data Field": "Other Charges", "Available Data / Limitation": "No Other Charges column exists in the existing invoices worksheet."},
        {"Data Field": "Completion Status", "Available Data / Limitation": "Only explicit Completed / Pending-style values are classified. Values such as Active are left unclassified."},
        {"Data Field": "Manual Invoices", "Available Data / Limitation": "The separate manual_invoices worksheet has no Job Card Number and is not included in this Job Card-based report."},
        {"Data Field": "Expense Persistence", "Available Data / Limitation": "Month-end expenses are session-only and exported; no dedicated approved expense storage exists in this project."},
    ])
    sheets = {
        "Monthly Summary": bundle["summary"],
        "Technician Summary": bundle["technician_summary"],
        "Job Card Details": bundle["jobcard_details"],
        "Spare Sales": bundle["spare_details"],
        "Labour Details": bundle["labour_details"],
        "Expense Details": expense["rows"],
        "Financial Summary": financial,
        "Data Notes": notes,
    }
    if audit:
        sheets["Missing Job Cards"] = pd.DataFrame({"Missing Job Card Number": audit.get("missing_numbers", [])})
        sheets["Duplicate Job Cards"] = pd.DataFrame({"Duplicate Job Card Number": audit.get("duplicate_numbers", [])})
        sheets["Invalid Job Cards"] = audit.get("invalid_records", pd.DataFrame())
        sheets["Audit Summary"] = pd.DataFrame([
            {"Description": "Start Job Card Number", "Result": audit.get("start", "")},
            {"Description": "End Job Card Number", "Result": audit.get("end", "")},
            {"Description": "Expected Job Cards", "Result": audit.get("expected_count", 0)},
            {"Description": "Found Job Cards", "Result": audit.get("found_count", 0)},
            {"Description": "Missing Job Cards", "Result": audit.get("missing_count", 0)},
            {"Description": "Duplicate Rows", "Result": audit.get("duplicate_count", 0)},
            {"Description": "Verification Status", "Result": audit.get("verification", "Not checked")},
        ])
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for title, data in sheets.items():
            safe = re.sub(r"[\\/*?:\[\]]", "_", title)[:31]
            data.to_excel(writer, sheet_name=safe, index=False)
        workbook = writer.book
        header_fill = PatternFill("solid", fgColor="171B24")
        header_font = Font(name="Aptos", bold=True, color="FFFFFF", size=10)
        thin_gray = Side(style="thin", color="E5E7EB")
        for worksheet in workbook.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions if worksheet.max_row >= 1 else "A1"
            for cell in worksheet[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = Border(bottom=thin_gray)
            worksheet.row_dimensions[1].height = 28
            for column_cells in worksheet.columns:
                max_length = 0
                column_index = column_cells[0].column
                for cell in column_cells[:2000]:
                    value = "" if cell.value is None else str(cell.value)
                    max_length = max(max_length, len(value))
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                    if isinstance(cell.value, (int, float)) and any(word in str(worksheet.cell(1, column_index).value).lower() for word in ["amount", "sales", "collection", "labour", "expenses"]):
                        cell.number_format = '₹#,##0.00;[Red]-₹#,##0.00'
                worksheet.column_dimensions[get_column_letter(column_index)].width = min(max(max_length + 2, 12), 38)
    return buffer.getvalue()


def create_missing_jobcard_workbook(audit: dict) -> bytes:
    """Create a dedicated Job Card audit workbook."""
    from io import BytesIO
    buffer = BytesIO()
    summary = pd.DataFrame([
        {"Summary": "Start Job Card Number", "Result": audit.get("start", "")},
        {"Summary": "End Job Card Number", "Result": audit.get("end", "")},
        {"Summary": "Expected Job Cards", "Result": audit.get("expected_count", 0)},
        {"Summary": "Found Job Cards", "Result": audit.get("found_count", 0)},
        {"Summary": "Missing Job Cards", "Result": audit.get("missing_count", 0)},
        {"Summary": "Duplicate Rows", "Result": audit.get("duplicate_count", 0)},
        {"Summary": "Verification Status", "Result": audit.get("verification", "")},
    ])
    missing = pd.DataFrame({"Missing Job Card Number": audit.get("missing_numbers", [])})
    duplicates = pd.DataFrame({"Duplicate Job Card Number": audit.get("duplicate_numbers", [])})
    invalid = audit.get("invalid_records", pd.DataFrame(columns=["Source Row", "Job Card Number", "Issue"]))
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Audit Summary", index=False)
        missing.to_excel(writer, sheet_name="Missing Job Cards", index=False)
        duplicates.to_excel(writer, sheet_name="Duplicate Job Cards", index=False)
        invalid.to_excel(writer, sheet_name="Invalid Records", index=False)
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for cell in worksheet[1]:
                cell.fill = PatternFill("solid", fgColor="171B24")
                cell.font = Font(bold=True, color="FFFFFF")
                cell.alignment = Alignment(horizontal="center", wrap_text=True)
            for cells in worksheet.columns:
                width = min(max(max(len(str(c.value or "")) for c in cells) + 2, 14), 48)
                worksheet.column_dimensions[get_column_letter(cells[0].column)].width = width
    return buffer.getvalue()
