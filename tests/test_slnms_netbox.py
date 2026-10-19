"""NetBox command orchestration with mocked normalization and API boundaries."""

from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from slnms_test_support import SlnmsCommandTestCase, device


class NetboxTests(SlnmsCommandTestCase):
    def setUp(self):
        super().setUp()
        self.nb = self.namespace["NetboxClient"].return_value
        self.info = {
            "full_name": "Router1.example.test", "mgmt_ip": "192.0.2.1", "device_type": "Model A",
            "device_role": "network", "serial": "SERIAL1", "location": "DC1",
        }
        self.api.list_devices.return_value = [device()]
        self.namespace["normalize_devices"].return_value = {"router1": self.info}
        self.namespace["build_clean_lookup"].side_effect = lambda lookup: lookup
        self.namespace["find_closest_id"].side_effect = lambda name, lookup: lookup.get(name)
        self.namespace["match_site"].return_value = "DC1"
        self.nb.get_device_types.return_value = {"Model A": 10}
        self.nb.get_roles.return_value = {"network": 20}
        self.nb.get_sites.return_value = {"DC1": 30}
        self.nb.get_all_devices.return_value = []

    def test_nb_connect_validates_credentials_before_constructing_client(self):
        for field in ("nb_url", "nb_token"):
            with self.subTest(field=field):
                original = getattr(self.settings, field)
                setattr(self.settings, field, "")
                with self.assertRaisesRegex(SystemExit, "netbox.url, netbox.token"):
                    self.namespace["_nb_connect"](self.args)
                setattr(self.settings, field, original)
        self.namespace["NetboxClient"].assert_not_called()
        self.assertIs(self.namespace["_nb_connect"](self.args), self.nb)
        self.namespace["NetboxClient"].assert_called_once_with(self.settings.nb_url, self.settings.nb_token)

    def test_nb_dispatch_forwards_api_only_where_required(self):
        for action in ("load", "prime", "diff"):
            self.namespace[f"cmd_nb_{action}"] = Mock()
            self.args.nb_action = action
            self.namespace["cmd_nb"](self.args, self.api)
            expected = (self.args,) if action == "prime" else (self.args, self.api)
            self.namespace[f"cmd_nb_{action}"].assert_called_once_with(*expected)

    def test_nb_diff_reports_missing_devices_and_field_mismatches(self):
        self.namespace["normalize_devices"].return_value = {"router1": self.info, "only-nms": self.info}
        self.namespace["normalize_nb_devices"].return_value = {
            "router1": {**self.info, "serial": "OLD", "mgmt_ip": "192.0.2.99"}, "only-nb": self.info,
        }
        output = self.run_command("cmd_nb_diff")
        for text in ("Missing in NetBox (1)", "Missing in LibreNMS (1)", "only-nms", "only-nb", "Field mismatches (1)", "OLD", "192.0.2.99"):
            self.assertIn(text, output)
        self.nb.create_device.assert_not_called()

    def test_nb_diff_reports_sync_and_ignores_empty_comparison_fields(self):
        self.namespace["normalize_nb_devices"].return_value = {"router1": {**self.info, "serial": "", "mgmt_ip": ""}}
        self.assertIn("are in sync", self.run_command("cmd_nb_diff"))

    def test_nb_prime_does_not_prompt_when_nothing_is_missing(self):
        self.nb.diff_objects.return_value = []
        with patch("builtins.input") as prompt:
            self.assertIn("Nothing to create", self.output(self.namespace["cmd_nb_prime"], self.args))
        prompt.assert_not_called()
        self.nb.create_objects.assert_not_called()

    def test_nb_prime_declining_confirmation_does_not_write(self):
        self.nb.diff_objects.side_effect = [["Region"], [], []]
        with patch("builtins.input", return_value="n"):
            self.assertIn("Aborted", self.output(self.namespace["cmd_nb_prime"], self.args))
        self.nb.create_objects.assert_not_called()

    def test_nb_prime_only_creates_missing_categories_after_confirmation(self):
        self.namespace["sites_from_mapping"].return_value = ["DC1"]
        self.nb.diff_objects.side_effect = [["Region"], [], ["Network"]]
        with patch("builtins.input", return_value=" Y "):
            self.output(self.namespace["cmd_nb_prime"], self.args)
        self.assertEqual(self.nb.create_objects.call_args_list, [call(self.nb.regions, ["Region"]), call(self.nb.device_roles, ["Network"])])

    def test_nb_load_declining_plan_does_not_mutate_netbox(self):
        with patch("builtins.input", return_value="n"):
            output = self.run_command("cmd_nb_load")
        self.assertIn("To be created (1)", output)
        self.assertIn("Aborted", output)
        self.nb.create_device.assert_not_called()
        self.nb.ensure_mgmt_ip.assert_not_called()

    def test_nb_load_creates_planned_device_and_assigns_management_ip(self):
        with patch("builtins.input", return_value="y"):
            output = self.run_command("cmd_nb_load")
        self.nb.create_device.assert_called_once_with("router1", 10, 20, 30)
        self.nb.ensure_mgmt_ip.assert_called_once_with(self.nb.create_device.return_value, "192.0.2.1/32")
        self.assertIn("1 created, 0 updated, 0 skipped", output)

    def test_nb_load_skips_devices_without_type_role_or_site_match(self):
        for missing, message in (("type", "no device type match"), ("role", "no role match"), ("site", "no site match")):
            with self.subTest(missing=missing):
                self.nb.get_device_types.return_value = {} if missing == "type" else {"Model A": 10}
                self.nb.get_roles.return_value = {} if missing == "role" else {"network": 20}
                self.nb.get_sites.return_value = {} if missing == "site" else {"DC1": 30}
                with patch("builtins.input") as prompt:
                    output = self.run_command("cmd_nb_load")
                self.assertIn(message, output)
                prompt.assert_not_called()
        self.nb.create_device.assert_not_called()

    def existing_device(self, **attributes):
        existing = Mock()
        existing.configure_mock(**{
            "name": "Router1.example.test", "device_type": SimpleNamespace(id=10), "role": SimpleNamespace(id=20),
            "site": SimpleNamespace(id=30), "serial": "SERIAL1", "primary_ip4": SimpleNamespace(address="192.0.2.1/32"),
            **attributes,
        })
        return existing

    def test_nb_load_does_not_prompt_or_save_unchanged_device(self):
        existing = self.existing_device()
        self.nb.get_all_devices.return_value = [existing]
        with patch("builtins.input") as prompt:
            output = self.run_command("cmd_nb_load")
        self.assertIn("already up to date", output)
        prompt.assert_not_called()
        existing.save.assert_not_called()

    def test_nb_load_updates_changed_fields_and_management_ip(self):
        existing = self.existing_device(device_type=SimpleNamespace(id=1), role=SimpleNamespace(id=2), site=SimpleNamespace(id=3), serial="OLD", primary_ip4=None)
        self.nb.get_all_devices.return_value = [existing]
        with patch("builtins.input", return_value="y"):
            output = self.run_command("cmd_nb_load")
        self.assertEqual((existing.device_type, existing.role, existing.site, existing.serial), (10, 20, 30, "SERIAL1"))
        existing.save.assert_called_once_with()
        self.nb.ensure_mgmt_ip.assert_called_once_with(existing, "192.0.2.1/32")
        self.nb.create_device.assert_not_called()
        self.assertIn("0 created, 1 updated, 0 skipped", output)