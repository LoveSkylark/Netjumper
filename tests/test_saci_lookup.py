"""IP, subnet, endpoint, and tree-building behavior."""

from unittest.mock import Mock, patch

from saci_test_support import SaciTestCase, record


class LookupTests(SaciTestCase):
    def test_ip_in_cidr_handles_host_bits_ipv6_and_invalid_input(self):
        for address, network, expected in (
            ("10.1.1.9", "10.1.1.1/24", True),
            ("10.1.2.9", "10.1.1.0/24", False),
            ("2001:db8::1", "2001:db8::/64", True),
            ("10.1.1.9", "2001:db8::/64", False),
            ("bad", "10.1.1.0/24", False),
            ("10.1.1.9", "bad", False),
        ):
            with self.subTest(address=address, network=network):
                self.assertEqual(self.client.ip_in_cidr(address, network), expected)

    def test_process_endpoint_reports_location_and_respects_tenant(self):
        records = [record(
            "fvIp", addr="10.1.1.9", dn="uni/tn-A/ap-App/epg-Web/cep-AA:BB:CC:DD:EE:FF/ip-[10.1.1.9]",
            fabricPathDn="topology/pod-2/paths-101/pathep-[eth1/1]",
        )]
        output = self.output(self.client.process_endpoint, records, "A")
        self.assertIn("Pod-2, Node-101", output)
        self.assertIn("AA:BB:CC:DD:EE:FF", output)
        self.assertIn("eth1/1", output)
        self.assertFalse(self.client.process_endpoint(records, "B"))
        self.assertFalse(self.client.process_endpoint([{}]))

    def test_process_subnet_groups_bd_and_epg_and_deduplicates(self):
        records = [
            record("fvSubnet", dn="uni/tn-A/BD-LAN/subnet-[10.1.1.1/24]", ip="10.1.1.1/24"),
            record("fvSubnet", dn="uni/tn-A/ap-App/epg-Web/subnet-[10.1.1.1/24]", ip="10.1.1.1/24"),
            record("fvSubnet", dn="uni/tn-B/BD-LAN/subnet-[10.1.1.1/24]", ip="10.1.1.1/24"),
            record("fvSubnet", dn="uni/tn-A/BD-Default/subnet-[0.0.0.0/0]", ip="0.0.0.0/0"),
        ]
        self.client.process_subnet(records + records, "10.1.1.9", prefix_filter="/24", tenant_filter="A")
        self.assertEqual(self.client.print_tree.call_args.args[0], {
            "A": {"BD:": {"_leaf": ["LAN - 10.1.1.1/24"]}, "AP:": {"App": {"_leaf": ["Web - 10.1.1.1/24"]}}},
        })
        self.client.print_tree.reset_mock()
        self.client.process_subnet(records, "10.1", prefix_mode=True, prefix_filter="/32")
        self.client.print_tree.assert_not_called()

    def test_process_external_subnet_filters_prefix_and_tenant(self):
        records = [record(
            "l3extSubnet", dn=f"uni/tn-{tenant}/out-WAN/instP-Internet/extsubnet-[10.1.0.0/24]", ip="10.1.0.0/24",
        ) for tenant in ("A", "B")]
        self.client.process_external_subnet(records + records, "10.1", prefix_mode=True, prefix_filter="/24", tenant_filter="A")
        self.assertEqual(self.client.print_tree.call_args.args[0], {
            "A": {"L3Out: WAN": {"_leaf": ["Internet - 10.1.0.0/24"]}},
        })

    def test_process_peer_reports_l3_interface_and_bgp_peer(self):
        for kind, attributes, expected in (
            ("l3extIp", {"dn": "uni/tn-A/out-WAN/lnodep-Nodes/lifp-Uplink/ip-[10.1.1.1/30]", "addr": "10.1.1.1/30"},
             {"A": {"L3Out: WAN": {"_leaf": ["Uplink - 10.1.1.1/30"]}}}),
            ("bgpPeer", {"dn": "topology/pod-1/node-101/sys/bgp/inst/dom-A:VRF/peer-[10.1.1.1]", "id": "10.1.1.1"},
             {"A": {"BGP Peers:": {"_leaf": ["Peer IP: 10.1.1.1"]}}}),
        ):
            with self.subTest(kind=kind):
                self.client.print_tree.reset_mock()
                records = [record(kind, **attributes)]
                self.assertTrue(self.client.process_peer(records, "10.1.1.1", kind, "A"))
                self.assertEqual(self.client.print_tree.call_args.args[0], expected)
                self.assertFalse(self.client.process_peer(records, "10.1.1.1", kind, "B"))

    def test_process_static_route_ignores_default_and_nonmatching_prefixes(self):
        records = [record("ipRouteP", dn="uni/tn-A/out-WAN/instP-External", ip=prefix)
                   for prefix in ("0.0.0.0/0", "10.2.0.0/24", "invalid")]
        self.assertFalse(self.client.process_static_route(records, "10.1.1.9"))
        self.client.print_tree.assert_not_called()

    def test_tree_add_creates_nested_labels_without_duplicate_leaves(self):
        tree = {}
        for _ in range(2):
            self.client.tree_add(tree, "Tenant", "App", label="Web/Servers")
        self.assertEqual(tree, {"Tenant": {"App": {"Web": {"_leaf": ["Servers"]}}}})
        with self.assertRaises(ValueError):
            self.client.tree_add(tree, label="missing levels")

    def test_epg_tenant_and_label_support_epg_l3out_and_fallback(self):
        for dn, tenant, label in (
            ("uni/tn-A/ap-App/epg-Web", "A", "EPG: App/Web"),
            ("uni/tn-B/out-WAN/instP-External", "B", "L3: WAN/External"),
            ("invalid", "unknown", "invalid"),
            ("uni/tn-A/rsprov-Contract", "A", "Contract"),
        ):
            with self.subTest(dn=dn):
                self.assertEqual(self.client.epg_tenant(dn), tenant)
                self.assertEqual(self.client.epg_label(dn), label)

    def test_collect_epgs_sorts_deduplicates_and_marks_imported_contracts(self):
        self.client.contract_dn_map = {
            "uni/tn-A/brc-Local": {"scope": "local"},
            "uni/tn-A/cif-Imported": {"scope": "imported"},
        }
        records = [
            record("fvRsCons", dn="uni/tn-A/ap-App/epg-Web/rscons-Local", tDn="uni/tn-A/brc-Local"),
            record("fvRsCons", dn="uni/tn-A/ap-App/epg-API/rscons-Imported", tDn="uni/tn-A/cif-Imported"),
            record("fvRsCons", dn="uni/tn-A/ap-App/epg-Other/rscons-Other", tDn="uni/tn-A/brc-Other"),
        ]
        self.assertEqual(self.client.collect_epgs(records + records, "fvRsCons"), {
            "A": [("EPG: App/API", True), ("EPG: App/Web", False)],
        })

    def test_list_all_subnets_combines_tenant_cidr_and_mask_filters(self):
        self.data["fvSubnet"] = [
            record("fvSubnet", dn=f"uni/tn-{tenant}/BD-LAN/subnet-[{prefix}]", ip=prefix)
            for tenant, prefix in (("A", "10.1.1.1/24"), ("B", "10.1.1.1/24"), ("A", "10.2.1.1/24"), ("A", "10.1.0.1/16"))
        ]
        self.data["l3extSubnet"] = [record("l3extSubnet", dn="uni/tn-A/out-WAN/instP-External/extsubnet-[10.1.2.0/24]", ip="10.1.2.0/24")]
        self.output(self.client.list_all_subnets, "A", "/24", "10.1.0.0/16")
        self.assertEqual(self.client.print_tree.call_args.args[0], {
            "A": {"BD Subnets:": ["LAN - 10.1.1.1/24"], "L3Out Subnets:": ["WAN - 10.1.2.0/24"]},
        })
        self.client.print_tree.reset_mock()
        self.assertIn("Invalid CIDR", self.output(self.client.list_all_subnets, ip_filter="bad/24"))
        self.client.print_tree.assert_not_called()

    def test_search_routes_filters_tenant_mask_and_deduplicates_leafs(self):
        self.data["uribv4Route"] = [
            record("uribv4Route", dn=f"topology/pod-1/node-{node}/sys/uribv4/dom-{tenant}:VRF/db-rt/rt-[{prefix}]", prefix=prefix)
            for node, tenant, prefix in (("101", "A", "10.1.1.0/24"), ("102", "A", "10.1.1.0/24"), ("101", "B", "10.1.1.0/24"), ("101", "A", "10.1.1.9/32"))
        ]
        self.client.search_routes_for_ip("10.1.1.9", "/24", "A")
        self.assertEqual(self.client.print_tree.call_args.args[0], {"A": {"VRF: VRF": {"_leaf": ["10.1.1.0/24"]}}})
        self.client.print_tree.reset_mock()
        self.client.search_routes_for_ip("10.1", "/24", "A")
        self.assertEqual(self.client.print_tree.call_args.args[0], {"A": {"VRF: VRF": {"_leaf": ["10.1.1.0/24"]}}})

    def test_search_routes_rejects_invalid_mask_before_query(self):
        self.assertIn("Invalid prefix filter", self.output(self.client.search_routes_for_ip, "10.1", "bad"))
        self.client.query_api.assert_not_called()

    def test_ip_command_falls_back_only_when_no_endpoint_peer_or_static_match(self):
        for found in (True, False):
            with self.subTest(found=found):
                self.client.process_endpoint = Mock(return_value=found)
                self.client.process_peer = Mock(return_value=False)
                self.client.process_static_route = Mock(return_value=False)
                self.client.process_subnet = Mock()
                self.client.process_external_subnet = Mock()
                self.client.search_routes_for_ip = Mock()
                self.output(self.client.handle_ip_command, "10.1.1.9", "/24", "A")
                self.assertEqual(self.client.process_subnet.call_count, int(not found))
                self.assertEqual(self.client.process_external_subnet.call_count, int(not found))
                self.client.search_routes_for_ip.assert_called_once_with("10.1.1.9", "/24", "A")
        self.client.query_api.assert_any_call("/api/node/class/fvIp.json", 'eq(fvIp.addr,"10.1.1.9")')

    def test_ip_prefix_command_always_searches_subnets_and_routes(self):
        for name in ("process_endpoint", "process_subnet", "process_external_subnet", "search_routes_for_ip"):
            setattr(self.client, name, Mock())
        self.output(self.client.handle_ip_command, "10.1", "/24", "A")
        self.client.process_subnet.assert_called_once_with([], "10.1", prefix_mode=True, prefix_filter="/24", tenant_filter="A")
        self.client.search_routes_for_ip.assert_called_once_with("10.1", "/24", "A")

    def test_subnet_command_forwards_filters(self):
        self.client.list_all_subnets = Mock()
        self.client.handle_subnet_command("A", "/24", "10.1")
        self.client.list_all_subnets.assert_called_once_with("A", "/24", "10.1")

    def test_print_tree_delegates_to_shared_renderer(self):
        tree = {"A": ["Web"]}
        with patch.object(self.namespace["CLITreeBuilder"], "print_tree") as renderer:
            self.namespace["ACIClient"].print_tree(tree, "Heading")
        renderer.assert_called_once_with(tree, "Heading")