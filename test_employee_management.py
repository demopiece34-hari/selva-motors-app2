import unittest
import pandas as pd

from employee_management import calculate_salary, load_access_context


class EmployeeManagementTests(unittest.TestCase):
    def test_per_day_salary_example(self):
        result = calculate_salary(18000, 30, 26)
        self.assertEqual(result["Per Day Salary"], 600.0)
        self.assertEqual(result["Earned Salary"], 15600.0)
        self.assertEqual(result["Final Salary"], 15600.0)

    def test_salary_components_formula(self):
        result = calculate_salary(18000, 30, 26, overtime=500, incentives=300, bonus=200, advance=1000, deductions=100)
        self.assertEqual(result["Final Salary"], 15500.0)

    def test_rejects_invalid_salary_days(self):
        with self.assertRaises(ValueError):
            calculate_salary(18000, 0, 26)
        with self.assertRaises(ValueError):
            calculate_salary(18000, 30, 31)

    def test_role_permissions_and_individual_deny(self):
        def reader(sheet, purpose):
            if sheet == "employee_roles":
                return pd.DataFrame([{"Role Name": "Technician", "Permissions JSON": '["attendance", "upload_invoice", "employee_profiles"]', "Enabled": "TRUE"}])
            if sheet == "employee_permissions":
                return pd.DataFrame([{"User ID": "u1", "Permission": "upload_invoice", "Allowed": "FALSE"}])
            raise AssertionError(sheet)
        ctx = load_access_context(reader, "u1", "Technician")
        self.assertIn("attendance", ctx["permissions"])
        self.assertIn("employee_profiles", ctx["permissions"])
        self.assertNotIn("upload_invoice", ctx["permissions"])

    def test_disabled_custom_role_fails_closed(self):
        def reader(sheet, purpose):
            if sheet == "employee_roles":
                return pd.DataFrame([{"Role Name": "Workshop Lead", "Permissions JSON": '["reports"]', "Enabled": "FALSE"}])
            if sheet == "employee_permissions":
                return pd.DataFrame(columns=["User ID", "Permission", "Allowed"])
            raise AssertionError(sheet)
        ctx = load_access_context(reader, "u2", "Workshop Lead")
        self.assertEqual(ctx["permissions"], [])
        self.assertTrue(ctx["disabled_role"])


if __name__ == "__main__":
    unittest.main()
