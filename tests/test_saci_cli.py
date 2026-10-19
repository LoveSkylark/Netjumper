"""Argument parsing and main dispatch without configuration or authentication."""

import contextlib
import io
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from saci_test_support import SaciTestCase


class CliTests(SaciTestCase):
    def parse(self, *arguments):
        with patch("sys.argv", ["saci", *arguments]):
            return self.namespace["parse_args"]()

    def test_parse_ip_port_and_subnet_filters(self):
        args = self.parse("ip", "10.1.1.9", "-p", "/24", "-t", "A")
        self.assertEqual((args.command, args.ip, args.prefix, args.tenant), ("ip", "10.1.1.9", "/24", "A"))
        args = self.parse("port", "1/1", "-i", "101", "-n", "leaf1")
        self.assertEqual((args.port, args.id, args.name), ("1/1", "101", "leaf1"))
        args = self.parse("subnet", "10.1.0.0/16", "-p", "/24", "-t", "A")
        self.assertEqual((args.filter, args.prefix, args.tenant), ("10.1.0.0/16", "/24", "A"))

    def test_parse_every_clean_subcommand(self):
        for command in ("aaep", "domain", "static", "vlan", "vrf", "bd", "bd-gw", "gw-conflict", "epg", "empty", "contract", "overlap", "subnet", "filter"):
            with self.subTest(command=command):
                args = self.parse("clean", command)
                self.assertEqual((args.command, args.clean_cmd), ("clean", command))
        for command in ("static", "bd-gw", "gw-conflict", "overlap", "subnet", "filter"):
            with self.subTest(tenant_command=command):
                self.assertEqual(self.parse("clean", command, "-t", "A").tenant, "A")

    def test_parse_aaep_endpoint_option_boolean_or_path(self):
        self.assertFalse(self.parse("aaep").list_endpoints)
        self.assertIs(self.parse("aaep", "Servers", "-l").list_endpoints, True)
        self.assertEqual(self.parse("aaep", "Servers", "-l", "A/App/Web").list_endpoints, "A/App/Web")

    def test_parse_vpc_vmm_and_route_options(self):
        args = self.parse("vpc", "101-102", "Bundle", "vlan")
        self.assertEqual((args.nodes, args.interface, args.vpc_action), ("101-102", "Bundle", "vlan"))
        args = self.parse("vmm", "VMware/Production", "vlan", "dynamic", "-t", "A")
        self.assertEqual((args.domain, args.vmm_action, args.vmm_vlan_cmd, args.tenant), ("VMware/Production", "vlan", "dynamic", "A"))
        args = self.parse("route", "A:VRF", "10.1", "-p", "/24", "-l", "-d")
        self.assertEqual((args.vrf, args.filter, args.prefix, args.local, args.external, args.detail), ("A:VRF", "10.1", "/24", True, False, True))

    def test_parser_rejects_missing_or_invalid_commands_and_conflicting_route_scopes(self):
        for arguments in ((), ("unknown",), ("clean",), ("ip",), ("vpc", "101-102", "Bundle", "invalid"), ("vmm", "Production", "vlan", "invalid"), ("route", "A:VRF", "-l", "-x")):
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                self.parse(*arguments)
            self.assertEqual(raised.exception.code, 2)

    def test_main_constructs_client_logs_in_and_forwards_each_command(self):
        cases = (
            (("ip", "10.1.1.9", "-p", "/24", "-t", "A"), "handle_ip_command", ("10.1.1.9", "/24", "A")),
            (("port", "1/1", "-i", "101"), "handle_port_command", ("1/1", "101", None)),
            (("vpc", "101-102", "Bundle", "vlan"), "handle_vpc_command", ("101-102", "Bundle", "vlan")),
            (("vlan", "100"), "handle_vlan_command", (100,)),
            (("tenant", "A"), "handle_tenant_command", ("A",)),
            (("clean", "static", "-t", "A"), "handle_clean_command", ("static", "A")),
            (("epg", "Web", "-t", "A"), "handle_epg_command", ("Web", "A")),
            (("contract", "HTTP", "-t", "A", "-f"), "handle_contract_command", ("HTTP", "A", True)),
            (("subnet", "10.1", "-p", "/24", "-t", "A"), "handle_subnet_command", ("A", "/24", "10.1")),
            (("aaep", "Servers", "-l", "A/App/Web"), "handle_aaep_command", ("Servers", "A/App/Web")),
            (("vmm",), "handle_vmm_command", ()),
            (("vmm", "Production", "-t", "A"), "handle_vmm_epg_command", ("Production", "A")),
            (("vmm", "Production", "vlan"), "handle_vmm_vlan_command", ("all", "Production", None)),
            (("vmm", "Production", "vlan", "static", "-t", "A"), "handle_vmm_vlan_command", ("static", "Production", "A")),
            (("vmm", "Production", "vlan", "dynamic"), "handle_vmm_vlan_command", ("dynamic", "Production", None)),
            (("route", "A:VRF", "10.1", "-p", "/24", "-x", "-d"), "handle_route_command", ("A:VRF", True, "10.1", "/24", False, True)),
        )
        settings = SimpleNamespace(url="https://apic.example.test", verify_ssl=True, username="admin", password="test-password")
        self.namespace["load_apic_settings"].return_value = settings
        client_type = self.namespace["ACIClient"]
        for arguments, handler, expected in cases:
            with self.subTest(arguments=arguments):
                client = Mock(spec=client_type)
                constructor = Mock(return_value=client)
                with patch.dict(self.namespace, {"ACIClient": constructor}), patch("sys.argv", ["saci", *arguments]):
                    self.namespace["main"]()
                constructor.assert_called_once_with(settings.url, verify_ssl=True, username="admin", password="test-password")
                self.assertEqual(client.mock_calls, [call.login(), getattr(call, handler)(*expected)])

    def test_main_rejects_missing_apic_url_before_constructing_client(self):
        self.namespace["load_apic_settings"].return_value = SimpleNamespace(url="")
        constructor = Mock()
        with patch.dict(self.namespace, {"ACIClient": constructor}), self.assertRaises(SystemExit) as raised:
            self.namespace["main"]()
        self.assertEqual(raised.exception.code, 1)
        constructor.assert_not_called()
        self.namespace["logger"].error.assert_called_once()

    def test_main_rejects_vmm_vlan_without_domain(self):
        self.namespace["load_apic_settings"].return_value = SimpleNamespace(
            url="https://apic.example.test", verify_ssl=False, username="", password="",
        )
        client = Mock(spec=self.namespace["ACIClient"])
        with patch.dict(self.namespace, {"ACIClient": Mock(return_value=client)}), patch("sys.argv", ["saci", "vmm", "vlan"]):
            output = self.output(self.namespace["main"])
        self.assertIn("specify a VMM domain first", output)
        client.handle_vmm_vlan_command.assert_not_called()