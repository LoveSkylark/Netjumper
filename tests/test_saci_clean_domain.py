"""Exercise domain reporting without HTTP dependencies or APIC authentication."""

import ast
import contextlib
import io
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from saci_parsers import RE_EPG, parse_regex


def record(class_name, **attributes):
    return {class_name: {"attributes": attributes}}


class CleanDomainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ast.parse((SCRIPTS / "saci.py").read_text(encoding="utf-8"))
        client = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "ACIClient")
        handler = next(node for node in client.body if isinstance(node, ast.FunctionDef) and node.name == "handle_clean_domain")
        namespace = {"re": re, "RE_EPG": RE_EPG, "parse_regex": parse_regex}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), str(SCRIPTS / "saci.py"), "exec"), namespace)
        cls.handler = staticmethod(namespace["handle_clean_domain"])

    def setUp(self):
        self.domain = "uni/phys-SENS-s32-dc-core"
        self.aaep = "uni/infra/attentp-current"
        self.epg = "uni/tn-HRAH/ap-Services/epg-Servers"
        self.data = {
            "physDomP": [record("physDomP", dn=self.domain)],
            "infraAttEntityP": [record("infraAttEntityP", dn=self.aaep)],
            "infraRsDomP": [record("infraRsDomP", dn=f"{self.aaep}/rsdomP-[{self.domain}]", tDn=self.domain, state="formed")],
            "fabricNode": [record("fabricNode", dn="topology/pod-1/node-101", fabricSt="inactive")],
            "fvRsDomAtt": [record("fvRsDomAtt", dn=f"{self.epg}/rsdomAtt-[{self.domain}]", tDn=self.domain)],
        }

    def add_path(self, path, class_name="fvRsPathAtt"):
        relation = "rspathAtt" if class_name == "fvRsPathAtt" else "dyPathAtt"
        self.data.setdefault(class_name, []).append(record(class_name, dn=f"{self.epg}/{relation}-[{path}]", tDn=path))

    def report(self):
        client = SimpleNamespace(
            query_api=lambda endpoint: self.data.get(endpoint.rsplit("/", 1)[-1].removesuffix(".json"), []),
            print_tree=Mock(),
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.handler(client)
        return client.print_tree.call_args_list, output.getvalue()

    def test_orphaned_domain_is_reported_despite_other_domain_path(self):
        self.data["infraRsDomP"] = []
        self.add_path("topology/pod-1/paths-101/pathep-[eth1/1]")
        calls, _ = self.report()
        self.assertEqual(calls[0].args[0], {"Global": {"Physical Domains": ["SENS-s32-dc-core"]}})
        self.assertIn("no existing AAEP attachment", str(calls[1]))
        self.assertIn("EPG: Servers", str(calls[1]))

    def test_reference_under_deleted_aaep_is_not_usage(self):
        self.data["infraAttEntityP"] = []
        self.add_path("topology/pod-1/paths-101/pathep-[eth1/1]")
        calls, _ = self.report()
        self.assertEqual(len(calls), 2)
        self.assertIn("no existing AAEP attachment", str(calls[1]))

    def test_unformed_reference_is_not_usage(self):
        self.data["infraRsDomP"][0]["infraRsDomP"]["attributes"]["state"] = "unformed"
        calls, _ = self.report()
        self.assertIn("no existing AAEP attachment", str(calls[1]))

    def test_paths_in_removed_pod_do_not_hide_attachment(self):
        for class_name in ("fvRsPathAtt", "fvDyPathAtt"):
            with self.subTest(class_name=class_name):
                self.add_path("topology/pod-2/paths-101/pathep-[eth1/1]", class_name)
                calls, _ = self.report()
                self.assertEqual(len(calls), 1)
                self.assertIn("no path to an existing fabric node", str(calls[0]))

    def test_existing_offline_node_preserves_static_and_dynamic_paths(self):
        for class_name in ("fvRsPathAtt", "fvDyPathAtt"):
            with self.subTest(class_name=class_name):
                self.add_path("topology/pod-1/paths-101/pathep-[eth1/1]", class_name)
                calls, _ = self.report()
                self.assertEqual(calls, [])

    def test_vpc_with_one_remaining_node_is_preserved(self):
        self.add_path("topology/pod-1/protpaths-101-102/pathep-[bundle]")
        calls, _ = self.report()
        self.assertEqual(calls, [])

    def test_missing_inventory_does_not_mark_all_paths_stale(self):
        self.data["fabricNode"] = []
        self.add_path("topology/pod-2/paths-101/pathep-[eth1/1]")
        calls, output = self.report()
        self.assertEqual(calls, [])
        self.assertIn("missing-node path checks skipped", output)

    def test_vmm_attachment_is_not_reported_as_physical(self):
        self.data["fvRsDomAtt"] = [record("fvRsDomAtt", dn=f"{self.epg}/rsdomAtt-[uni/vmmp-VMware/dom-virtual]", tDn="uni/vmmp-VMware/dom-virtual")]
        calls, _ = self.report()
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()