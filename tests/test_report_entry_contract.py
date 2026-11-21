"""Static compatibility checks for the Streamlit Reports entry point."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_ast(filename):
    return ast.parse((ROOT / filename).read_text(encoding="utf-8"))


def _find_function(tree, name):
    return next(
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )


def test_report_center_accepts_daily_only_flag():
    tree = _read_ast("report_center.py")
    function = _find_function(tree, "render_report_center")
    names = {arg.arg for arg in function.args.kwonlyargs + function.args.args}
    assert "daily_only" in names


def test_app_checks_report_module_compatibility_before_calling():
    tree = _read_ast("app.py")
    function = _find_function(tree, "page_reports")
    source = ast.unparse(function)
    assert "inspect.signature(render_report_center)" in source
    assert "missing_parameters" in source
    assert "st.exception(exc)" in source


def test_app_daily_menu_routes_to_daily_only_mode():
    tree = _read_ast("app.py")
    main = _find_function(tree, "main")
    source = ast.unparse(main)
    assert "Daily Service Report" in source
    assert "page_reports(daily_only=True)" in source


def test_daily_only_report_center_entry_does_not_require_a_clicked_button(monkeypatch):
    import importlib.util
    import sys
    import types

    fake_st = types.ModuleType("streamlit")
    fake_st.session_state = {}
    fake_st.markdown = lambda *args, **kwargs: None
    fake_st.caption = lambda *args, **kwargs: None
    fake_st.date_input = lambda label, value=None, **kwargs: value
    fake_st.checkbox = lambda *args, **kwargs: False
    fake_st.button = lambda *args, **kwargs: False
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)

    spec = importlib.util.spec_from_file_location("_selva_report_center_test", ROOT / "report_center.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    module.render_report_center(
        read_report_sheet=lambda *args, **kwargs: None,
        today_str=lambda: "21-11-2026",
        pdf_dir=ROOT / "generated_reports_test",
        is_admin=True,
        is_manager=False,
        is_technician=False,
        is_prathisha=False,
        user_id="admin-1",
        employee_name="Admin",
        daily_only=True,
    )
