import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ArchitectureGuardTests(unittest.TestCase):
    def test_no_legacy_full_sheet_or_excel_read_calls(self):
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in ROOT.rglob("*.py")
            if "tests" not in path.parts and ".devcontainer" not in path.parts
        )
        for forbidden in ("get_all_values(", "get_all_records(", "pd.read_excel(", ".to_excel(", "ExcelWriter("):
            self.assertNotIn(forbidden, source)

    def test_only_gateway_contains_google_client_operations(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("import gspread", app)
        self.assertNotIn("from google.oauth2", app)
        self.assertNotIn("def google_read_sheet", app)
        gateway = (ROOT / "google_sheet.py").read_text(encoding="utf-8")
        self.assertIn("worksheet.append_row(", gateway)
        self.assertIn("batch_get(ranges)", gateway)
        self.assertIn('spreadsheet.batch_update({"requests": requests})', gateway)

    def test_streamlit_pages_autodiscovery_directory_is_removed(self):
        self.assertFalse((ROOT / "pages").exists())
        self.assertTrue((ROOT / "ui_modules" / "hero_bikes_catalog_en_th.py").is_file())
        self.assertTrue((ROOT / "ui_modules" / "letter_pad.py").is_file())
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("from ui_modules.hero_bikes_catalog_en_th import page_hero_bikes", app)
        self.assertIn("from ui_modules.letter_pad import render_letter_pad_page", app)

    def test_disabled_read_pages_are_not_menu_entries(self):
        tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
        menu = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "menu_page")
        menu_text = ast.get_source_segment((ROOT / "app.py").read_text(encoding="utf-8"), menu)
        for disabled in ["Dashboard", "Search", "Customer Service History", "Google Sheet View Only", "Excel View Only", "Duplicate Upload Finder"]:
            self.assertNotIn(f'"{disabled}"', menu_text)

    def test_report_generation_calls_are_behind_explicit_buttons(self):
        source = (ROOT / "report_center.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        generate_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_generate"]
        self.assertEqual(len(generate_calls), 3)
        # Every call to _generate is syntactically contained within an if-button branch.
        def has_button_guard(node):
            parent_map = {}
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    parent_map[child] = parent
            current = node
            while current in parent_map:
                current = parent_map[current]
                if isinstance(current, ast.If) and "st.button" in ast.get_source_segment(source, current.test):
                    return True
            return False
        self.assertTrue(all(has_button_guard(node) for node in generate_calls))

    def test_daily_pdf_excludes_total_amount_column(self):
        source = (ROOT / "pdf_generator.py").read_text(encoding="utf-8")
        self.assertIn('df = df.drop(columns=["Total Amount"], errors="ignore")', source)


if __name__ == "__main__":
    unittest.main()
