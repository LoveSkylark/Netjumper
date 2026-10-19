"""Cleanup reports use mocked APIC records, not a live fabric."""

from unittest.mock import Mock

from saci_test_support import SaciTestCase, record


class CleanTests(SaciTestCase):
    def test_clean_vrf_keeps_references_scoped_to_tenant(self):
        self.data["fvCtx"] = [
            record("fvCtx", dn="uni/tn-A/ctx-shared"),
            record("fvCtx", dn="uni/tn-B/ctx-shared"),
        ]
        self.data["fvRsCtx"] = [
            record("fvRsCtx", dn="uni/tn-A/BD-used/rsctx", tnFvCtxName="shared"),
        ]
        self.output(self.client.handle_clean_vrf)
        self.client.print_tree.assert_called_once_with({"B": {"vrfs": ["shared"]}})

    def test_clean_bd_reports_only_unattached_domains(self):
        self.data["fvBD"] = [
            record("fvBD", dn="uni/tn-A/BD-used"),
            record("fvBD", dn="uni/tn-A/BD-unused"),
        ]
        self.data["fvRsBd"] = [
            record("fvRsBd", dn="uni/tn-A/ap-App/epg-Web/rsbd", tnFvBDName="used"),
        ]
        self.output(self.client.handle_clean_bd)
        self.client.print_tree.assert_called_once_with({"A": ["unused"]})

    def test_clean_bd_does_not_hide_same_name_in_other_tenant(self):
        self.data["fvBD"] = [
            record("fvBD", dn="uni/tn-A/BD-shared"),
            record("fvBD", dn="uni/tn-B/BD-shared"),
        ]
        self.data["fvRsBd"] = [
            record("fvRsBd", dn="uni/tn-A/ap-App/epg-Web/rsbd", tnFvBDName="shared"),
        ]
        self.output(self.client.handle_clean_bd)
        self.client.print_tree.assert_called_once_with({"B": ["shared"]})

    def test_clean_bd_uses_target_tenant_for_shared_bd_reference(self):
        self.data["fvBD"] = [
            record("fvBD", dn="uni/tn-A/BD-shared"),
            record("fvBD", dn="uni/tn-common/BD-shared"),
        ]
        self.data["fvRsBd"] = [record(
            "fvRsBd", dn="uni/tn-A/ap-App/epg-Web/rsbd",
            tnFvBDName="shared", tDn="uni/tn-common/BD-shared",
        )]
        self.output(self.client.handle_clean_bd)
        self.client.print_tree.assert_called_once_with({"A": ["shared"]})

    def test_clean_bd_gateway_respects_tenant_and_routing_flag(self):
        self.data["fvBD"] = [
            record("fvBD", dn="uni/tn-A/BD-broken", unicastRoute="no"),
            record("fvBD", dn="uni/tn-A/BD-working", unicastRoute="yes"),
            record("fvBD", dn="uni/tn-B/BD-broken", unicastRoute="no"),
        ]
        self.data["fvSubnet"] = [
            record("fvSubnet", dn=f"uni/tn-{tenant}/BD-{bd}/subnet-[10.1.1.1/24]", ip="10.1.1.1/24")
            for tenant, bd in (("A", "broken"), ("A", "working"), ("B", "broken"))
        ]
        self.output(self.client.handle_clean_bd_gw, "A")
        self.assertEqual(self.client.print_tree.call_args.args[0], {"A": {"broken": ["10.1.1.1/24"]}})

    def test_gateway_conflict_ignores_no_default_gateway_subnets(self):
        self.data["fvSubnet"] = [
            record("fvSubnet", dn="uni/tn-A/BD-LAN/subnet-[10.1.1.1/24]", ip="10.1.1.1/24"),
            record("fvSubnet", dn="uni/tn-A/ap-App/epg-Web/subnet-[10.1.1.1/24]", ip="10.1.1.1/24"),
            record("fvSubnet", dn="uni/tn-A/ap-App/epg-Safe/subnet-[10.1.1.1/24]", ip="10.1.1.1/24", ctrl="no-default-gateway"),
        ]
        self.data["fvRsBd"] = [
            record("fvRsBd", dn=f"uni/tn-A/ap-App/epg-{epg}/rsbd", tnFvBDName="LAN")
            for epg in ("Web", "Safe")
        ]
        self.output(self.client.handle_clean_bd_epg_gw)
        self.assertEqual(self.client.print_tree.call_args.args[0], {
            "A": {"BD: LAN": {"EPG: App/Web": ["10.1.1.1/24"]}},
        })

    def test_clean_epg_recognizes_each_usage_type(self):
        for class_name in ("fvRsProv", "fvRsCons", "fvMac", "fvIp", "fvRsPathAtt"):
            with self.subTest(class_name=class_name):
                self.data = {
                    "fvAEPg": [record("fvAEPg", dn=f"uni/tn-A/ap-App/epg-{name}") for name in ("Used", "Empty")],
                    class_name: [record(class_name, dn="uni/tn-A/ap-App/epg-Used/reference")],
                }
                self.client.print_tree.reset_mock()
                self.output(self.client.handle_clean_epg)
                self.client.print_tree.assert_called_once_with({"A": {"App": ["Empty"]}})

    def test_clean_empty_does_not_count_contract_as_endpoint(self):
        self.data["fvAEPg"] = [record("fvAEPg", dn="uni/tn-A/ap-App/epg-Empty")]
        self.data["fvRsProv"] = [record("fvRsProv", dn="uni/tn-A/ap-App/epg-Empty/rsprov-C")]
        self.output(self.client.handle_clean_empty)
        self.client.print_tree.assert_called_once_with({"A": {"App": ["Empty"]}})

    def test_clean_empty_recognizes_each_endpoint_type(self):
        for class_name in ("fvMac", "fvIp", "fvRsPathAtt"):
            with self.subTest(class_name=class_name):
                self.data = {
                    "fvAEPg": [record("fvAEPg", dn="uni/tn-A/ap-App/epg-Used")],
                    class_name: [record(class_name, dn="uni/tn-A/ap-App/epg-Used/reference")],
                }
                self.output(self.client.handle_clean_empty)
                self.client.print_tree.assert_not_called()

    def test_clean_aaep_reports_only_unreferenced_profile(self):
        self.data["infraAttEntityP"] = [record("infraAttEntityP", name=name) for name in ("Used", "Unused")]
        self.data["infraRsAttEntP"] = [record("infraRsAttEntP", tDn="uni/infra/attentp-Used")]
        self.output(self.client.handle_clean_aaep)
        self.client.print_tree.assert_called_once_with({"Global": {"AAEPs": ["Unused"]}})

    def test_clean_static_preserves_offline_nodes_and_reports_missing_vpc_peer(self):
        self.data["fabricNode"] = [record("fabricNode", id="101", fabricSt="inactive")]
        self.data["fvRsPathAtt"] = [
            record("fvRsPathAtt", dn=f"uni/tn-A/ap-App/epg-Web/rspathAtt-[{path}]", tDn=path, encap="vlan-100")
            for path in (
                "topology/pod-1/paths-101/pathep-[eth1/1]",
                "topology/pod-1/protpaths-101-102/pathep-[bundle]",
            )
        ]
        self.output(self.client.handle_clean_static, "A")
        self.assertEqual(self.client.print_tree.call_args.args[0], {
            "A": {"AP: App": {"EPG: Web": ["bundle  (vlan-100)  [node 102 not in fabric]"]}},
        })

    def test_clean_static_skips_other_tenants(self):
        self.data["fvRsPathAtt"] = [record(
            "fvRsPathAtt", dn="uni/tn-B/ap-App/epg-Web/rspathAtt-[path]",
            tDn="topology/pod-1/paths-999/pathep-[eth1/1]", encap="vlan-100",
        )]
        self.output(self.client.handle_clean_static, "A")
        self.client.print_tree.assert_not_called()

    def test_clean_overlap_reports_only_different_bds_in_same_vrf(self):
        self.data["fvRsCtx"] = [
            record("fvRsCtx", dn=f"uni/tn-A/BD-{bd}/rsctx", tnFvCtxName=vrf)
            for bd, vrf in (("LAN", "shared"), ("Web", "shared"), ("Other", "separate"))
        ]
        self.data["fvSubnet"] = [
            record("fvSubnet", dn=f"uni/tn-A/BD-{bd}/subnet-[{prefix}]", ip=prefix)
            for bd, prefix in (("LAN", "10.1.0.1/24"), ("Web", "10.1.0.129/25"), ("Other", "10.1.0.1/24"))
        ]
        self.output(self.client.handle_clean_overlap)
        self.assertEqual(self.client.print_tree.call_args.args[0], {
            "A": {"VRF: shared": ["10.1.0.1/24 (BD: LAN)  <->  10.1.0.129/25 (BD: Web)"]},
        })

    def test_clean_vlan_reports_unreferenced_pool(self):
        self.data["fvnsVlanInstP"] = [record("fvnsVlanInstP", name=name) for name in ("Used", "Unused")]
        self.data["infraRsVlanNs"] = [record("infraRsVlanNs", tDn="uni/infra/vlanns-[Used]-static")]
        self.output(self.client.handle_clean_vlan)
        self.client.print_tree.assert_called_once_with({"Global": {"vlan_pools": ["Unused"]}})

    def test_clean_subnet_matches_both_address_families_and_vrf(self):
        self.data["l3extRsEctx"] = [record("l3extRsEctx", dn="uni/tn-A/out-WAN/rsectx", tnFvCtxName="VRF")]
        self.data["l3extSubnet"] = [
            record("l3extSubnet", dn=f"uni/tn-A/out-WAN/instP-External/extsubnet-[{prefix}]", ip=prefix)
            for prefix in ("10.1.0.0/24", "2001:db8::/64", "10.2.0.0/24")
        ]
        for class_name, vrf, prefix in (
            ("uribv4Route", "VRF", "10.1.0.0/24"),
            ("uribv6Route", "VRF", "2001:db8::/64"),
            ("uribv4Route", "Other", "10.2.0.0/24"),
        ):
            self.data.setdefault(class_name, []).append(record(
                class_name, dn=f"topology/pod-1/node-101/sys/uribv4/dom-A:{vrf}/db-rt/rt-[{prefix}]", prefix=prefix,
            ))
        self.output(self.client.handle_clean_subnet, "A")
        self.assertEqual(self.client.print_tree.call_args.args[0], {
            "A": {"L3Out: WAN  (vrf: VRF)": {"InstP: External": ["10.2.0.0/24"]}},
        })

    def test_clean_contract_recognizes_vzany_and_reports_each_missing_side(self):
        self.data["vzBrCP"] = [record("vzBrCP", dn=f"uni/tn-A/brc-{name}", name=name) for name in ("None", "Provider", "Consumer", "Both")]
        self.data["vzRsAnyToProv"] = [record("vzRsAnyToProv", tDn=f"uni/tn-A/brc-{name}") for name in ("Provider", "Both")]
        self.data["fvRsCons"] = [record("fvRsCons", tDn=f"uni/tn-A/brc-{name}") for name in ("Consumer", "Both")]
        output = self.output(self.client.handle_clean_contract)
        for name in ("None", "Provider", "Consumer"):
            self.assertIn(f"  - {name}\n", output)
        self.assertNotIn("  - Both\n", output)

    def test_clean_filter_uses_full_dn_and_tenant_filter(self):
        self.data["vzFilter"] = [record("vzFilter", dn=f"uni/tn-{tenant}/flt-shared", name="shared") for tenant in ("A", "B")]
        self.data["vzRsSubjFiltAtt"] = [record("vzRsSubjFiltAtt", tDn="uni/tn-A/flt-shared")]
        output = self.output(self.client.handle_clean_filter, "B")
        self.assertIn("B:\n  - shared\n", output)
        self.assertNotIn("A:\n", output)

    def test_clean_dispatch_forwards_tenant_only_to_supported_handlers(self):
        handlers = {
            "vrf": "vrf", "bd": "bd", "bd-gw": "bd_gw", "gw-conflict": "bd_epg_gw",
            "epg": "epg", "empty": "empty", "aaep": "aaep", "domain": "domain",
            "static": "static", "overlap": "overlap", "vlan": "vlan", "contract": "contract",
            "subnet": "subnet", "filter": "filter",
        }
        tenant_commands = {"bd-gw", "gw-conflict", "static", "overlap", "subnet", "filter"}
        for suffix in handlers.values():
            setattr(self.client, f"handle_clean_{suffix}", Mock())
        for command, suffix in handlers.items():
            with self.subTest(command=command):
                self.client.handle_clean_command(command, "A")
                handler = getattr(self.client, f"handle_clean_{suffix}")
                handler.assert_called_once_with(*(("A",) if command in tenant_commands else ()))
        self.assertIn("Unknown clean command", self.output(self.client.handle_clean_command, "unknown"))