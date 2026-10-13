import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "flask-server"))

from Sections.AssignmentPermissions import can_assign_to


class AssignmentPermissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        roles_path = Path(__file__).resolve().parents[1] / "flask-server" / "roles.json"
        cls.roles = json.loads(roles_path.read_text(encoding="utf-8"))
        cls.public_roles = cls.roles["public"]
        cls.private_roles = cls.roles["private"]

    def grants(self, role):
        return self.public_roles.get(role, self.private_roles.get(role, []))

    def test_sia_alumni_keeps_its_self_selected_public_scope(self):
        grants = self.grants("Sia-Alumni")
        self.assertTrue(can_assign_to(grants, "public", "registration", "public"))
        self.assertTrue(can_assign_to(grants, "public", "task", "public"))
        self.assertFalse(can_assign_to(grants, "member", "registration", "member"))
        self.assertFalse(can_assign_to(grants, "public", "task", "member"))
        self.assertFalse(can_assign_to(grants, "public", "shift"))

    def test_confirmed_member_can_be_assigned_only_within_member_permissions(self):
        grants = self.grants("Mitglied")
        self.assertTrue(can_assign_to(grants, "member", "registration", "member"))
        self.assertTrue(can_assign_to(grants, "member", "task", "member"))
        self.assertTrue(can_assign_to(grants, "public", "shift"))
        self.assertFalse(can_assign_to(grants, "private", "registration", "public"))

    def test_moderator_can_help_with_public_student_and_member_tasks_but_not_private_tasks(self):
        grants = self.grants("Moderator")
        self.assertTrue(can_assign_to(grants, "public", "task", "public"))
        self.assertTrue(can_assign_to(grants, "student", "task", "student"))
        self.assertTrue(can_assign_to(grants, "member", "task", "member"))
        self.assertTrue(can_assign_to(grants, "member", "shift"))
        self.assertFalse(can_assign_to(grants, "private", "task", "private"))
        self.assertFalse(can_assign_to(grants, "member", "task", "private"))

        from Sections.AssignmentPermissions import has_permission

        self.assertTrue(has_permission(grants, "finance.tally.use"))
        self.assertEqual(["Mitglied"], self.roles["requestable_on_change"])
        self.assertIn("Moderator", self.roles["private"])
        self.assertIn("Admin", self.roles["private"])
        self.assertNotIn("Moderator", self.roles["public"])
        self.assertNotIn("Admin", self.roles["public"])

    def test_student_scope_does_not_grant_member_or_shift_permissions(self):
        grants = self.grants("Student")
        self.assertTrue(can_assign_to(grants, "student", "registration", "student"))
        self.assertTrue(can_assign_to(grants, "student", "task", "student"))
        self.assertFalse(can_assign_to(grants, "member", "registration", "public"))
        self.assertFalse(can_assign_to(grants, "public", "shift"))

    def test_admin_wildcard_can_manage_private_scope_but_invalid_scopes_stay_denied(self):
        grants = self.grants("Admin")
        self.assertTrue(can_assign_to(grants, "private", "registration", "private"))
        self.assertTrue(can_assign_to(grants, "private", "task", "private"))
        self.assertFalse(can_assign_to(grants, "unknown", "registration", "private"))
        self.assertFalse(can_assign_to(grants, "public", "unknown", "public"))

    def test_tally_permission_is_member_role_based_not_finance_membership_based(self):
        from Sections.AssignmentPermissions import has_permission

        self.assertTrue(has_permission(self.grants("Mitglied"), "finance.tally.use"))
        self.assertTrue(has_permission(self.grants("Admin"), "finance.tally.use"))
        self.assertFalse(has_permission(self.grants("Gast"), "finance.tally.use"))
        self.assertFalse(has_permission(self.grants("Sia-Alumni"), "finance.tally.use"))


if __name__ == "__main__":
    unittest.main()
