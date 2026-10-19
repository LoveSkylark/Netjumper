"""Shared LibreNMS test fixtures without optional runtime dependencies."""

# pylint: disable=exec-used

import ast
import contextlib
import importlib
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))


def load_definitions(filename, namespace, import_roots=()):
    source_path = SCRIPTS / filename
    source = ast.parse(source_path.read_text(encoding="utf-8"))
    definitions = []
    for node in source.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.Assign, ast.AnnAssign)):
            definitions.append(node)
        elif isinstance(node, ast.Import):
            if all(alias.name.split(".")[0] in import_roots for alias in node.names):
                definitions.append(node)
        elif isinstance(node, ast.ImportFrom):
            if node.module.split(".")[0] in import_roots:
                definitions.append(node)
    namespace = {"__name__": "slnms_under_test", **namespace}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source_path), "exec"), namespace)
    return namespace


def load_client():
    return load_definitions("slnms_client.py", {"requests": SimpleNamespace(Session=Mock())})


def load_cli():
    parsers = importlib.import_module("scripts.slnms_parsers")
    namespace = load_client()
    namespace.update({name: getattr(parsers, name) for name in (
        "format_mbps", "format_bill_date", "find_unknown_neighbors", "get_sorted_port_list",
        "group_by_hardware_version", "save_firmware_files", "print_firmware_list", "get_vendor",
    )})
    namespace["CLITreeBuilder"] = importlib.import_module("scripts.tree_utils").CLITreeBuilder
    namespace.update({name: Mock() for name in (
        "Hosts", "HostsEntry", "load_settings", "list_librenms_servers", "set_librenms_active",
        "NetboxClient", "normalize_devices", "normalize_nb_devices", "match_site", "compile_mapping",
        "sites_from_mapping", "find_closest_id", "build_clean_lookup",
    )})
    namespace["DEVICE_ROLES"] = ["Network", "Servers"]
    return load_definitions("slnms.py", namespace, ("os", "re", "sys", "socket", "logging", "argparse", "ipaddress"))


def device(**attributes):
    return {
        "device_id": 1, "sysName": "Router1.example.test", "hostname": "192.0.2.1", "ip": "192.0.2.1",
        "hardware": "Model A", "version": "1.0", "serial": "SERIAL1", "icon": "images/os/cisco.svg",
        "status": 1, "type": "network", "location": "DC1", **attributes,
    }


class SlnmsTestCase(unittest.TestCase):
    def output(self, function, *args, **kwargs):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            function(*args, **kwargs)
        return stream.getvalue()


class SlnmsCommandTestCase(SlnmsTestCase):
    def setUp(self):
        self.namespace = load_cli()
        self.namespace["logging"] = Mock()
        self.namespace["socket"] = SimpleNamespace(gethostbyname=Mock(side_effect=OSError("DNS unavailable in tests")))
        self.api = Mock(spec=self.namespace["Client"])
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.settings = SimpleNamespace(
            info_dir=str(self.directory / "info"), config_dir=str(self.directory / "configs"),
            hosts_dir=str(self.directory / "hosts"), log_dir=str(self.directory / "logs"),
            url="https://nms.example.test", token="test-token", nb_url="https://nb.example.test",
            nb_token="test-nb-token", nb_regions=["Region"], nb_site_mapping={"DC1": {"name": "router*"}},
        )
        self.args = SimpleNamespace(
            settings=self.settings, customer=None, ports=False, vendor=None, hostname=None,
            tree=False, hardware=None, version=None,
        )

    def run_command(self, name):
        return self.output(self.namespace[name], self.args, self.api)