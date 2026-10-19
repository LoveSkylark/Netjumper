"""Host-file planning and writing without touching the system hosts file."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

from slnms_test_support import SlnmsCommandTestCase, device


class HostTests(SlnmsCommandTestCase):
    def test_device_ipv4_accepts_address_cidr_and_hostname_address(self):
        for record, expected in (
            ({"ip": "192.0.2.1"}, "192.0.2.1"),
            ({"ip": " 192.0.2.1/32 "}, "192.0.2.1"),
            ({"hostname": "192.0.2.2"}, "192.0.2.2"),
            ({"ip": None, "hostname": "192.0.2.3"}, "192.0.2.3"),
        ):
            with self.subTest(record=record):
                self.assertEqual(self.namespace["_device_ipv4"](record), expected)
        self.namespace["socket"].gethostbyname.assert_not_called()

    def test_device_ipv4_uses_mocked_dns_and_falls_back_after_invalid_candidate(self):
        resolver = self.namespace["socket"].gethostbyname
        resolver.side_effect = [OSError("bad IP"), "192.0.2.5"]
        self.assertEqual(self.namespace["_device_ipv4"]({"ip": "invalid", "hostname": "router.example.test"}), "192.0.2.5")
        self.assertEqual(resolver.call_args_list, [call("invalid"), call("router.example.test")])

    def test_device_ipv4_returns_none_for_missing_or_unresolvable_values(self):
        for record in ({}, {"ip": " "}, {"ip": "2001:db8::1"}, {"hostname": "not-resolvable"}):
            with self.subTest(record=record):
                self.assertIsNone(self.namespace["_device_ipv4"](record))

    def test_host_dispatch_selects_update_or_compare(self):
        self.namespace["_host_update"] = Mock()
        self.namespace["_host_compare"] = Mock()
        for action in ("update", "compare"):
            self.args.host_action = action
            self.namespace["cmd_host"](self.args, self.api)
            self.namespace[f"_host_{action}"].assert_called_once_with(self.args, self.api)

    def test_host_update_normalizes_names_skips_invalid_ips_and_writes_both_paths(self):
        self.api.list_devices.return_value = [device(), device(sysName="Invalid", ip="", hostname="")]
        writer = self.namespace["_write_hosts_file"] = Mock()
        output = self.run_command("_host_update")
        self.assertEqual(writer.call_args_list, [
            call([("router1", "192.0.2.1")], self.settings.hosts_dir),
            call([("router1", "192.0.2.1")], str(Path(self.settings.info_dir) / "hosts.list")),
        ])
        self.assertIn("1 hosts written", output)
        self.assertIn("Skipped 1 device(s) without a valid IPv4 address.", output)
        self.namespace["logging"].warning.assert_not_called()

    def test_host_compare_reports_additions_changes_and_skipped_devices(self):
        self.api.list_devices.return_value = [
            device(), device(device_id=2, sysName="Added", ip="192.0.2.2"),
            device(device_id=3, sysName="Invalid", ip="", hostname=""),
        ]
        self.namespace["Hosts"].return_value.entries = [
            SimpleNamespace(entry_type="ipv4", names=["router1", "alias"], address="192.0.2.99"),
            SimpleNamespace(entry_type="ipv6", names=["added"], address="2001:db8::1"),
        ]
        output = self.run_command("_host_compare")
        for text in ("To be added:", "added", "To be updated:", "192.0.2.99", "router1", "Skipped 1 device(s)"):
            self.assertIn(text, output)
        self.namespace["Hosts"].return_value.write.assert_not_called()

    def test_host_compare_reports_in_sync_without_writing(self):
        self.api.list_devices.return_value = [device()]
        self.namespace["Hosts"].return_value.entries = [SimpleNamespace(entry_type="ipv4", names=["router1"], address="192.0.2.1")]
        self.assertIn("already up to date", self.run_command("_host_compare"))
        self.namespace["Hosts"].return_value.write.assert_not_called()

    def test_write_hosts_file_constructs_ipv4_entries_and_persists(self):
        self.namespace["_write_hosts_file"]([("router1", "192.0.2.1")], self.settings.hosts_dir)
        self.namespace["Hosts"].assert_called_once_with(path=self.settings.hosts_dir)
        self.namespace["HostsEntry"].assert_called_once_with(entry_type="ipv4", address="192.0.2.1", names=["router1"])
        hosts = self.namespace["Hosts"].return_value
        hosts.add.assert_called_once_with([self.namespace["HostsEntry"].return_value])
        hosts.write.assert_called_once_with()