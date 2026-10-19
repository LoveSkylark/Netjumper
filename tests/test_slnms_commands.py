"""LibreNMS reports and filesystem outputs using temporary directories."""

import contextlib
import io
import logging
import logging.handlers
from pathlib import Path
from unittest.mock import Mock, call, patch

from slnms_test_support import SlnmsCommandTestCase, device


class CommandTests(SlnmsCommandTestCase):
    def test_ensure_dir_creates_nested_directory_and_is_idempotent(self):
        path = str(self.directory / "nested" / "output")
        self.assertEqual(self.namespace["_ensure_dir"](path), path)
        self.assertEqual(self.namespace["_ensure_dir"](path), path)
        self.assertTrue(Path(path).is_dir())

    def test_setup_logging_configures_rotation_and_stderr(self):
        self.namespace["setup_logging"]("test.log", self.settings.log_dir)
        self.assertTrue(Path(self.settings.log_dir).is_dir())
        logger = self.namespace["logging"]
        logger.handlers.RotatingFileHandler.assert_called_once_with(
            str(Path(self.settings.log_dir) / "test.log"), maxBytes=5 * 1024 * 1024, backupCount=10,
        )
        logger.StreamHandler.assert_called_once_with(self.namespace["sys"].stderr)
        logger.StreamHandler.return_value.setLevel.assert_called_once_with(logger.ERROR)
        self.assertEqual(logger.basicConfig.call_args.kwargs["handlers"], [
            logger.handlers.RotatingFileHandler.return_value, logger.StreamHandler.return_value,
        ])

    def test_logging_keeps_info_and_warnings_in_file_and_only_errors_on_stderr(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), patch.dict(self.namespace, {"logging": logging}), patch.object(logging, "basicConfig") as configure:
            self.namespace["setup_logging"]("test.log", self.settings.log_dir)
        handlers = configure.call_args.kwargs["handlers"]
        logger = logging.Logger("slnms-test", level=configure.call_args.kwargs["level"])
        for handler in handlers:
            logger.addHandler(handler)
        try:
            logger.info("routine progress")
            logger.warning("partial information")
            logger.error("actual failure")
        finally:
            for handler in handlers:
                handler.close()
        self.assertEqual(stderr.getvalue(), "actual failure\n")
        log_text = (Path(self.settings.log_dir) / "test.log").read_text()
        for message in ("routine progress", "partial information", "actual failure"):
            self.assertIn(message, log_text)

    def test_api_fetch_preserves_order_and_exits_on_api_or_unexpected_error(self):
        first, second = Mock(return_value=[1]), Mock(return_value=[2])
        self.assertEqual(self.namespace["_api_fetch"](first, second), [[1], [2]])
        first.assert_called_once_with()
        second.assert_called_once_with()
        for failure in (self.namespace["APIError"]("denied"), ValueError("bad response")):
            with self.subTest(failure=failure), self.assertRaises(SystemExit) as raised:
                self.namespace["_api_fetch"](Mock(side_effect=failure))
            self.assertEqual(raised.exception.code, 1)

    def test_billing_list_skips_isp_accounts_and_formats_overuse(self):
        self.api.list_bills.return_value = [
            {"bill_id": 1, "bill_name": "Customer", "rate_95th": 2_000_000, "overuse": "-"},
            {"bill_id": 2, "bill_name": "OverLimit", "rate_95th": 3_000_000, "overuse": "10"},
            {"bill_id": 3, "bill_name": "ISP: transit", "rate_95th": 4_000_000, "overuse": "-"},
        ]
        output = self.run_command("cmd_billing")
        self.assertIn("Customer", output)
        self.assertIn("2.00 Mbps", output)
        self.assertIn("over: 10", output)
        self.assertNotIn("ISP:", output)
        self.api.list_devices.assert_not_called()

    def test_billing_customer_history_formats_dates_and_overuse(self):
        self.args.customer = "Customer"
        self.api.list_bills.return_value = [{"bill_id": 7, "bill_name": "Customer"}]
        self.api.get_bill_history.return_value = [
            {"rate_95th": 2_000_000, "bill_datefrom": "2026-10-01", "bill_overuse": 1_000_000},
            {"rate_95th": 3_000_000, "bill_datefrom": "2026-09-01", "bill_overuse": 0},
        ]
        output = self.run_command("cmd_billing")
        self.assertIn("Customer: Customer", output)
        self.assertIn("October 2026", output)
        self.assertIn("September 2026", output)
        self.assertIn("1.00 Mbps", output)
        self.api.get_bill_history.assert_called_once_with(7)

    def test_billing_unknown_customer_exits_without_fetching_history(self):
        self.args.customer = "missing"
        self.api.list_bills.return_value = []
        with self.assertRaises(SystemExit) as raised:
            self.run_command("cmd_billing")
        self.assertEqual(raised.exception.code, 1)
        self.api.get_bill_history.assert_not_called()

    def test_billing_ports_converts_octets_to_bits_and_resolves_device_name(self):
        self.args.customer = "Customer"
        self.args.ports = True
        self.api.list_bills.return_value = [{"bill_id": 7, "bill_name": "Customer"}]
        self.api.list_devices.return_value = [device()]
        self.api.get_bill_ports.return_value = [{"device_id": 1, "port_id": 10, "ifName": "eth1"}]
        self.api.get_port.return_value = {"ifInOctets_rate": 125_000, "ifOutOctets_rate": 250_000}
        output = self.run_command("cmd_billing")
        self.assertIn("Router1", output)
        self.assertIn("eth1", output)
        self.assertIn("1.00 Mbps", output)
        self.assertIn("2.00 Mbps", output)
        self.api.get_bill_ports.assert_called_once_with(7)

    def test_billing_list_with_ports_fetches_devices_once(self):
        self.args.ports = True
        self.api.list_bills.return_value = [{"bill_id": index, "bill_name": f"Customer{index}", "rate_95th": 0, "overuse": "-"} for index in (1, 2)]
        self.api.list_devices.return_value = []
        self.api.get_bill_ports.return_value = []
        self.assertEqual(self.run_command("cmd_billing").count("no ports assigned"), 2)
        self.api.list_devices.assert_called_once_with()
        self.assertEqual(self.api.get_bill_ports.call_args_list, [call(1), call(2)])

    def test_bill_ports_handles_missing_details_and_fetch_errors(self):
        self.api.get_bill_ports.return_value = [{"device_id": 999, "port_id": 10, "ifName": "eth1"}]
        self.api.get_port.side_effect = self.namespace["APIError"]("unavailable")
        output = self.output(self.namespace["_print_bill_ports"], 7, self.api, [])
        self.assertIn("999", output)
        self.assertEqual(output.count("n/a"), 2)
        self.api.get_bill_ports.side_effect = self.namespace["APIError"]("unavailable")
        self.assertIn("could not fetch ports", self.output(self.namespace["_print_bill_ports"], 7, self.api, []))

    def test_inventory_writes_filtered_csv_with_empty_missing_serial_without_logs(self):
        self.args.vendor = "CISCO"
        self.api.list_devices.return_value = [
            device(), device(device_id=2, sysName="Router2", hostname="192.0.2.2", serial=None, version=None, hardware=None),
            device(device_id=3, sysName="Other", icon="juniper.svg"),
        ]
        output = self.run_command("cmd_inventory")
        csv_path = Path(self.settings.info_dir) / "device-list.csv"
        self.assertEqual(csv_path.read_text(),
            "NAME, IP, VENDOR, HARDWARE, VERSION, SERIAL\n"
            "Router1, 192.0.2.1, Cisco, Model A, 1.0, SERIAL1\n"
            "Router2, 192.0.2.2, Cisco, , , \n")
        self.assertIn("Router1  S:SERIAL1", output)
        self.assertIn("Router2  S:\n", output)
        self.assertNotIn("Other", output)
        self.assertEqual(self.namespace["logging"].mock_calls, [])

    def test_inventory_treats_absent_none_and_empty_serial_as_blank(self):
        for serial in (None, "", "absent"):
            with self.subTest(serial=serial):
                entry = device(serial=serial)
                if serial == "absent":
                    entry.pop("serial")
                self.api.list_devices.return_value = [entry]
                output = self.run_command("cmd_inventory")
                self.assertIn("Router1  S:\n", output)
                self.assertTrue((Path(self.settings.info_dir) / "device-list.csv").read_text().endswith(
                    "Router1, 192.0.2.1, Cisco, Model A, 1.0, \n"))
                self.assertEqual(self.namespace["logging"].mock_calls, [])

    def test_inventory_falls_back_to_chassis_serial_in_output_and_csv(self):
        self.api.list_devices.return_value = [device(serial=None)]
        self.api.get_chassis_serial = Mock(return_value="CHASSIS1; CHASSIS2")
        output = self.run_command("cmd_inventory")
        self.api.get_chassis_serial.assert_called_once_with(1)
        self.assertIn("Router1  S:CHASSIS1; CHASSIS2 (chassis)\n", output)
        self.assertTrue((Path(self.settings.info_dir) / "device-list.csv").read_text().endswith(
            "Router1, 192.0.2.1, Cisco, Model A, 1.0, CHASSIS1; CHASSIS2 (chassis)\n"))
        self.assertEqual(self.namespace["logging"].mock_calls, [])

    def test_inventory_keeps_existing_serial_and_skips_filtered_device_lookup(self):
        self.args.vendor = "Cisco"
        self.api.list_devices.return_value = [device(), device(device_id=2, serial=None, icon="juniper.svg")]
        self.api.get_chassis_serial = Mock(return_value="CHASSIS")
        output = self.run_command("cmd_inventory")
        self.assertIn("S:SERIAL1\n", output)
        self.assertNotIn("(chassis)", output)
        self.assertNotIn("(chassis)", (Path(self.settings.info_dir) / "device-list.csv").read_text())
        self.api.get_chassis_serial.assert_not_called()

    def test_inventory_looks_up_chassis_when_normal_serial_is_whitespace(self):
        self.api.list_devices.return_value = [device(serial=" ")]
        self.api.get_chassis_serial = Mock(return_value="CHASSIS")
        self.assertIn("S:CHASSIS (chassis)\n", self.run_command("cmd_inventory"))
        self.api.get_chassis_serial.assert_called_once_with(1)

    def test_inventory_chassis_api_failure_remains_a_real_error(self):
        self.api.list_devices.return_value = [device(serial=None)]
        self.api.get_chassis_serial = Mock(side_effect=self.namespace["APIError"]("denied"))
        with self.assertRaises(SystemExit) as raised:
            self.run_command("cmd_inventory")
        self.assertEqual(raised.exception.code, 1)
        self.namespace["logging"].error.assert_called_once()
        self.namespace["logging"].warning.assert_not_called()

    def test_empty_inventory_still_writes_csv_header(self):
        self.api.list_devices.return_value = []
        self.run_command("cmd_inventory")
        self.assertEqual((Path(self.settings.info_dir) / "device-list.csv").read_text(), "NAME, IP, VENDOR, HARDWARE, VERSION, SERIAL\n")

    def configure_neighbors(self):
        self.api.list_devices.return_value = [device()]
        self.api.list_links.return_value = [
            {"remote_hostname": "REMOTE.example.test", "local_device_id": 1, "local_port_id": 10},
            {"remote_hostname": "other.example.test", "local_device_id": 1, "local_port_id": 20},
        ]
        self.api.get_all_ports.return_value = [{"port_id": 10, "ifName": "eth1/1"}, {"port_id": 20, "ifName": "eth1/2"}]

    def test_neighbors_filters_regex_and_renders_port_details(self):
        self.configure_neighbors()
        self.args.hostname = "^REM"
        self.args.ports = True
        output = self.run_command("cmd_neighbors")
        self.assertIn("remote\n", output)
        self.assertIn("Router1.example.test (eth1/1)", output)
        self.assertNotIn("other", output)

    def test_neighbors_tree_renders_matches_and_no_results(self):
        self.configure_neighbors()
        self.args.tree = True
        self.args.ports = True
        output = self.run_command("cmd_neighbors")
        self.assertIn("Unknown neighbors", output)
        self.assertIn("Router1.example.test", output)
        self.assertIn("eth1", output)
        self.args.hostname = "missing"
        self.assertEqual(self.run_command("cmd_neighbors"), "No unknown neighbors found.\n")

    def test_neighbor_tree_falls_back_for_missing_device_or_ports(self):
        tree = self.namespace["_print_neighbors_tree"]
        output = self.output(tree, ["remote"], [], [{"remote_hostname": "remote", "local_device_id": 999, "local_port_id": 999}], [], True)
        self.assertIn("unknown-device", output)
        self.assertIn("unknown-port", output)
        self.assertIn("no local ports", self.output(tree, ["remote"], [], [], [], True))
        self.assertIn("discovered", self.output(tree, ["remote"], [], [], [], False))

    def test_download_saves_configs_and_skips_missing_ones(self):
        self.api.list_devices.return_value = [device()]
        self.api.list_oxidized.return_value = [{"hostname": hostname} for hostname in ("192.0.2.1", "fallback.example.test", "missing", "empty")]
        self.api.get_oxidized_config.side_effect = ["hostname Router1\n", "hostname fallback\n", "node not found", None]
        output = self.run_command("cmd_download")
        directory = Path(self.settings.config_dir)
        self.assertEqual((directory / "Router1.txt").read_text(), "hostname Router1\n")
        self.assertEqual((directory / "fallback.txt").read_text(), "hostname fallback\n")
        self.assertEqual(sorted(path.name for path in directory.iterdir()), ["Router1.txt", "fallback.txt"])
        self.assertIn("saved 2/4 configs", output)
        self.assertIn("Config missing for: missing", output)
        self.assertIn("Config missing for: empty", output)
        self.namespace["logging"].warning.assert_not_called()

    def test_firmware_command_writes_files_and_switches_tree_rendering(self):
        self.api.list_devices.return_value = [device(), device(hostname="192.0.2.2", version="2.0")]
        self.args.hardware = "Model_A"
        output = self.run_command("cmd_firmware")
        self.assertIn("192.0.2.1", output)
        firmware_file = Path(self.settings.info_dir) / "list_firmware" / "Model_A.txt"
        self.assertIn("> 2.0\n  192.0.2.2", firmware_file.read_text())
        self.args.tree = True
        self.args.version = "2.0"
        output = self.run_command("cmd_firmware")
        self.assertIn("Firmware inventory", output)
        self.assertIn("192.0.2.2", output)
        self.assertNotIn("192.0.2.1", output)

    def test_firmware_tree_reports_no_matching_models(self):
        output = self.output(self.namespace["_print_firmware_tree"], {"Model": {"1.0": ["192.0.2.1"]}}, "missing", None)
        self.assertIn("No firmware entries matched", output)

    def test_api_reports_version_and_unknown_response_shape(self):
        self.api.ping.return_value = {"system": {"local_ver": "26.10"}}
        self.assertIn("LibreNMS 26.10", self.run_command("cmd_api"))
        self.api.ping.return_value = []
        self.assertIn("LibreNMS unknown", self.run_command("cmd_api"))

    def test_api_exits_with_distinct_failure_messages(self):
        self.api.configure_mock(_url=self.settings.url)
        for failure, message in (
            (self.namespace["APIError"]("denied"), "FAIL  denied"),
            (TimeoutError("timed out"), "Connection timed out"),
            (OSError("offline"), "Could not reach API"),
        ):
            with self.subTest(failure=failure):
                self.api.ping.side_effect = failure
                with patch("builtins.print") as printer, self.assertRaises(SystemExit) as raised:
                    self.namespace["cmd_api"](self.args, self.api)
                self.assertEqual(raised.exception.code, 1)
                self.assertIn(message, printer.call_args.args[0])