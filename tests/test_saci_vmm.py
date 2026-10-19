"""VMM domain maps and static/dynamic VLAN selection."""

# pylint: disable=protected-access

from unittest.mock import Mock

from saci_test_support import SaciTestCase, record


class VmmTests(SaciTestCase):
    def setUp(self):
        super().setUp()
        self.epg = "uni/tn-A/ap-App/epg-Web"
        self.domain = "uni/vmmp-VMware/dom-Production"
        self.attachment = f"{self.epg}/rsdomAtt-[{self.domain}]"

    def test_vlan_sort_is_numeric_and_places_non_vlan_values_last(self):
        self.assertEqual(
            sorted(["unknown", "vlan-100", "vlan-20", "vlan-3"], key=self.client._vlan_encap_sort_key),
            ["vlan-3", "vlan-20", "vlan-100", "unknown"],
        )

    def test_extract_vlan_encaps_only_reads_string_encap_fields(self):
        attributes = {
            "encap": "vlan-100", "primaryEncap": "vlan-20", "secondaryEncap": "vlan-30,vlan-40",
            "description": "vlan-999", "numericEncap": 5, "emptyEncap": None,
        }
        self.assertEqual(self.client._extract_vlan_encaps_from_attrs(attributes), {"vlan-100", "vlan-20", "vlan-30", "vlan-40"})
        self.assertEqual(self.client._extract_primary_vlan_encaps_from_attrs(attributes), {"vlan-20", "vlan-30", "vlan-40"})

    def test_member_vlan_map_deduplicates_and_ignores_unknown_encaps(self):
        self.data["fvCEp"] = [
            record("fvCEp", dn=f"{self.epg}/cep-{index}", encap=encap)
            for index, encap in enumerate(("vlan-100", "vlan-100", "unknown", "unspecified", ""))
        ] + [record("fvCEp", dn="invalid", encap="vlan-999")]
        self.assertEqual(self.client._build_epg_member_vlans_map(), {self.epg: {"vlan-100"}})

    def test_domdef_map_scopes_vlans_to_epg_and_vmm_domain(self):
        self.data["fvDomDef"] = [
            record("fvDomDef", dn=f"{self.epg}/rsdomDef-[{domain}]", encap=encap)
            for domain, encap in ((self.domain, "vlan-100"), (self.domain, "unknown"), ("uni/phys-LAN", "vlan-999"))
        ]
        self.assertEqual(self.client._build_epg_domain_domdef_vlans_map(), {(self.epg, self.domain): {"vlan-100"}})

    def test_deployed_vlan_map_extracts_epg_and_domain_from_dn(self):
        self.data["vmmEpPD"] = [
            record("vmmEpPD", dn=f"{self.domain}/eppd-[{self.epg}]", encap="vlan-200"),
            record("vmmEpPD", dn="invalid", encap="vlan-999"),
            record("vmmEpPD", dn=f"{self.domain}/eppd-[{self.epg}]", encap="unspecified"),
        ]
        self.assertEqual(self.client._build_vmm_deployed_epg_vlans_map(), {(self.epg, self.domain): {"vlan-200"}})

    def test_attachment_subtree_ignores_unknown_values_and_empty_dn(self):
        self.assertEqual(self.client._get_attachment_domdef_vlans(""), set())
        self.client.query_api.assert_not_called()
        endpoint = f"/api/mo/{self.attachment}.json?query-target=subtree&target-subtree-class=fvDomDef"
        self.data[endpoint] = [record("fvDomDef", encap=encap) for encap in ("vlan-30", "vlan-30", "unknown", "unspecified")]
        self.assertEqual(self.client._get_attachment_domdef_vlans(self.attachment), {"vlan-30"})

    def test_vlan_resolution_precedence_and_fallbacks(self):
        self.client._get_attachment_domdef_vlans = Mock(return_value=set())
        key = (self.epg, self.domain)
        cases = (
            ({"encap": "vlan-100"}, {"vlan-20"}, {"vlan-30"}, ("vlan-100", "static")),
            ({"primaryEncap": "vlan-100", "secondaryEncap": "vlan-20"}, set(), set(), ("vlan-20", "static")),
            ({"mode": "static"}, set(), {"vlan-30"}, ("vlan-30", "static")),
            ({}, {"vlan-20"}, {"vlan-30"}, ("vlan-30", "dynamic")),
            ({}, {"vlan-100", "vlan-20"}, set(), ("vlan-20", "dynamic")),
            ({"otherEncap": "vlan-40", "mode": "dynamic"}, set(), set(), ("vlan-40", "dynamic")),
            ({}, set(), set(), (None, None)),
        )
        for attributes, domdef, deployed, expected in cases:
            with self.subTest(attributes=attributes, expected=expected):
                self.assertEqual(self.client._resolve_vmm_attachment_vlan(
                    attributes, self.epg, self.domain, self.attachment, {key: domdef}, {key: deployed},
                ), expected)
        self.client._get_attachment_domdef_vlans.return_value = {"vlan-50"}
        self.assertEqual(self.client._resolve_vmm_attachment_vlan({}, self.epg, self.domain, self.attachment, {}, {}), ("vlan-50", "dynamic"))

    def test_vmm_command_groups_domains_by_provider(self):
        self.data["vmmDomP"] = [
            record("vmmDomP", dn=self.domain, name="Production"),
            record("vmmDomP", dn="uni/vmmp-Nutanix/dom-Test", name="Test"),
            record("vmmDomP", dn="invalid", name=""),
        ]
        output = self.output(self.client.handle_vmm_command)
        self.client.print_tree.assert_called_once_with({"VMM Domains": {"Nutanix": ["Test"], "VMware": ["Production"]}})
        self.assertIn("Total: 2 VMM domain(s)", output)

    def test_vmm_epg_command_filters_case_insensitively_and_marks_static_vlan(self):
        attachment = record("fvRsDomAtt", dn=self.attachment, tDn=self.domain, encap="vlan-100")
        self.data["fvRsDomAtt"] = [attachment, attachment, record("fvRsDomAtt", dn=self.attachment, tDn="uni/phys-LAN")]
        output = self.output(self.client.handle_vmm_epg_command, "vmware/production", "a")
        self.client.print_tree.assert_called_once_with({"VMM Domain EPG Associations": {
            "VMware": {"Production": {"A": ["App/Web (100[s])"]}},
        }})
        self.assertIn("Total: 1 associated EPG(s)", output)

    def test_vmm_vlan_command_sorts_deduplicates_and_filters_binding_type(self):
        dynamic_epg = "uni/tn-A/ap-App/epg-Dynamic"
        static = record("fvRsDomAtt", dn=self.attachment, tDn=self.domain, encap="vlan-100")
        self.data["fvRsDomAtt"] = [static, static, record("fvRsDomAtt", dn=f"{dynamic_epg}/rsdomAtt-[{self.domain}]", tDn=self.domain)]
        self.data["vmmEpPD"] = [record("vmmEpPD", dn=f"{self.domain}/eppd-[{dynamic_epg}]", encap="vlan-20")]
        output = self.output(self.client.handle_vmm_vlan_command, "all", "production", "A")
        self.assertIn("20 | A/App/Dynamic\n", output)
        self.assertIn("100 | A/App/Web[s]\n", output)
        self.assertLess(output.index("20 |"), output.index("100 |"))
        self.assertIn("Total: 2 VLAN(s), 2 mapping(s)", output)
        static_output = self.output(self.client.handle_vmm_vlan_command, "static", "production", "A")
        self.assertIn("100 | A/App/Web\n", static_output)
        self.assertNotIn("20 |", static_output)
        dynamic_output = self.output(self.client.handle_vmm_vlan_command, "dynamic", "production", "A")
        self.assertIn("20 | A/App/Dynamic\n", dynamic_output)
        self.assertNotIn("100 |", dynamic_output)

    def test_vmm_commands_report_no_matching_data(self):
        self.assertIn("No VMM domains found", self.output(self.client.handle_vmm_command))
        self.assertIn("No EPG to VMM domain associations", self.output(self.client.handle_vmm_epg_command, "missing"))
        for mode in ("all", "static", "dynamic"):
            with self.subTest(mode=mode):
                self.assertIn("No ", self.output(self.client.handle_vmm_vlan_command, mode))