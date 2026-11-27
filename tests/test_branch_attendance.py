import ast
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from branch_attendance import BRANCHES, normalize_branch, resolve_gps_config, validate_gps_config


def test_branch_names_are_canonical_and_invalid_values_rejected():
    assert BRANCHES == ("Kilvelur", "Thirukkuvalai")
    assert normalize_branch(" kilvelur ") == "Kilvelur"
    assert normalize_branch("THIRUKKUVALAI") == "Thirukkuvalai"
    assert normalize_branch("Thirukkuvalai Branch") is None
    assert normalize_branch("") is None


def test_gps_values_validate_ranges_and_required_values():
    config, error = validate_gps_config("10.759710", "79.742772", "100")
    assert error == ""
    assert config == {"latitude": 10.759710, "longitude": 79.742772, "allowed_radius": 100.0}
    assert validate_gps_config("91", "79", "100")[0] is None
    assert validate_gps_config("10", "181", "100")[0] is None
    assert validate_gps_config("10", "79", "0")[0] is None
    assert validate_gps_config("", "79", "100")[0] is None


def test_each_employee_branch_resolves_only_its_own_coordinates():
    settings = {
        "Kilvelur": {"Latitude": "10.759710", "Longitude": "79.742772", "Allowed Radius": "100"},
        "Thirukkuvalai": {"Latitude": "10.400001", "Longitude": "79.800002", "Allowed Radius": "75"},
    }
    legacy = {"latitude": 10.759710, "longitude": 79.742772, "allowed_radius": 100}
    kilvelur, error_k = resolve_gps_config("Kilvelur", settings, legacy)
    thiru, error_t = resolve_gps_config("Thirukkuvalai", settings, legacy)
    assert not error_k and not error_t
    assert kilvelur["latitude"] == 10.759710
    assert thiru["latitude"] == 10.400001
    assert kilvelur["branch"] != thiru["branch"]
    assert kilvelur["longitude"] != thiru["longitude"]


def test_only_kilvelur_has_legacy_fallback_and_missing_employee_location_blocks():
    legacy = {"latitude": 10.759710, "longitude": 79.742772, "allowed_radius": 100}
    kilvelur, error = resolve_gps_config("Kilvelur", {}, legacy)
    assert not error
    assert kilvelur["source"] == "legacy_code"
    assert kilvelur["latitude"] == 10.759710
    thiru, thiru_error = resolve_gps_config("Thirukkuvalai", {}, legacy)
    assert thiru is None
    assert "not configured" in thiru_error
    missing, missing_error = resolve_gps_config("", {}, legacy)
    assert missing is None
    assert "Location is missing" in missing_error


def test_incomplete_saved_branch_settings_do_not_fall_back_or_guess():
    legacy = {"latitude": 10.759710, "longitude": 79.742772, "allowed_radius": 100}
    settings = {"Thirukkuvalai": {"Latitude": "", "Longitude": "", "Allowed Radius": ""}}
    config, error = resolve_gps_config("Thirukkuvalai", settings, legacy)
    assert config is None
    assert "incomplete or invalid" in error


class WorksheetNotFound(Exception):
    pass


class FakeWorksheet:
    def __init__(self, title, rows=None, cols=6):
        self.title = title
        self.rows = rows or []
        self.col_count = cols
        self.id = 1
        self.updated_cells = []
        self.updated_ranges = []
        self.batch_updates = []

    def row_values(self, row):
        return list(self.rows[row - 1]) if row <= len(self.rows) else []

    def update_cell(self, row, col, value):
        while len(self.rows) < row:
            self.rows.append([])
        while len(self.rows[row - 1]) < col:
            self.rows[row - 1].append("")
        self.rows[row - 1][col - 1] = value
        self.updated_cells.append((row, col, value))

    def add_cols(self, count):
        self.col_count += count

    def update(self, range_name, values, **kwargs):
        self.updated_ranges.append((range_name, values))
        if range_name == "A1:D3":
            self.rows = [list(row) for row in values]

    def batch_update(self, data, **kwargs):
        self.batch_updates.append((data, kwargs))

    def get(self, range_name):
        if range_name == "A2:D":
            return [list(row) for row in self.rows[1:]]
        if range_name == "A:F":
            return [list(row) for row in self.rows]
        return []

    def col_values(self, column):
        return [row[column - 1] if column - 1 < len(row) else "" for row in self.rows]

    def append_row(self, values, **kwargs):
        self.rows.append(list(values))


class FakeSpreadsheet:
    def __init__(self, worksheets=None):
        self.worksheets = worksheets or {}
        self.added = []

    def worksheet(self, name):
        if name not in self.worksheets:
            raise WorksheetNotFound(name)
        return self.worksheets[name]

    def add_worksheet(self, title, rows, cols):
        ws = FakeWorksheet(title, rows=[], cols=cols)
        self.worksheets[title] = ws
        self.added.append(title)
        return ws


class FakeClient:
    def __init__(self, spreadsheet):
        self.spreadsheet = spreadsheet

    def open_by_key(self, key):
        return self.spreadsheet


def _gateway(monkeypatch, google_sheet_module, spreadsheet, schemas):
    monkeypatch.setattr(google_sheet_module, "_has_live_streamlit_context", lambda: False)
    monkeypatch.setattr(google_sheet_module, "st", types.SimpleNamespace(session_state={}))
    return google_sheet_module.GoogleSheetsAccess(
        "test-sheet-id", schemas, client_factory=lambda: FakeClient(spreadsheet)
    )


def test_employee_location_migration_adds_only_header_and_preserves_rows(monkeypatch):
    import google_sheet as gs

    employee_rows = [
        ["User ID", "Password", "Employee Name", "Role", "Status"],
        ["harish", "hash", "Harish", "Technician", "Active"],
        ["yogash", "hash2", "Yogash", "Technician", "Active"],
    ]
    ws = FakeWorksheet("employees", rows=[list(row) for row in employee_rows], cols=5)
    spreadsheet = FakeSpreadsheet({"employees": ws})
    gateway = _gateway(monkeypatch, gs, spreadsheet, {"employees": [*employee_rows[0], "Location"]})

    ok, message = gateway.ensure_employee_location_column()
    assert ok
    assert ws.rows[0] == ["User ID", "Password", "Employee Name", "Role", "Status", "Location"]
    assert ws.rows[1:] == employee_rows[1:]
    assert ws.updated_cells == [(1, 6, "Location")]


def test_employee_location_migration_refuses_unknown_headers(monkeypatch):
    import google_sheet as gs

    original = ["User ID", "Password", "Employee Name", "Role", "Status", "Other Existing Field"]
    ws = FakeWorksheet("employees", rows=[original], cols=6)
    gateway = _gateway(monkeypatch, gs, FakeSpreadsheet({"employees": ws}), {"employees": original[:5] + ["Location"]})
    ok, message = gateway.ensure_employee_location_column()
    assert not ok
    assert "stopped safely" in message
    assert ws.rows[0] == original
    assert not ws.updated_cells


def test_branch_settings_initialization_creates_one_tab_and_no_fake_thirukkuvalai_coordinates(monkeypatch):
    import google_sheet as gs

    spreadsheet = FakeSpreadsheet()
    gateway = _gateway(
        monkeypatch,
        gs,
        spreadsheet,
        {"branch_settings": ["Branch", "Latitude", "Longitude", "Allowed Radius"]},
    )
    ok, message = gateway.ensure_branch_settings_sheet(
        {"latitude": 10.759710, "longitude": 79.742772, "allowed_radius": 100}
    )
    assert ok
    assert spreadsheet.added == ["branch_settings"]
    rows = spreadsheet.worksheets["branch_settings"].rows
    assert rows[0] == ["Branch", "Latitude", "Longitude", "Allowed Radius"]
    assert rows[1] == ["Kilvelur", 10.759710, 79.742772, 100]
    assert rows[2] == ["Thirukkuvalai", "", "", ""]


def test_existing_branch_settings_rows_are_not_overwritten_and_only_missing_rows_append(monkeypatch):
    import google_sheet as gs

    original_rows = [
        ["Branch", "Latitude", "Longitude", "Allowed Radius"],
        ["Kilvelur", 10.759710, 79.742772, 100],
    ]
    ws = FakeWorksheet("branch_settings", rows=[list(row) for row in original_rows], cols=4)
    spreadsheet = FakeSpreadsheet({"branch_settings": ws})
    gateway = _gateway(
        monkeypatch,
        gs,
        spreadsheet,
        {"branch_settings": ["Branch", "Latitude", "Longitude", "Allowed Radius"]},
    )
    ok, _ = gateway.ensure_branch_settings_sheet(
        {"latitude": 10.759710, "longitude": 79.742772, "allowed_radius": 100}
    )
    assert ok
    assert ws.rows[1] == original_rows[1]
    assert ws.rows[2] == ["Thirukkuvalai", "", "", ""]


def _function(tree, name):
    return next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)


def test_attendance_uses_employee_branch_without_manual_branch_selector_and_keeps_attendance_schema():
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    attendance = ast.unparse(_function(tree, "page_attendance"))
    assert "employee_location" in attendance
    assert "get_employee_branch_gps_config" in attendance
    assert "st.selectbox" not in attendance
    assert "attendance_map_card" in attendance

    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"Latitude", "Longitude", "Distance Meter"' in source
    # Location is intentionally not added to the historical attendance worksheet.
    sheets_block = source[source.index('"attendance": ['):source.index('"invoices": [')]
    assert '"Location"' not in sheets_block
    assert 'COMPANY_LAT = 10.759710' in source
    assert 'COMPANY_LON = 79.742772' in source
    assert 'ALLOWED_RADIUS_METER = 100' in source


def test_new_employee_form_requires_location_and_admin_branch_update_is_row_scoped():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'new_location = st.selectbox("Assigned Branch / Location", ["Select branch", *BRANCHES]' in source
    assert 'elif new_location not in BRANCHES:' in source
    assert 'f"F{int(branch_employee_row)}:F{int(branch_employee_row)}"' in source


def test_google_sheet_authorizes_branch_config_read_and_restricts_writes():
    source = (ROOT / "google_sheet.py").read_text(encoding="utf-8")
    assert 'purpose == "branch_config"' in source
    assert 'allowed = logged_in and sheet_name == "branch_settings"' in source
    assert 'sheet_name in {"employees", "branch_settings"} and not is_admin' in source
    assert 'r"F\\d+:F\\d+"' in source
    assert 'r"B\\d+:D\\d+"' in source


def test_unlabelled_employee_f_column_is_not_treated_as_location(monkeypatch):
    import google_sheet as gs
    rows = [
        ["User ID", "Password", "Employee Name", "Role", "Status"],
        ["user1", "hash", "Employee One", "Technician", "Active", "Thirukkuvalai"],
    ]
    ws = FakeWorksheet("employees", rows=rows, cols=6)
    gateway = _gateway(monkeypatch, gs, FakeSpreadsheet({"employees": ws}), {"employees": ["User ID", "Password", "Employee Name", "Role", "Status", "Location"]})
    frame = gateway.read_sheet("employees", purpose="auth", columns=["User ID", "Password", "Employee Name", "Role", "Status", "Location"])
    assert frame.iloc[0]["Location"] == ""


def test_location_header_migration_refuses_existing_unlabelled_f_data(monkeypatch):
    import google_sheet as gs
    rows = [
        ["User ID", "Password", "Employee Name", "Role", "Status"],
        ["user1", "hash", "Employee One", "Technician", "Active", "legacy-value"],
    ]
    ws = FakeWorksheet("employees", rows=rows, cols=6)
    gateway = _gateway(monkeypatch, gs, FakeSpreadsheet({"employees": ws}), {"employees": ["User ID", "Password", "Employee Name", "Role", "Status", "Location"]})
    ok, message = gateway.ensure_employee_location_column()
    assert not ok
    assert "Column F already contains data" in message
    assert ws.rows == rows
    assert not ws.updated_cells


def test_employee_and_branch_settings_updates_are_narrow_row_writes(monkeypatch):
    import google_sheet as gs
    emp_ws = FakeWorksheet("employees", rows=[["User ID", "Password", "Employee Name", "Role", "Status", "Location"]], cols=6)
    branch_ws = FakeWorksheet("branch_settings", rows=[["Branch", "Latitude", "Longitude", "Allowed Radius"], ["Kilvelur", 10.759710, 79.742772, 100]], cols=4)
    spreadsheet = FakeSpreadsheet({"employees": emp_ws, "branch_settings": branch_ws})
    gateway = _gateway(monkeypatch, gs, spreadsheet, {
        "employees": ["User ID", "Password", "Employee Name", "Role", "Status", "Location"],
        "branch_settings": ["Branch", "Latitude", "Longitude", "Allowed Radius"],
        "delete_requests": ["Request ID", "Date", "Time", "Entry ID", "Technician Name", "User ID", "Reason", "Request Status", "Admin Action Date"],
    })
    ok_employee, _ = gateway.update_range("employees", "F2:F2", [["Thirukkuvalai"]])
    ok_branch, _ = gateway.update_range("branch_settings", "B2:D2", [[10.759710, 79.742772, 100]])
    denied, _ = gateway.update_range("employees", "A2:A2", [["other"]])
    assert ok_employee and ok_branch and not denied
    assert emp_ws.updated_ranges == [("F2:F2", [["Thirukkuvalai"]])]
    assert branch_ws.updated_ranges == [("B2:D2", [[10.759710, 79.742772, 100]])]


def test_auto_save_re_resolves_assigned_branch_and_never_accepts_client_branch_argument():
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    function = _function(tree, "auto_save_attendance_from_gps")
    args = [arg.arg for arg in function.args.args]
    body = ast.unparse(function)
    assert args == ["lat", "lon"]
    assert "get_employee_branch_gps_config" in body
    assert "employee_location" in body
    assert "branch_config" not in args


def test_branch_gps_settings_are_saved_in_one_batch_update(monkeypatch):
    import google_sheet as gs

    branch_ws = FakeWorksheet(
        "branch_settings",
        rows=[
            ["Branch", "Latitude", "Longitude", "Allowed Radius"],
            ["Kilvelur", 10.759710, 79.742772, 100],
            ["Thirukkuvalai", "", "", ""],
        ],
        cols=4,
    )
    gateway = _gateway(
        monkeypatch,
        gs,
        FakeSpreadsheet({"branch_settings": branch_ws}),
        {"branch_settings": ["Branch", "Latitude", "Longitude", "Allowed Radius"]},
    )
    updates = [
        (2, [10.759710, 79.742772, 100]),
        (3, [10.700001, 79.900002, 80]),
    ]
    ok, message = gateway.update_branch_settings_rows(updates)
    assert ok, message
    assert len(branch_ws.batch_updates) == 1
    submitted, kwargs = branch_ws.batch_updates[0]
    assert submitted == [
        {"range": "B2:D2", "values": [[10.759710, 79.742772, 100.0]]},
        {"range": "B3:D3", "values": [[10.700001, 79.900002, 80.0]]},
    ]
    assert kwargs["value_input_option"] == "USER_ENTERED"


def test_invalid_branch_gps_batch_update_is_rejected_without_writing(monkeypatch):
    import google_sheet as gs

    branch_ws = FakeWorksheet("branch_settings", rows=[["Branch", "Latitude", "Longitude", "Allowed Radius"]], cols=4)
    gateway = _gateway(
        monkeypatch,
        gs,
        FakeSpreadsheet({"branch_settings": branch_ws}),
        {"branch_settings": ["Branch", "Latitude", "Longitude", "Allowed Radius"]},
    )
    ok, message = gateway.update_branch_settings_rows([(2, [91, 79.5, 100])])
    assert not ok
    assert "Invalid branch GPS values" in message
    assert branch_ws.batch_updates == []


def test_invalid_employee_branch_update_is_rejected_without_writing(monkeypatch):
    import google_sheet as gs

    emp_ws = FakeWorksheet("employees", rows=[["User ID", "Password", "Employee Name", "Role", "Status", "Location"]], cols=6)
    gateway = _gateway(
        monkeypatch,
        gs,
        FakeSpreadsheet({"employees": emp_ws}),
        {"employees": ["User ID", "Password", "Employee Name", "Role", "Status", "Location"]},
    )
    ok, message = gateway.update_range("employees", "F2:F2", [["Thiru Kkuvalai"]])
    assert not ok
    assert "exactly Kilvelur or Thirukkuvalai" in message
    assert emp_ws.updated_ranges == []
