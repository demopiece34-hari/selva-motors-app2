from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

from branch_attendance import attendance_date_time_fields

ROOT = Path(__file__).resolve().parents[1]


def test_attendance_timestamp_converts_utc_instant_to_ist_date_and_12_hour_time():
    # 2026-11-27 18:23:45 IST, represented as a UTC instant.
    now_utc = datetime(2026, 11, 27, 12, 53, 45, tzinfo=timezone.utc)
    assert attendance_date_time_fields(now_utc) == {
        "Date": "27-11-2026",
        "Time": "06:23:45 PM",
    }


def test_attendance_timestamp_midnight_and_noon_use_correct_12_hour_labels():
    assert attendance_date_time_fields(
        datetime(2026, 11, 27, 0, 5, 6, tzinfo=timezone.utc)
    ) == {"Date": "27-11-2026", "Time": "05:35:06 AM"}
    assert attendance_date_time_fields(
        datetime(2026, 11, 27, 6, 35, 6, tzinfo=timezone.utc)
    ) == {"Date": "27-11-2026", "Time": "12:05:06 PM"}


def test_naive_datetime_is_interpreted_as_ist_for_backward_compatibility():
    assert attendance_date_time_fields(datetime(2026, 11, 27, 0, 2, 3)) == {
        "Date": "27-11-2026",
        "Time": "12:02:03 AM",
    }


def test_attendance_sheet_header_names_and_order_are_unchanged():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    sheets_node = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "SHEETS" for target in node.targets)
    )
    sheets = ast.literal_eval(sheets_node.value)
    assert sheets["attendance"] == [
        "Date", "Time", "User ID", "Technician Name", "Role",
        "Attendance Status", "Latitude", "Longitude", "Distance Meter", "Selfie Saved",
    ]


def test_attendance_append_uses_one_named_date_time_mapping_and_existing_wrapper():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "auto_save_attendance_from_gps"
    )
    body = ast.unparse(fn)
    assert 'attendance_date_time_fields(app_now())' in body
    assert "attendance_timestamp['Date']" in body
    assert '"Date": today' not in body
    assert '"Time": time_str()' not in body
    assert "append_row('attendance', attendance_record)" in body
    assert '**attendance_timestamp' in body


def test_attendance_wrapper_maps_named_fields_using_existing_schema_not_fixed_indices():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    wrapper = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "append_row"
    )
    wrapper_source = ast.unparse(wrapper)
    assert "columns=SHEETS[sheet_name]" in wrapper_source

    gateway_source = (ROOT / "google_sheet.py").read_text(encoding="utf-8")
    gateway_tree = ast.parse(gateway_source)
    gateway_class = next(
        node for node in gateway_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "GoogleSheetsAccess"
    )
    gateway_append = next(
        node for node in gateway_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "append_row"
    )
    gateway_body = ast.unparse(gateway_append)
    assert "ordered_columns = list(columns or self.schemas.get(sheet_name, list(row.keys())))" in gateway_body
    assert "values = [row.get(column, '') for column in ordered_columns]" in gateway_body


def test_attendance_timestamp_rolls_date_at_ist_midnight_not_utc_midnight():
    # 26 Nov 2026 18:40 UTC is already 27 Nov 00:10 in India.
    assert attendance_date_time_fields(
        datetime(2026, 11, 26, 18, 40, 0, tzinfo=timezone.utc)
    ) == {"Date": "27-11-2026", "Time": "12:10:00 AM"}
