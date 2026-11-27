"""Centralized, policy-enforced Google Sheets access for Selva Motors ERP.

Business-data reads are intentionally restricted to explicit authentication and
report-generation purposes. Normal page code cannot read invoice records. The
invoice append path may inspect row 1 once to safely add/map the permitted Oil
Amount header; it never downloads the invoice data body or rewrites old rows.
"""
from __future__ import annotations

from collections import Counter
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Mapping, Optional

import pandas as pd

try:
    import streamlit as st
except Exception:  # pragma: no cover - useful for isolated tests
    st = None


AUTH_SHEET = "employees"
REPORT_SHEETS = {"invoices", "attendance"}
APPEND_SHEETS = {"employees", "attendance", "invoices", "delete_requests", "manual_invoices", "employee_profiles", "employee_roles", "employee_permissions", "employee_salary", "salary_history", "employee_access_logs", "salary_policies"}
RANGE_UPDATE_SHEETS = {"employees", "delete_requests", "branch_settings"}
ROW_DELETE_SHEETS = {"invoices"}
AUTH_COLUMNS = ["User ID", "Password", "Employee Name", "Role", "Status", "Location"]
EMPLOYEE_BASE_HEADERS = ["User ID", "Password", "Employee Name", "Role", "Status"]
BRANCH_SETTINGS_HEADERS = ["Branch", "Latitude", "Longitude", "Allowed Radius"]
EMPLOYEE_BRANCHES = {"kilvelur": "Kilvelur", "thirukkuvalai": "Thirukkuvalai"}

_AUDIT_LOCK = RLock()
_API_AUDIT: list[dict[str, Any]] = []
_CACHED_CLIENT = None
_DEFAULT_GATEWAY: Optional["GoogleSheetsAccess"] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _record_api_call(
    operation: str,
    function_name: str,
    sheet_name: str = "",
    purpose: str = "",
    allowed: bool = True,
    reason: str = "",
) -> None:
    event = {
        "timestamp_utc": _now_iso(),
        "function": function_name,
        "operation": operation,
        "sheet": sheet_name,
        "purpose": purpose,
        "allowed": bool(allowed),
        "reason": reason,
    }
    with _AUDIT_LOCK:
        _API_AUDIT.append(event)


def get_api_call_audit() -> list[dict[str, Any]]:
    with _AUDIT_LOCK:
        return [dict(item) for item in _API_AUDIT]


def get_api_call_audit_summary() -> list[dict[str, Any]]:
    with _AUDIT_LOCK:
        grouped: dict[tuple[str, str, str, str, str, bool], int] = Counter(
            (x["function"], x["operation"], x["sheet"], x["purpose"], x["reason"], x["allowed"])
            for x in _API_AUDIT
        )
    return [
        {
            "Function": key[0],
            "Operation": key[1],
            "Sheet": key[2],
            "Purpose": key[3],
            "Reason": key[4],
            "Calls": count,
            "Allowed": key[5],
        }
        for key, count in sorted(grouped.items())
    ]


def reset_api_call_audit() -> None:
    with _AUDIT_LOCK:
        _API_AUDIT.clear()


def _column_name(index: int) -> str:
    """Convert a 1-based column number to an A1 column label."""
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _has_live_streamlit_context() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx(suppress_warning=True) is not None
    except Exception:
        return False


@dataclass
class GoogleSheetsAccess:
    """Small injectable gateway; accepts a fake client in unit tests."""

    spreadsheet_id: str
    schemas: Mapping[str, list[str]]
    client: Any = None
    client_factory: Optional[Callable[[], Any]] = None

    def __post_init__(self) -> None:
        self._spreadsheet = None
        self._worksheets: dict[str, Any] = {}
        self._worksheet_headers: dict[str, list[str]] = {}

    def _ensure_write_sheet(self, sheet_name: str, allowed_sheets: set[str], operation: str) -> None:
        if sheet_name not in allowed_sheets or sheet_name not in self.schemas:
            raise PermissionError(f"Google Sheets {operation} blocked for worksheet: {sheet_name}")

    def _get_client(self):
        if self.client is not None:
            return self.client
        if self.client_factory is not None:
            self.client = self.client_factory()
            return self.client
        return _authorize_client()

    def _get_spreadsheet(self):
        if self._spreadsheet is not None:
            return self._spreadsheet
        if not self.spreadsheet_id:
            raise RuntimeError("SHEET_ID is missing in Streamlit secrets.")
        client = self._get_client()
        if client is None:
            raise RuntimeError("Google Sheets client is not configured.")
        _record_api_call("META_READ", "open_by_key", reason="Open spreadsheet metadata")
        self._spreadsheet = client.open_by_key(self.spreadsheet_id)
        return self._spreadsheet

    def _get_worksheet(self, sheet_name: str):
        if sheet_name in self._worksheets:
            return self._worksheets[sheet_name]
        # Resolve an existing tab only. Missing sheets fail closed rather than
        # silently creating tabs or writing rows under an unexpected schema.
        spreadsheet = self._get_spreadsheet()
        _record_api_call("META_READ", "worksheet", sheet_name, reason="Resolve existing worksheet metadata")
        worksheet = spreadsheet.worksheet(sheet_name)
        self._worksheets[sheet_name] = worksheet
        return worksheet

    def read_sheet(self, sheet_name: str, *, purpose: Optional[str], columns: Optional[list[str]] = None) -> pd.DataFrame:
        if purpose == "auth":
            allowed = sheet_name == AUTH_SHEET
            selected_columns = AUTH_COLUMNS
        elif purpose == "report":
            allowed = sheet_name in REPORT_SHEETS and bool(columns)
            selected_columns = list(columns or [])
        elif purpose in {"access_config", "employee_admin", "self_profile", "payroll", "branch_config"}:
            role = str(st.session_state.get("role", "")) if st is not None else ""
            access = st.session_state.get("_employee_access", {}) if st is not None else {}
            permissions = set(access.get("permissions", []))
            is_admin = role in {"Admin", "Super Admin"} or bool(access.get("is_admin"))
            logged_in = bool(st.session_state.get("logged_in")) if st is not None else False
            if purpose == "access_config":
                allowed = logged_in and sheet_name in {"employee_roles", "employee_permissions"}
            elif purpose == "employee_admin":
                allowed = logged_in and is_admin and sheet_name in {"employees", "employee_profiles", "employee_roles", "employee_permissions", "employee_access_logs"}
            elif purpose == "self_profile":
                allowed = logged_in and sheet_name in {"employee_profiles", "employee_salary", "salary_history"}
            elif purpose == "branch_config":
                # Branch coordinates are needed by authenticated attendance users;
                # edits remain Admin-only through update_range().
                allowed = logged_in and sheet_name == "branch_settings"
            else:
                allowed = logged_in and (is_admin or "salary_management" in permissions) and sheet_name in {"employees", "employee_salary", "salary_history", "salary_policies"}
            selected_columns = list(columns or self.schemas.get(sheet_name, []))
        else:
            allowed = False
            selected_columns = []

        if not allowed:
            _record_api_call(
                "BLOCKED_READ", "read_sheet", sheet_name, str(purpose or "normal"), False,
                "Business-data read is restricted to employee authentication and explicit reports.",
            )
            raise PermissionError(
                "Google Sheets READ blocked. Only login authentication and explicit report generation may read business data."
            )

        schema_columns = list(self.schemas.get(sheet_name, []))
        if not selected_columns:
            selected_columns = schema_columns
        if (
            not schema_columns
            or not selected_columns
            or len(set(selected_columns)) != len(selected_columns)
            or any(column not in schema_columns for column in selected_columns)
        ):
            raise PermissionError("Explicit, unique report columns from the approved worksheet schema are required.")

        worksheet = self._get_worksheet(sheet_name)
        # Group only the requested columns into contiguous A1 ranges. Multiple ranges
        # are fetched with one batch_get HTTP request, not one request per column.
        selected_indexes = sorted({schema_columns.index(column) + 1 for column in selected_columns})
        groups: list[list[int]] = []
        for index in selected_indexes:
            if not groups or index != groups[-1][-1] + 1:
                groups.append([index])
            else:
                groups[-1].append(index)
        ranges = [f"{_column_name(group[0])}:{_column_name(group[-1])}" for group in groups]

        if len(ranges) == 1:
            _record_api_call(
                "READ", "worksheet.get", sheet_name, purpose, True,
                f"Read only required columns {ranges[0]} for {purpose}.",
            )
            range_values = [worksheet.get(ranges[0])]
        else:
            _record_api_call(
                "READ", "worksheet.batch_get", sheet_name, purpose, True,
                f"Read only required ranges {', '.join(ranges)} for {purpose} in one batch request.",
            )
            batch_get = getattr(worksheet, "batch_get", None)
            if callable(batch_get):
                range_values = batch_get(ranges)
            else:
                # Older gspread-compatible clients still get one bounded read.
                fallback = f"{_column_name(selected_indexes[0])}:{_column_name(selected_indexes[-1])}"
                range_values = [worksheet.get(fallback)]
                groups = [list(range(selected_indexes[0], selected_indexes[-1] + 1))]

        # Confirm the configured column order before mapping values. This avoids
        # silently mislabelling report data if a worksheet header was manually moved.
        group_columns = [[schema_columns[index - 1] for index in group] for group in groups]
        auth_location_header_present = True
        for values, columns_in_group in zip(range_values, group_columns):
            if not values:
                continue
            for offset, expected_header in enumerate(columns_in_group):
                actual_header = str(values[0][offset]).strip() if offset < len(values[0]) else ""
                if purpose == "auth" and expected_header == "Location" and actual_header != "Location":
                    # Until an Admin initializes the Location header, never interpret
                    # an unlabelled F-column value as an employee branch assignment.
                    auth_location_header_present = False
                    continue
                if actual_header and actual_header != expected_header:
                    raise ValueError(
                        f"Worksheet '{sheet_name}' header mismatch at '{expected_header}': found '{actual_header}'."
                    )

        # Reconstruct the selected frame by original worksheet row index.
        row_count = max((len(values) for values in range_values if values), default=0)
        result_rows: list[dict[str, Any]] = []
        for row_index in range(1, row_count):
            record: dict[str, Any] = {}
            for values, columns_in_group in zip(range_values, group_columns):
                row = values[row_index] if row_index < len(values) else []
                for offset, column in enumerate(columns_in_group):
                    record[column] = row[offset] if offset < len(row) else ""
            result_rows.append(record)
        result = pd.DataFrame(result_rows, columns=selected_columns).fillna("")
        if purpose == "auth" and "Location" in result.columns and not auth_location_header_present:
            result["Location"] = ""
        return result

    def _invoice_headers_for_append(self, worksheet: Any, approved_columns: list[str]) -> list[str]:
        """Resolve the live invoice header row and add only the permitted Oil Amount header.

        This narrow row-1 check is cached for this gateway instance. It never reads
        invoice records and never rewrites, reorders, or renames existing headers.
        """
        cached = self._worksheet_headers.get("invoices")
        if cached is None:
            _record_api_call(
                "READ", "worksheet.row_values", "invoices", "schema_migration", True,
                "Read only row 1 once to map invoice append values safely.",
            )
            headers = [str(value or "").strip() for value in worksheet.row_values(1)]
            if not headers:
                raise RuntimeError("Invoice worksheet row 1 is empty. No data was appended; configure the existing headers first.")

            oil_header = "Oil Amount"
            existing_columns = [column for column in approved_columns if column != oil_header]
            missing = [column for column in existing_columns if headers.count(column) != 1]
            if missing:
                raise RuntimeError(
                    "Invoice worksheet headers do not match the existing ERP schema. Missing or duplicate headers: "
                    + ", ".join(missing)
                    + ". No existing columns or records were changed."
                )
            if headers.count(oil_header) > 1:
                raise RuntimeError("More than one Oil Amount header exists. No data was appended; remove the duplicate manually after backup.")
            if oil_header not in headers:
                next_column = len(headers) + 1
                if getattr(worksheet, "col_count", next_column) < next_column:
                    worksheet.add_cols(next_column - int(worksheet.col_count))
                _record_api_call(
                    "WRITE", "worksheet.update_cell", "invoices", "schema_migration", True,
                    "Create the single permitted Oil Amount header at the end of row 1.",
                )
                worksheet.update_cell(1, next_column, oil_header)
                headers.append(oil_header)

            for column in approved_columns:
                if headers.count(column) != 1:
                    raise RuntimeError(f"Invoice header '{column}' is not present exactly once. No invoice row was appended.")
            self._worksheet_headers["invoices"] = headers
            cached = headers
        return list(cached)

    def append_row(self, sheet_name: str, row: Mapping[str, Any], *, columns: Optional[list[str]] = None) -> tuple[bool, str]:
        try:
            management_sheets = {"employee_profiles", "employee_roles", "employee_permissions", "employee_access_logs"}
            payroll_sheets = {"employee_salary", "salary_history", "salary_policies"}
            if sheet_name in management_sheets | payroll_sheets | {"employees"}:
                role = str(st.session_state.get("role", "")) if st is not None else ""
                access = st.session_state.get("_employee_access", {}) if st is not None else {}
                permissions = set(access.get("permissions", []))
                is_admin = role in {"Admin", "Super Admin"} or bool(access.get("is_admin"))
                if _has_live_streamlit_context():
                    if not bool(st.session_state.get("logged_in")):
                        raise PermissionError("Management writes require an authenticated session.")
                    if sheet_name in payroll_sheets and not (is_admin or "salary_management" in permissions):
                        raise PermissionError("Payroll write denied: salary management permission required.")
                    if sheet_name in management_sheets | {"employees"} and not is_admin:
                        if sheet_name != "employee_profiles" or "photo_upload" not in permissions or str(row.get("User ID", "")).casefold() != str(st.session_state.get("user_id", "")).casefold():
                            raise PermissionError("Employee management write denied. Admin access is required.")
            self._ensure_write_sheet(sheet_name, APPEND_SHEETS, "APPEND")
            ordered_columns = list(columns or self.schemas.get(sheet_name, list(row.keys())))
            if not ordered_columns or any(column not in self.schemas[sheet_name] for column in ordered_columns):
                raise PermissionError("Append columns must be present in the approved worksheet schema.")
            row = dict(row)
            if sheet_name == "employees":
                branch = EMPLOYEE_BRANCHES.get(str(row.get("Location", "")).strip().casefold())
                if not branch:
                    raise ValueError("A valid employee Location is required: Kilvelur or Thirukkuvalai.")
                row["Location"] = branch
            worksheet = self._get_worksheet(sheet_name)
            if sheet_name == "invoices" and "Oil Amount" in ordered_columns:
                live_headers = self._invoice_headers_for_append(worksheet, ordered_columns)
                # Match by the worksheet's actual header order so a pre-existing
                # Oil Amount column is reused wherever it already lives.
                values = [row.get(header, "") if header in ordered_columns else "" for header in live_headers]
            else:
                values = [row.get(column, "") for column in ordered_columns]
            _record_api_call(
                "WRITE", "append_row", sheet_name, "normal_write", True,
                "Direct append API; invoice schema check reads row 1 only and no invoice records are read or rewritten.",
            )
            worksheet.append_row(
                values,
                value_input_option="USER_ENTERED",
                insert_data_option="INSERT_ROWS",
            )
            return True, f"{sheet_name} row appended."
        except Exception as exc:
            return False, str(exc)

    def append_rows_atomic(self, entries: list[tuple[str, Mapping[str, Any]]]) -> tuple[bool, str]:
        """Append rows across worksheets in one Google Sheets batchUpdate request."""
        try:
            if not entries:
                return False, "No rows supplied for atomic append."
            role = str(st.session_state.get("role", "")) if st is not None else ""
            access = st.session_state.get("_employee_access", {}) if st is not None else {}
            permissions = set(access.get("permissions", []))
            is_admin = role in {"Admin", "Super Admin"} or bool(access.get("is_admin"))
            if _has_live_streamlit_context():
                if not bool(st.session_state.get("logged_in")):
                    raise PermissionError("Atomic management writes require an authenticated session.")
                for sheet_name, row in entries:
                    if sheet_name in {"employee_salary", "salary_history", "salary_policies"} and not (is_admin or "salary_management" in permissions):
                        raise PermissionError("Payroll write denied.")
                    if sheet_name in {"employees", "employee_profiles", "employee_roles", "employee_permissions", "employee_access_logs"} and not is_admin:
                        raise PermissionError("Employee management atomic writes are Admin-only.")
            requests = []
            for sheet_name, row in entries:
                self._ensure_write_sheet(sheet_name, APPEND_SHEETS, "ATOMIC APPEND")
                columns = list(self.schemas.get(sheet_name, []))
                if not columns:
                    raise PermissionError(f"Missing schema for {sheet_name}.")
                worksheet = self._get_worksheet(sheet_name)
                cells = []
                for column in columns:
                    value = row.get(column, "")
                    if isinstance(value, bool):
                        entered = {"boolValue": value}
                    elif isinstance(value, (int, float)) and not isinstance(value, bool):
                        entered = {"numberValue": float(value)}
                    else:
                        entered = {"stringValue": str(value if value is not None else "")}
                    cells.append({"userEnteredValue": entered})
                requests.append({"appendCells": {"sheetId": int(worksheet.id), "rows": [{"values": cells}], "fields": "userEnteredValue"}})
            spreadsheet = self._get_spreadsheet()
            _record_api_call("WRITE", "spreadsheet.batch_update", ",".join(x[0] for x in entries), "atomic_management_write", True, f"Atomically append {len(entries)} row(s) across worksheets.")
            spreadsheet.batch_update({"requests": requests})
            return True, "Rows appended atomically."
        except Exception as exc:
            return False, str(exc)

    def update_range(self, sheet_name: str, range_name: str, values: list[list[Any]]) -> tuple[bool, str]:
        try:
            role = str(st.session_state.get("role", "")) if st is not None else ""
            access = st.session_state.get("_employee_access", {}) if st is not None else {}
            permissions = set(access.get("permissions", []))
            is_admin = role in {"Admin", "Super Admin"} or bool(access.get("is_admin"))
            if _has_live_streamlit_context():
                if not bool(st.session_state.get("logged_in")):
                    raise PermissionError("Employee account updates require an authenticated session.")
                if sheet_name in {"employees", "branch_settings"} and not is_admin:
                    raise PermissionError("Employee and branch settings updates are Admin-only.")
                if sheet_name == "delete_requests" and not is_admin:
                    raise PermissionError("Delete request approval is restricted to Admin.")
            self._ensure_write_sheet(sheet_name, RANGE_UPDATE_SHEETS, "RANGE UPDATE")
            normalized_range = str(range_name).upper()
            if sheet_name == "employees":
                allowed_ranges = (r"B\d+:E\d+", r"C\d+:E\d+", r"F\d+:F\d+")
            elif sheet_name == "branch_settings":
                allowed_ranges = (r"B\d+:D\d+",)
            else:
                allowed_ranges = (r"H\d+:I\d+",)
            if not any(re.fullmatch(pattern, normalized_range) for pattern in allowed_ranges):
                raise PermissionError("Only approved employee, branch-settings, and delete-request row ranges may be updated.")
            start_cell, end_cell = str(range_name).upper().split(":")
            start_row = int(re.search(r"\d+", start_cell).group())
            end_row = int(re.search(r"\d+", end_cell).group())
            if start_row != end_row or start_row < 2:
                raise PermissionError("Range updates must target one data row (row 2 or later).")
            if sheet_name == "employees":
                expected_width = 4 if start_cell.startswith("B") else (3 if start_cell.startswith("C") else 1)
            elif sheet_name == "branch_settings":
                expected_width = 3
            else:
                expected_width = 2
            if not values or any(len(row) != expected_width for row in values) or len(values) != 1:
                raise ValueError(f"This update range requires exactly one row with {expected_width} values.")
            if sheet_name == "employees" and start_cell.startswith("F"):
                canonical_branch = EMPLOYEE_BRANCHES.get(str(values[0][0] or "").strip().casefold())
                if not canonical_branch:
                    raise ValueError("Employee Location must be exactly Kilvelur or Thirukkuvalai.")
                values = [[canonical_branch]]
            worksheet = self._get_worksheet(sheet_name)
            _record_api_call(
                "WRITE", "worksheet.update", sheet_name, "normal_write", True,
                f"Update the explicitly supplied range {range_name}; no read.",
            )
            worksheet.update(range_name, values, value_input_option="USER_ENTERED")
            return True, f"{sheet_name} {range_name} updated."
        except Exception as exc:
            return False, str(exc)

    def update_branch_settings_rows(self, updates: list[tuple[int, list[Any]]]) -> tuple[bool, str]:
        """Batch-update only the GPS value cells for existing branch rows (Admin only)."""
        try:
            role = str(st.session_state.get("role", "")) if st is not None else ""
            if _has_live_streamlit_context():
                if not bool(st.session_state.get("logged_in")) or role not in {"Admin", "Super Admin"}:
                    raise PermissionError("Only an authenticated Admin can update branch GPS settings.")
            self._ensure_write_sheet("branch_settings", RANGE_UPDATE_SHEETS, "BATCH RANGE UPDATE")
            if not updates:
                raise ValueError("No branch GPS settings were supplied.")
            ranges = []
            seen_rows = set()
            for row_number, values in updates:
                row_number = int(row_number)
                if row_number < 2 or row_number in seen_rows:
                    raise ValueError("Branch settings rows must be unique worksheet rows starting at row 2.")
                seen_rows.add(row_number)
                if len(values) != 3:
                    raise ValueError("Each branch settings row must contain Latitude, Longitude and Allowed Radius.")
                try:
                    lat, lon, radius = map(float, values)
                except (TypeError, ValueError):
                    raise ValueError("Branch GPS values must all be numeric.") from None
                if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 1 <= radius <= 100000):
                    raise ValueError("Invalid branch GPS values: latitude/longitude range or radius is invalid.")
                ranges.append({"range": f"B{row_number}:D{row_number}", "values": [[lat, lon, radius]]})
            worksheet = self._get_worksheet("branch_settings")
            batch_update = getattr(worksheet, "batch_update", None)
            if not callable(batch_update):
                raise RuntimeError("This Google Sheets client does not support branch settings batch updates.")
            _record_api_call("WRITE", "worksheet.batch_update", "branch_settings", "branch_config_update", True,
                             f"Update {len(ranges)} existing branch GPS row(s) in one request; branch labels and other rows are untouched.")
            batch_update(ranges, value_input_option="USER_ENTERED")
            return True, "Branch GPS settings updated in one Google Sheets batch write."
        except Exception as exc:
            return False, str(exc)

    def ensure_employee_location_column(self) -> tuple[bool, str]:
        """Add exactly one Location header at F1 only when the current A:E schema matches."""
        try:
            role = str(st.session_state.get("role", "")) if st is not None else ""
            if _has_live_streamlit_context():
                if not bool(st.session_state.get("logged_in")) or role not in {"Admin", "Super Admin"}:
                    raise PermissionError("Only an authenticated Admin can add the employee Location column.")
            if "employees" not in self.schemas or "Location" not in self.schemas["employees"]:
                raise RuntimeError("The approved employees schema does not include Location.")
            worksheet = self._get_worksheet("employees")
            _record_api_call("READ", "worksheet.row_values", "employees", "employee_schema_check", True,
                             "Read only the employee header row before adding Location.")
            headers = [str(x or "").strip() for x in worksheet.row_values(1)]
            while headers and not headers[-1]:
                headers.pop()
            if headers == EMPLOYEE_BASE_HEADERS + ["Location"]:
                return True, "Employee Location column is already configured at F1."
            if headers != EMPLOYEE_BASE_HEADERS:
                return False, (
                    "Employee header check stopped safely. Expected the existing five columns "
                    "User ID, Password, Employee Name, Role, Status, with no extra columns; "
                    "no employee data was changed."
                )
            current_column_count = int(getattr(worksheet, "col_count", 6) or 6)
            if current_column_count < 6:
                worksheet.add_cols(6 - current_column_count)
            col_values_method = getattr(worksheet, "col_values", None)
            if not callable(col_values_method):
                return False, "Cannot verify whether column F contains existing values. No cells were changed."
            _record_api_call("READ", "worksheet.col_values", "employees", "employee_schema_check", True,
                             "Check only column F so existing unlabelled values are never repurposed as Location.")
            column_f_values = col_values_method(6) or []
            if any(str(value or "").strip() for value in column_f_values[1:]):
                return False, "Column F already contains data without a Location header. No cells were changed; Admin must inspect the existing employee worksheet first."
            _record_api_call("WRITE", "worksheet.update_cell", "employees", "employee_schema_extension", True,
                             "Add the single Location header in the next unused F1 cell; employee rows are untouched.")
            worksheet.update_cell(1, 6, "Location")
            return True, "Added exactly one Location column at F1. Existing employee rows were not modified."
        except Exception as exc:
            return False, str(exc)

    def ensure_branch_settings_sheet(self, kilvelur_config: Mapping[str, Any]) -> tuple[bool, str]:
        """Create one dedicated branch_settings tab on explicit Admin action; never rewrite existing rows."""
        try:
            role = str(st.session_state.get("role", "")) if st is not None else ""
            if _has_live_streamlit_context():
                if not bool(st.session_state.get("logged_in")) or role not in {"Admin", "Super Admin"}:
                    raise PermissionError("Only an authenticated Admin can initialize branch GPS settings.")
            if "branch_settings" not in self.schemas:
                raise RuntimeError("branch_settings is not registered in the approved sheet schema.")
            spreadsheet = self._get_spreadsheet()
            created = False
            try:
                worksheet = self._get_worksheet("branch_settings")
            except Exception as lookup_exc:
                # Create only when Google Sheets explicitly reports that this tab is absent.
                if lookup_exc.__class__.__name__ != "WorksheetNotFound" and "worksheet not found" not in str(lookup_exc).lower():
                    raise
                _record_api_call("META_WRITE", "spreadsheet.add_worksheet", "branch_settings", "branch_config_init", True,
                                 "Create the one required branch GPS configuration worksheet after Admin action.")
                worksheet = spreadsheet.add_worksheet(title="branch_settings", rows=10, cols=4)
                self._worksheets["branch_settings"] = worksheet
                _record_api_call("WRITE", "worksheet.update", "branch_settings", "branch_config_init", True,
                                 "Write branch settings headers and two initial branch rows; no business data is changed.")
                worksheet.update("A1:D3", [
                    BRANCH_SETTINGS_HEADERS,
                    ["Kilvelur", kilvelur_config.get("latitude"), kilvelur_config.get("longitude"), kilvelur_config.get("allowed_radius")],
                    ["Thirukkuvalai", "", "", ""],
                ], value_input_option="USER_ENTERED")
                created = True
            if not created:
                _record_api_call("READ", "worksheet.row_values", "branch_settings", "branch_config_init", True,
                                 "Validate existing branch settings header before any append.")
                headers = [str(x or "").strip() for x in worksheet.row_values(1)]
                if headers != BRANCH_SETTINGS_HEADERS:
                    return False, "Existing branch_settings header does not match Branch, Latitude, Longitude, Allowed Radius. No rows were modified."
                _record_api_call("READ", "worksheet.get", "branch_settings", "branch_config_init", True,
                                 "Read current branch names to avoid duplicate initialization rows.")
                rows = worksheet.get("A2:D") or []
                existing = set()
                for row in rows:
                    if row and str(row[0] if row else "").strip():
                        existing.add(str(row[0]).strip().casefold())
                defaults = [
                    ["Kilvelur", kilvelur_config.get("latitude"), kilvelur_config.get("longitude"), kilvelur_config.get("allowed_radius")],
                    ["Thirukkuvalai", "", "", ""],
                ]
                for item in defaults:
                    if item[0].casefold() not in existing:
                        _record_api_call("WRITE", "worksheet.append_row", "branch_settings", "branch_config_init", True,
                                         f"Append missing {item[0]} settings row without changing existing rows.")
                        worksheet.append_row(item, value_input_option="USER_ENTERED", insert_data_option="INSERT_ROWS")
            return True, "Branch GPS settings are initialized. Kilvelur retains its existing code coordinates; Thirukkuvalai is blank until Admin configures it."
        except Exception as exc:
            return False, str(exc)

    def approve_delete_request(self, invoice_row: int, request_row: int, action_date: str) -> tuple[bool, str]:
        """Atomically delete one invoice row and mark its request Approved."""
        if int(invoice_row) < 2 or int(request_row) < 2:
            return False, "Invoice and request row numbers must be 2 or greater."
        if "invoices" not in self.schemas or "delete_requests" not in self.schemas:
            return False, "Required worksheets are not configured."
        try:
            spreadsheet = self._get_spreadsheet()
            invoice_ws = self._get_worksheet("invoices")
            request_ws = self._get_worksheet("delete_requests")
            requests = [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": int(invoice_ws.id),
                            "dimension": "ROWS",
                            "startIndex": int(invoice_row) - 1,
                            "endIndex": int(invoice_row),
                        }
                    }
                },
                {
                    "updateCells": {
                        "range": {
                            "sheetId": int(request_ws.id),
                            "startRowIndex": int(request_row) - 1,
                            "endRowIndex": int(request_row),
                            "startColumnIndex": 7,
                            "endColumnIndex": 9,
                        },
                        "rows": [{
                            "values": [
                                {"userEnteredValue": {"stringValue": "Approved"}},
                                {"userEnteredValue": {"stringValue": str(action_date)}},
                            ]
                        }],
                        "fields": "userEnteredValue",
                    }
                },
            ]
            _record_api_call(
                "WRITE", "spreadsheet.batch_update", "invoices+delete_requests", "normal_write", True,
                f"Atomically delete invoice row {int(invoice_row)} and approve request row {int(request_row)}.",
            )
            spreadsheet.batch_update({"requests": requests})
            return True, "Invoice deleted and request approved atomically."
        except Exception as exc:
            return False, str(exc)

    def delete_row(self, sheet_name: str, row_number: int) -> tuple[bool, str]:
        try:
            self._ensure_write_sheet(sheet_name, ROW_DELETE_SHEETS, "ROW DELETE")
        except PermissionError as exc:
            return False, str(exc)
        if int(row_number) < 2:
            return False, "Row number must be 2 or greater; row 1 is the header."
        try:
            worksheet = self._get_worksheet(sheet_name)
            _record_api_call(
                "WRITE", "worksheet.delete_rows", sheet_name, "normal_write", True,
                f"Delete explicitly supplied row {row_number}; no read.",
            )
            worksheet.delete_rows(int(row_number))
            return True, f"{sheet_name} row {row_number} deleted."
        except Exception as exc:
            return False, str(exc)


def _authorize_client():
    global _CACHED_CLIENT
    if _CACHED_CLIENT is not None:
        return _CACHED_CLIENT
    if st is None:
        raise RuntimeError("Streamlit is required for Google Sheets secrets.")
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        secrets = st.secrets
        account = secrets.get("gcp_service_account")
        if not account:
            raise RuntimeError("gcp_service_account is missing in Streamlit secrets.")
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_info(account, scopes=scopes)
        _CACHED_CLIENT = gspread.authorize(credentials)
        return _CACHED_CLIENT
    except Exception as exc:
        raise RuntimeError(f"Unable to initialize Google Sheets client: {exc}") from exc


def _get_default_gateway() -> GoogleSheetsAccess:
    global _DEFAULT_GATEWAY
    if _DEFAULT_GATEWAY is None:
        if st is None:
            raise RuntimeError("Streamlit secrets are unavailable.")
        spreadsheet_id = str(st.secrets.get("SHEET_ID", "")).strip()
        # The application supplies schemas with configure_default_gateway().
        _DEFAULT_GATEWAY = GoogleSheetsAccess(spreadsheet_id, {})
    return _DEFAULT_GATEWAY


def configure_default_gateway(spreadsheet_id: str, schemas: Mapping[str, list[str]]) -> None:
    global _DEFAULT_GATEWAY
    normalized_id = str(spreadsheet_id or "").strip()
    if _DEFAULT_GATEWAY is not None and _DEFAULT_GATEWAY.spreadsheet_id == normalized_id and dict(_DEFAULT_GATEWAY.schemas) == dict(schemas):
        return
    _DEFAULT_GATEWAY = GoogleSheetsAccess(normalized_id, schemas)


def configure_gateway_for_testing(gateway: Optional[GoogleSheetsAccess]) -> None:
    global _DEFAULT_GATEWAY
    _DEFAULT_GATEWAY = gateway


def read_sheet(sheet_name: str, *, purpose: Optional[str] = None, columns: Optional[list[str]] = None) -> pd.DataFrame:
    return _get_default_gateway().read_sheet(sheet_name, purpose=purpose, columns=columns)


def append_row(sheet_name: str, row: Mapping[str, Any], *, columns: Optional[list[str]] = None) -> tuple[bool, str]:
    return _get_default_gateway().append_row(sheet_name, row, columns=columns)


def append_rows_atomic(entries: list[tuple[str, Mapping[str, Any]]]) -> tuple[bool, str]:
    return _get_default_gateway().append_rows_atomic(entries)


def update_range(sheet_name: str, range_name: str, values: list[list[Any]]) -> tuple[bool, str]:
    return _get_default_gateway().update_range(sheet_name, range_name, values)


def update_branch_settings_rows(updates: list[tuple[int, list[Any]]]) -> tuple[bool, str]:
    return _get_default_gateway().update_branch_settings_rows(updates)


def ensure_employee_location_column() -> tuple[bool, str]:
    return _get_default_gateway().ensure_employee_location_column()


def ensure_branch_settings_sheet(kilvelur_config: Mapping[str, Any]) -> tuple[bool, str]:
    return _get_default_gateway().ensure_branch_settings_sheet(kilvelur_config)


def delete_row(sheet_name: str, row_number: int) -> tuple[bool, str]:
    return _get_default_gateway().delete_row(sheet_name, row_number)


def approve_delete_request(invoice_row: int, request_row: int, action_date: str) -> tuple[bool, str]:
    return _get_default_gateway().approve_delete_request(invoice_row, request_row, action_date)


def reset_client_cache() -> None:
    """Reset the shared credential client and default gateway (mainly for tests)."""
    global _CACHED_CLIENT, _DEFAULT_GATEWAY
    _CACHED_CLIENT = None
    _DEFAULT_GATEWAY = None
