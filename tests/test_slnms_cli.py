"""LibreNMS argument parsing, server selection, and main dispatch."""

import contextlib
import io
from pathlib import Path
from unittest.mock import Mock, patch

from slnms_test_support import SlnmsCommandTestCase


class CliTests(SlnmsCommandTestCase):
    def parse(self, *arguments):
        return self.namespace["build_parser"]().parse_args(arguments)

    def test_parser_accepts_billing_inventory_and_neighbor_options(self):
        args = self.parse("billing", "Customer", "-p")
        self.assertEqual((args.command, args.customer, args.ports), ("billing", "Customer", True))
        self.assertIsNone(self.parse("billing").customer)
        self.assertEqual(self.parse("inventory", "-v", "Cisco").vendor, "Cisco")
        args = self.parse("neighbors", "^router", "-p", "--tree")
        self.assertEqual((args.hostname, args.ports, args.tree), ("^router", True, True))

    def test_parser_accepts_firmware_filters_and_simple_commands(self):
        args = self.parse("firmware", "Model_A", "2.0", "-t")
        self.assertEqual((args.hardware, args.version, args.tree), ("Model_A", "2.0", True))
        for command in ("download", "api"):
            with self.subTest(command=command):
                self.assertEqual(self.parse(command).command, command)

    def test_parser_accepts_host_netbox_and_server_subcommands(self):
        for action in ("update", "compare"):
            self.assertEqual(self.parse("host", action).host_action, action)
        for action in ("load", "prime", "diff"):
            self.assertEqual(self.parse("nb", action).nb_action, action)
        self.assertEqual(self.parse("server", "list").action, "list")
        args = self.parse("server", "switch", "2")
        self.assertEqual((args.action, args.target), ("switch", "2"))

    def test_parser_rejects_missing_subcommands_and_invalid_arguments(self):
        for arguments in ((), ("missing",), ("host",), ("nb",), ("server",), ("server", "switch"), ("host", "invalid"), ("nb", "invalid"), ("inventory", "--invalid")):
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                self.parse(*arguments)
            self.assertEqual(raised.exception.code, 2)

    def configure_servers(self):
        servers = {"secondary": {"url": "https://secondary.example.test"}, "primary": {"url": "https://primary.example.test"}}
        self.namespace["list_librenms_servers"].return_value = (servers, "secondary")
        return servers

    def test_server_list_is_sorted_and_marks_active_server(self):
        self.configure_servers()
        self.args.action = "list"
        output = self.run_command("cmd_server")
        self.assertIn("1. https://primary.example.test", output)
        self.assertIn("* 2. https://secondary.example.test", output)
        self.assertIn("Active: 2. https://secondary.example.test", output)
        self.namespace["set_librenms_active"].assert_not_called()

    def test_server_list_handles_no_active_server(self):
        self.namespace["list_librenms_servers"].return_value = ({}, "missing")
        self.args.action = "list"
        self.assertIn("Active: (not set)", self.run_command("cmd_server"))

    def test_server_switch_accepts_name_and_sorted_index(self):
        self.configure_servers()
        self.args.action = "switch"
        for target, expected in (("primary", "primary"), ("2", "secondary")):
            with self.subTest(target=target):
                self.namespace["set_librenms_active"].reset_mock()
                self.args.target = target
                self.assertIn(f"set to: {expected}", self.run_command("cmd_server"))
                self.namespace["set_librenms_active"].assert_called_once_with(expected)

    def test_server_switch_rejects_invalid_names_and_indices_without_writing(self):
        self.configure_servers()
        self.args.action = "switch"
        for target in ("0", "3", "missing", "-1"):
            with self.subTest(target=target), self.assertRaises(SystemExit) as raised:
                self.args.target = target
                self.run_command("cmd_server")
            self.assertEqual(raised.exception.code, 1)
        self.namespace["set_librenms_active"].assert_not_called()

    def test_server_switch_forwards_explicit_configuration_path(self):
        self.configure_servers()
        self.args.action = "switch"
        self.args.target = "primary"
        self.args.config = str(self.directory / "custom.yaml")
        self.run_command("cmd_server")
        self.namespace["list_librenms_servers"].assert_called_once_with(Path(self.args.config))
        self.namespace["set_librenms_active"].assert_called_once_with("primary", Path(self.args.config))

    def test_main_loads_settings_initializes_client_and_dispatches_each_command(self):
        cases = (
            ("billing", "Customer", "-p"), ("inventory", "-v", "Cisco"),
            ("neighbors", "remote", "--tree"), ("download",), ("firmware", "Model_A", "2.0"),
            ("host", "compare"), ("nb", "diff"), ("api",), ("server", "list"),
        )
        expected_commands = {"billing", "inventory", "neighbors", "download", "firmware", "host", "nb", "api", "server"}
        self.assertEqual(set(self.namespace["COMMANDS"]), expected_commands)
        for arguments in cases:
            with self.subTest(arguments=arguments):
                command = arguments[0]
                self.namespace["load_settings"].reset_mock()
                self.namespace["load_settings"].return_value = self.settings
                constructor = Mock(return_value=self.api)
                setup_logging = Mock()
                handlers = {name: Mock() for name in expected_commands}
                with patch.dict(self.namespace, {"Client": constructor, "setup_logging": setup_logging, "COMMANDS": handlers}), patch("sys.argv", ["slnms", *arguments]):
                    self.namespace["main"]()
                self.namespace["load_settings"].assert_called_once_with()
                constructor.assert_called_once_with(self.settings.url, self.settings.token)
                setup_logging.assert_called_once_with(f"lnms_{command}.log", self.settings.log_dir)
                args, api = handlers[command].call_args.args
                self.assertIs(api, self.api)
                self.assertIs(args.settings, self.settings)
                self.assertEqual(vars(args), {**vars(self.parse(*arguments)), "settings": self.settings})
                for name, handler in handlers.items():
                    self.assertEqual(handler.call_count, int(name == command))

    def test_main_help_exits_without_loading_settings_or_creating_client(self):
        with patch("sys.argv", ["slnms", "--help"]), self.assertRaises(SystemExit) as raised:
            self.output(self.namespace["main"])
        self.assertEqual(raised.exception.code, 0)
        self.namespace["load_settings"].assert_not_called()