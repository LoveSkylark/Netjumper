"""Pure LibreNMS formatting, neighbor, and firmware helpers."""

import importlib
from pathlib import Path
import tempfile

from slnms_test_support import SlnmsTestCase, device


parsers = importlib.import_module("scripts.slnms_parsers")


class ParserTests(SlnmsTestCase):
    def test_format_mbps_converts_bits_and_rounds_to_two_places(self):
        for bps, expected in ((0, "0.00 Mbps"), (1_000_000, "1.00 Mbps"), (12_345_678, "12.35 Mbps")):
            with self.subTest(bps=bps):
                self.assertEqual(parsers.format_mbps(bps), expected)

    def test_vendor_extracts_icon_basename_and_handles_empty_icon(self):
        for icon, expected in (("images/os/cisco.svg", "Cisco"), ("juniper.png", "Juniper"), ("", ""), (None, "")):
            with self.subTest(icon=icon):
                self.assertEqual(parsers.get_vendor(icon), expected)

    def test_unknown_neighbors_normalize_case_domains_and_parentheses(self):
        devices = [device(sysName="LOCAL.example.test"), None]
        links = [{"remote_hostname": name} for name in ("LOCAL.example.test", "Zulu.example.test", "alpha(extra)", "ALPHA.example.test")] + [None]
        self.assertEqual(parsers.find_unknown_neighbors(devices, links), ["alpha", "zulu"])
        self.assertEqual(parsers.find_unknown_neighbors([], []), [])

    def test_port_list_joins_device_and_port_ids_and_sorts_names(self):
        devices = [device(device_id=1, sysName="Zulu"), device(device_id=2, sysName="alpha")]
        ports = [{"port_id": 10, "ifName": "eth1/1"}, {"port_id": 20, "ifName": "eth1/2"}]
        links = [
            {"remote_hostname": "remote.example.test", "local_device_id": 1, "local_port_id": 10},
            {"remote_hostname": "REMOTE.example.test", "local_device_id": 2, "local_port_id": 20},
            {"remote_hostname": "other.example.test", "local_device_id": 1, "local_port_id": 10},
        ]
        self.assertEqual(parsers.get_sorted_port_list("remote", devices, links, ports), [("alpha", "eth1/2"), ("Zulu", "eth1/1")])

    def test_port_list_retains_unresolved_ids_without_crashing(self):
        links = [{"remote_hostname": "remote", "local_device_id": 999, "local_port_id": 999}]
        self.assertEqual(parsers.get_sorted_port_list("remote", [], links, []), [(None, None)])

    def test_firmware_grouping_normalizes_hardware_and_marks_offline_devices(self):
        devices = [
            device(hardware="Model A/B", hostname="192.0.2.1"),
            device(hardware="Model A/B", hostname="192.0.2.2", status=0),
            device(hardware=None),
        ]
        self.assertEqual(parsers.group_by_hardware_version(devices), {"Model_A_B": {"1.0": ["192.0.2.1", "#192.0.2.2"]}})

    def test_firmware_files_sort_versions_and_addresses(self):
        grouped = {"Model": {"2.0": ["192.0.2.2", "192.0.2.1"], "1.0": ["#192.0.2.3"]}}
        with tempfile.TemporaryDirectory() as directory:
            parsers.save_firmware_files(grouped, directory)
            self.assertEqual((Path(directory) / "Model.txt").read_text(), "> 1.0\n  #192.0.2.3\n> 2.0\n  192.0.2.1\n  192.0.2.2\n")

    def test_firmware_list_without_filter_lists_models_only(self):
        output = self.output(parsers.print_firmware_list, {"Zulu": {}, "Alpha": {}}, None, None)
        self.assertEqual(output, "Alpha\nZulu\n")

    def test_firmware_list_filters_model_and_minimum_version(self):
        grouped = {"Model": {"1.0": ["192.0.2.1"], "2.0": ["192.0.2.2"]}, "Other": {"2.0": ["192.0.2.3"]}}
        output = self.output(parsers.print_firmware_list, grouped, "Model", "2.0")
        self.assertEqual(output, "Model\n192.0.2.2\n")
        all_versions = self.output(parsers.print_firmware_list, grouped, "Model", None)
        self.assertLess(all_versions.index("2.0"), all_versions.index("1.0"))
        self.assertNotIn("192.0.2.3", all_versions)

    def test_bill_date_accepts_timestamp_and_rejects_invalid_dates(self):
        self.assertEqual(parsers.format_bill_date("2026-10-01 12:34:56"), "October 2026")
        with self.assertRaises(ValueError):
            parsers.format_bill_date("not-a-date")