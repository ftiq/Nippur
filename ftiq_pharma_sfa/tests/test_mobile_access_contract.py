from odoo.exceptions import ValidationError
from odoo.tests.common import SavepointCase


class TestMobileAccessContract(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_group = cls.env.ref("base.group_user")
        cls.rep_group = cls.env.ref("ftiq_pharma_sfa.group_ftiq_rep")
        cls.supervisor_group = cls.env.ref("ftiq_pharma_sfa.group_ftiq_supervisor")
        cls.manager_group = cls.env.ref("ftiq_pharma_sfa.group_ftiq_manager")
        cls.rep_profile = cls.env.ref("ftiq_pharma_sfa.mobile_access_profile_representative")
        cls.supervisor_profile = cls.env.ref("ftiq_pharma_sfa.mobile_access_profile_supervisor")
        cls.manager_profile = cls.env.ref("ftiq_pharma_sfa.mobile_access_profile_manager")

    @classmethod
    def _create_mobile_user(cls, login, group, profile=None, enabled=True):
        return cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": login,
                "login": login,
                "email": "%s@example.com" % login,
                "company_id": cls.env.company.id,
                "company_ids": [(6, 0, [cls.env.company.id])],
                "groups_id": [(6, 0, [cls.base_group.id, group.id])],
                "ftiq_mobile_access_enabled": enabled,
                "ftiq_mobile_access_profile_id": profile.id if profile else False,
            }
        )

    def test_mobile_access_is_denied_without_profile(self):
        user = self._create_mobile_user(
            "rep_without_profile",
            self.rep_group,
            profile=None,
            enabled=True,
        )
        payload = user.get_ftiq_mobile_access_payload()
        self.assertFalse(payload["enabled"])
        self.assertEqual(payload["reason"], "missing_mobile_profile")
        self.assertFalse(any(payload["navigation"].values()))
        self.assertFalse(any(payload["actions"].values()))

    def test_mobile_access_is_denied_when_disabled(self):
        user = self._create_mobile_user(
            "rep_disabled_mobile",
            self.rep_group,
            profile=self.rep_profile,
            enabled=False,
        )
        payload = user.get_ftiq_mobile_access_payload()
        self.assertFalse(payload["enabled"])
        self.assertEqual(payload["reason"], "mobile_access_disabled")
        self.assertFalse(any(payload["workspaces"].values()))

    def test_profile_role_mismatch_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._create_mobile_user(
                "rep_wrong_profile",
                self.rep_group,
                profile=self.supervisor_profile,
                enabled=True,
            )

    def test_payload_exposes_server_driven_sections_and_actions(self):
        user = self._create_mobile_user(
            "rep_server_contract",
            self.rep_group,
            profile=self.rep_profile,
            enabled=True,
        )
        payload = user.get_ftiq_mobile_access_payload()
        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["role"], "representative")
        self.assertTrue(payload["sections"]["order.details"])
        self.assertTrue(payload["sections"]["collection.thread"])
        self.assertTrue(payload["sections"]["stock_check.lines"])
        self.assertTrue(payload["sections"]["invoice.linked_operations"])
        self.assertTrue(payload["actions"]["invoice.create_collection"])
        self.assertTrue(payload["actions"]["attendance.check_out"])
        self.assertFalse(payload["actions"]["team.publish_note"])
        self.assertFalse(payload["sections"]["purchase.summary"])

    def test_profile_can_disable_a_specific_action(self):
        profile = self.env["ftiq.mobile.access.profile"].create(
            {
                "name": "Representative contract override",
                "code": "rep_contract_override",
                "role": "representative",
            }
        )
        profile.permission_line_ids.filtered(
            lambda line: line.full_key == "action.attendance.check_out"
        ).write({"enabled": False})
        user = self._create_mobile_user(
            "rep_no_checkout_action",
            self.rep_group,
            profile=profile,
            enabled=True,
        )
        payload = user.get_ftiq_mobile_access_payload()
        self.assertTrue(payload["enabled"])
        self.assertFalse(payload["actions"]["attendance.check_out"])
        self.assertTrue(payload["actions"]["order.confirm"])
