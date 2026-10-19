"""User-facing command reports with mocked APIC inventories."""

from ipaddress import ip_network
from unittest.mock import Mock, call

from saci_test_support import SaciTestCase, record


class CommandTests(SaciTestCase):
    def setUp(self):
        super().setUp()
        self.epg = "uni/tn-A/ap-App/epg-Web"
        self.path = "topology/pod-1/paths-101/pathep-[eth1/1]"
        self.vpc = "topology/pod-1/protpaths-101-102/pathep-[Bundle]"
        self.data["topSystem"] = [record("topSystem", id="101", podId="1", name="leaf1")]
        self.data["fabricNode"] = [record("fabricNode", id="101", name="leaf1", fabricSt="active")]

    def add_bindings(self, path):
        self.data["fvRsPathAtt"] = [record("fvRsPathAtt", dn=f"{self.epg}/rspathAtt-[{path}]", tDn=path, encap="vlan-100")]
        self.data["l3extRsPathL3OutAtt"] = [record(
            "l3extRsPathL3OutAtt", dn=f"uni/tn-A/out-WAN/lnodep-Nodes/lifp-Uplink/rspathL3OutAtt-[{path}]", tDn=path, encap="vlan-200",
        )]

    def test_port_command_combines_l2_and_l3_bindings(self):
        self.add_bindings(self.path)
        output = self.output(self.client.handle_port_command, "1/1", node_name="leaf1")
        self.assertIn("eth1/1 on leaf1 [101]", output)
        self.client.print_tree.assert_called_once_with({"A": {
            "EPG: App": {"_leaf": ["Web (vlan-100)"]},
            "L3: WAN": {"_leaf": ["Uplink (vlan-200)"]},
        }})

    def test_port_command_does_not_match_neighboring_port(self):
        self.add_bindings(self.path)
        self.assertIn("No bindings found", self.output(self.client.handle_port_command, "1/10", "101"))
        self.client.print_tree.assert_not_called()

    def test_port_command_exits_when_node_is_unknown(self):
        with self.assertRaises(SystemExit) as raised:
            self.output(self.client.handle_port_command, "1/1", "999")
        self.assertEqual(raised.exception.code, 1)

    def test_vpc_command_lists_interfaces_and_builds_binding_tree(self):
        self.add_bindings(self.vpc)
        self.assertIn("  Bundle\n", self.output(self.client.handle_vpc_command, "101-102"))
        self.output(self.client.handle_vpc_command, "101-102", "Bundle")
        self.client.print_tree.assert_called_once_with({"A": {
            "EPG: App": {"_leaf": ["Web (vlan-100)"]},
            "L3: WAN": {"_leaf": ["Uplink (vlan-200)"]},
        }})

    def test_vpc_vlan_table_includes_l2_and_l3_and_sorts_vlans(self):
        self.add_bindings(self.vpc)
        output = self.output(self.client.handle_vpc_command, "101-102", "Bundle", "vlan")
        self.assertIn("100 | A/App/Web [EPG]", output)
        self.assertIn("200 | A/WAN/Uplink [L3]", output)
        self.assertLess(output.index("100 |"), output.index("200 |"))
        self.assertIn("Total: 2 VLAN(s), 2 mapping(s)", output)

    def test_vpc_command_rejects_invalid_nodes_or_missing_interface(self):
        for nodes in ("invalid", "101", "101-102-103"):
            with self.subTest(nodes=nodes), self.assertRaises(SystemExit):
                self.output(self.client.handle_vpc_command, nodes)
        self.assertIn("specify a VPC interface", self.output(self.client.handle_vpc_command, "101-102", "vlan"))

    def test_tenant_command_scopes_bindings_to_exact_tenant(self):
        self.add_bindings(self.path)
        self.data["fvRsPathAtt"].append(record("fvRsPathAtt", dn=f"{self.epg.replace('tn-A/', 'tn-AB/')}/rspathAtt-[{self.path}]", tDn=self.path, encap="vlan-999"))
        self.output(self.client.handle_tenant_command, "A")
        self.assertEqual(self.client.print_tree.call_args_list, [
            call({"Pod-1": {"leaf1 [101]": {"eth1/1": {"App": {"_leaf": ["Web (vlan-100)"]}}}}}),
            call({"Pod-1": {"leaf1 [101]": {"eth1/1": {"WAN": {"_leaf": ["Uplink (vlan-200)"]}}}}}),
        ])

    def test_vlan_pool_lookup_includes_range_boundaries_and_skips_malformed_blocks(self):
        pool_dn = "uni/infra/vlanns-[Pool]-static"
        pools = [record("fvnsVlanInstP", dn=pool_dn, name="Pool")]
        endpoint = f"/api/mo/{pool_dn}.json?query-target=children&target-subtree-class=fvnsEncapBlk"
        self.data[endpoint] = [
            record("fvnsEncapBlk", dn=f"{pool_dn}/from-[vlan-100]-to-[vlan-200]", **{"from": "vlan-100", "to": "vlan-200"}),
            record("fvnsEncapBlk", dn="bad", **{"from": "invalid", "to": "vlan-300"}),
            record("fvnsEncapBlk", dn="missing-fields"),
        ]
        for vlan, expected_count in ((99, 0), (100, 1), (150, 1), (200, 1), (201, 0)):
            with self.subTest(vlan=vlan):
                results = self.client.find_vlan_in_vlan_pools(pools, vlan)
                self.assertEqual(len(results), expected_count)
                if results:
                    self.assertEqual((results[0].pool_name, results[0].from_vlan, results[0].to_vlan), ("Pool", 100, 200))

    def test_vlan_command_queries_exact_encap_and_deduplicates_dynamic_members(self):
        self.add_bindings(self.path)
        self.data["l3extRsPathL3OutAtt"][0]["l3extRsPathL3OutAtt"]["attributes"]["encap"] = "vlan-100"
        self.data["fvCEp"] = [record("fvCEp", dn=f"{self.epg}/cep-AA:BB:CC:DD:EE:FF", encap="vlan-100")]
        self.output(self.client.handle_vlan_command, 100)
        self.client.print_tree.assert_called_once_with({"A": {
            "EPG: App": {"_leaf": ["Web (vlan-100)"]},
            "L3: WAN": {"_leaf": ["Uplink (vlan-100)"]},
        }})
        self.client.query_api.assert_any_call("/api/node/class/fvRsPathAtt.json", 'eq(fvRsPathAtt.encap,"vlan-100")')
        self.client.query_api.assert_any_call("/api/class/fvCEp.json", 'eq(fvCEp.encap,"vlan-100")')

    def test_epg_command_shows_prefix_matches_and_ambiguous_exact_names(self):
        self.data["fvAEPg"] = [record("fvAEPg", dn=f"uni/tn-{tenant}/ap-App/epg-Web", name="Web") for tenant in ("A", "B")]
        self.assertIn("Possible matches", self.output(self.client.handle_epg_command, "We"))
        self.assertIn("multiple tenants", self.output(self.client.handle_epg_command, "Web"))
        self.assertEqual(self.client.print_tree.call_args.args[0], {"A": {"App": ["Web"]}, "B": {"App": ["Web"]}})

    def test_epg_command_reports_bd_vrf_contracts_bindings_and_endpoints(self):
        self.add_bindings(self.path)
        self.data["fvAEPg"] = [record("fvAEPg", dn=self.epg, name="Web")]
        self.data["fvRsBd"] = [record("fvRsBd", dn=f"{self.epg}/rsbd", tnFvBDName="LAN")]
        self.data["fvRsCtx"] = [record("fvRsCtx", dn="uni/tn-A/BD-LAN/rsctx", tnFvCtxName="VRF")]
        self.data["fvRsProv"] = [record("fvRsProv", dn=f"{self.epg}/rsprov-HTTP", tnVzBrCPName="HTTP")]
        endpoint_dn = f"{self.epg}/cep-AA:BB:CC:DD:EE:FF"
        self.data["fvCEp"] = [record("fvCEp", dn=endpoint_dn, mac="AA:BB:CC:DD:EE:FF", encap="vlan-100")]
        self.data["fvIp"] = [record("fvIp", dn=f"{endpoint_dn}/ip-[10.1.1.9]", addr="10.1.1.9")]
        output = self.output(self.client.handle_epg_command, "Web", "A")
        self.assertIn("BD:  LAN", output)
        self.assertIn("VRF: VRF", output)
        self.assertEqual(self.client.print_tree.call_args.args[0], {
            "Contracts": {"Provided": ["HTTP"]},
            "Static Bindings": {"Pod-1": {"leaf1 [101]": ["eth1/1  (vlan-100)"]}},
            "Endpoints (1)": ["AA:BB:CC:DD:EE:FF  10.1.1.9  (vlan-100)"],
        })

    def test_contract_command_groups_providers_consumers_and_exports(self):
        contract_dn = "uni/tn-A/brc-HTTP"
        self.data["vzBrCP"] = [record("vzBrCP", dn=contract_dn, name="HTTP", scope="global")]
        self.data["fvRsProv"] = [record("fvRsProv", dn=f"{self.epg}/rsprov-HTTP", tDn=contract_dn)]
        self.data["fvRsCons"] = [record("fvRsCons", dn="uni/tn-B/ap-App/epg-Client/rscons-HTTP", tDn=contract_dn)]
        self.data[f"/api/mo/{contract_dn}.json?query-target=subtree&target-subtree-class=vzRtIf"] = [record("vzRtIf", tDn="uni/tn-B/cif-Imported")]
        self.output(self.client.handle_contract_command, "HTTP")
        self.assertEqual(self.client.print_tree.call_args_list, [
            call({"Providers": {"A": ["EPG: App/Web"]}}),
            call({"Consumers": {"B": ["EPG: App/Client"]}}),
            call({"Exported to:": {"Imported": ["B"]}}),
        ])

    def test_contract_filters_only_dispatches_to_all_owning_tenants(self):
        self.data["vzBrCP"] = [record("vzBrCP", dn=f"uni/tn-{tenant}/brc-HTTP", name="HTTP") for tenant in ("B", "A", "A")]
        self.client.handle_filter_command = Mock()
        self.client.handle_contract_command("HTTP", filters_only=True)
        self.assertEqual(self.client.handle_filter_command.call_args_list, [call("HTTP", "A"), call("HTTP", "B")])

    def test_filter_command_compacts_ports_and_normalizes_unspecified(self):
        self.data["vzBrCP"] = [record("vzBrCP", dn="uni/tn-A/brc-HTTP", name="HTTP")]
        self.data["vzSubj"] = [record("vzSubj", dn="uni/tn-A/brc-HTTP/subj-Allow")]
        self.data["vzRsSubjFiltAtt"] = [record("vzRsSubjFiltAtt", dn="uni/tn-A/brc-HTTP/subj-Allow/rssubjFiltAtt-Web", tDn="uni/tn-A/flt-Web")]
        self.data["vzFilter"] = [record("vzFilter", dn="uni/tn-A/flt-Web", name="Web")]
        self.data["vzEntry"] = [
            record("vzEntry", dn="uni/tn-A/flt-Web/e-HTTPS", prot="tcp", sFromPort="unspecified", sToPort="unspecified", dFromPort="443", dToPort="443"),
            record("vzEntry", dn="uni/tn-A/flt-Web/e-Range", prot="udp", sFromPort="10", sToPort="20", dFromPort="30", dToPort="40"),
        ]
        self.output(self.client.handle_filter_command, "HTTP", "A")
        self.client.print_tree.assert_called_once_with({"HTTP": {"Filter Details": {"Web": ["tcp dst:443", "udp src:10-20 dst:30-40"]}}})

    def test_aaep_dispatches_list_or_detail_and_endpoint_filter(self):
        self.client.handle_aaep_list_command = Mock()
        self.client.handle_aaep_detail_command = Mock()
        self.client.handle_aaep_command()
        self.client.handle_aaep_command("Servers", "A/App/Web")
        self.client.handle_aaep_list_command.assert_called_once_with()
        self.client.handle_aaep_detail_command.assert_called_once_with("Servers", "A/App/Web")

    def test_aaep_list_is_sorted(self):
        self.data["infraAttEntityP"] = [record("infraAttEntityP", name=name) for name in ("Zebra", "Servers")]
        self.assertIn("Total: 2 AAEP(s)", self.output(self.client.handle_aaep_list_command))
        self.client.print_tree.assert_called_once_with({"AAEPs": ["Servers", "Zebra"]})

    def test_aaep_detail_reports_domain_vlan_pool_and_policy_group(self):
        aaep_dn = "uni/infra/attentp-Servers"
        self.data["infraAttEntityP"] = [record("infraAttEntityP", name="Servers", dn=aaep_dn)]
        self.data["infraRsDomP"] = [record("infraRsDomP", dn=f"{aaep_dn}/rsdomP-[uni/phys-LAN]", tDn="uni/phys-LAN")]
        self.data["infraRsVlanNs"] = [record("infraRsVlanNs", dn="uni/phys-LAN/rsvlanNs", tDn="uni/infra/vlanns-[Pool]-static")]
        self.data["infraRsAttEntP"] = [record("infraRsAttEntP", dn="uni/infra/funcprof/accportgrp-Access/rsattEntP", tDn=aaep_dn)]
        self.output(self.client.handle_aaep_detail_command, "Servers")
        self.assertEqual(self.client.print_tree.call_args.args[0], {
            "Domains": {"Physical: LAN": {"VLAN Pools": ["Pool"]}},
            "Interface Policy Groups": {"Access Port": ["Access"]},
        })

    def test_missing_objects_report_no_results(self):
        cases = (
            (self.client.handle_epg_command, ("missing",), "not found"),
            (self.client.handle_contract_command, ("missing",), "not found"),
            (self.client.handle_filter_command, ("missing", "A"), "not found"),
            (self.client.handle_aaep_detail_command, ("missing",), "not found"),
            (self.client.handle_aaep_list_command, (), "No AAEPs found"),
            (self.client.handle_vlan_command, (100,), "not found in any VLAN pools"),
        )
        for handler, args, message in cases:
            with self.subTest(handler=handler.__name__):
                self.assertIn(message, self.output(handler, *args))


class RouteCommandTests(SaciTestCase):
    def setUp(self):
        super().setUp()
        self.data["fvCtx"] = [record("fvCtx", dn="uni/tn-A/ctx-VRF")]
        self.client.get_tep_pool = Mock(return_value=ip_network("10.255.0.0/16"))

    def add_route(self, prefix, owner="bgp", via="192.0.2.1", node="101", nh_vrf="A:VRF"):
        route_dn = f"topology/pod-1/node-{node}/sys/uribv4/dom-A:VRF/db-rt/rt-[{prefix}]"
        self.data.setdefault("uribv4Route", []).append(record("uribv4Route", dn=route_dn, prefix=prefix))
        self.data.setdefault("uribv4Nexthop", []).append(record(
            "uribv4Nexthop", dn=f"{route_dn}/nh-[{owner}]-[{via}/32]-[eth1/1]-[{nh_vrf}]", owner=owner, addr=f"{via}/32",
        ))

    def test_routes_consolidate_leafs_and_sort_prefixes(self):
        self.add_route("10.2.0.0/24")
        self.add_route("10.1.0.0/24", node="102")
        self.add_route("10.1.0.0/24", node="101")
        output = self.output(self.client.handle_route_command, "A:VRF")
        self.assertLess(output.index("10.1.0.0/24"), output.index("10.2.0.0/24"))
        self.assertIn("101, 102", output)
        self.assertIn("Total: 2 prefix(es) across 2 leaf(s)", output)

    def test_routes_hide_direct_and_tep_routes_unless_detailed(self):
        self.add_route("10.1.0.0/24", owner="direct", via="0.0.0.0")
        self.add_route("10.255.1.0/24", nh_vrf="overlay-1")
        output = self.output(self.client.handle_route_command, "A:VRF")
        self.assertNotIn("10.1.0.0/24", output)
        self.assertNotIn("10.255.1.0/24", output)
        detailed = self.output(self.client.handle_route_command, "A:VRF", detail=True)
        self.assertIn("10.1.0.0/24", detailed)
        self.assertIn("10.255.1.0/24", detailed)

    def test_route_scope_filters_native_leaked_and_infrastructure_routes(self):
        self.add_route("10.1.0.0/24")
        self.add_route("10.2.0.0/24", nh_vrf="overlay-1")
        self.add_route("10.255.1.0/24", nh_vrf="overlay-1")
        local = self.output(self.client.handle_route_command, "A:VRF", local_only=True)
        self.assertIn("10.1.0.0/24", local)
        self.assertNotIn("10.2.0.0/24", local)
        external = self.output(self.client.handle_route_command, "A:VRF", external_only=True)
        self.assertIn("10.2.0.0/24", external)
        self.assertNotIn("10.1.0.0/24", external)
        self.assertNotIn("10.255.1.0/24", external)

    def test_route_cidr_string_and_mask_filters(self):
        self.add_route("10.1.0.0/24")
        self.add_route("10.2.0.0/24")
        self.add_route("10.1.0.9/32")
        for route_filter in ("10.1.0.0/16", "10.1"):
            with self.subTest(route_filter=route_filter):
                output = self.output(self.client.handle_route_command, "A:VRF", route_filter=route_filter, prefix_filter="/24")
                self.assertIn("10.1.0.0/24", output)
                self.assertNotIn("10.2.0.0/24", output)
                self.assertNotIn("10.1.0.9/32", output)

    def test_route_validation_handles_bad_vrf_and_filters(self):
        self.assertIn("specify VRF", self.output(self.client.handle_route_command, "invalid"))
        self.assertIn("not found", self.output(self.client.handle_route_command, "A:missing"))
        self.assertIn("No routes found", self.output(self.client.handle_route_command, "A:VRF"))
        self.add_route("10.1.0.0/24")
        self.assertIn("Invalid CIDR filter", self.output(self.client.handle_route_command, "A:VRF", route_filter="bad/24"))
        self.assertIn("Invalid prefix filter", self.output(self.client.handle_route_command, "A:VRF", prefix_filter="bad"))