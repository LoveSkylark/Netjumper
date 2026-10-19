"""LibreNMS HTTP requests, caching, endpoint wrappers, and Oxidized."""

# pylint: disable=protected-access

from unittest.mock import Mock, call

from slnms_test_support import SlnmsTestCase, load_client


class ClientTests(SlnmsTestCase):
    def setUp(self):
        self.namespace = load_client()
        self.client = self.namespace["Client"]("https://nms.example.test/", "test-token", timeout=12)
        self.session = self.client._session
        self.response = self.session.get.return_value
        self.response.ok = True

    def test_constructor_normalizes_url_sets_headers_and_timeout(self):
        self.assertEqual(self.client._url, "https://nms.example.test")
        self.assertEqual(self.client._timeout, 12)
        self.assertEqual(self.client._cache, {})
        self.assertFalse(self.session.verify)
        self.session.headers.update.assert_called_once_with({
            "Content-Type": "application/json", "Accept": "application/json", "X-Auth-Token": "test-token",
        })

    def test_get_caches_results_and_can_bypass_cache(self):
        first = {"devices": [{"device_id": 1}]}
        fresh = {"devices": [{"device_id": 2}]}
        self.response.json.side_effect = [first, fresh]
        self.assertEqual(self.client._get("/api/v0/devices"), first)
        self.assertEqual(self.client._get("/api/v0/devices"), first)
        self.assertEqual(self.client._get("/api/v0/devices", cache=False), fresh)
        self.assertEqual(self.client._get("/api/v0/devices"), first)
        self.assertEqual(self.session.get.call_args_list, [
            call("https://nms.example.test/api/v0/devices", timeout=12),
            call("https://nms.example.test/api/v0/devices", timeout=12),
        ])

    def test_get_cache_is_scoped_to_client_instance(self):
        self.response.json.return_value = {"devices": []}
        self.client._get("/api/v0/devices")
        other = self.namespace["Client"]("https://other.example.test", "other-token")
        self.assertEqual(other._cache, {})

    def test_get_raises_on_http_error_without_caching_it(self):
        self.response.ok = False
        self.response.status_code = 503
        self.response.text = "unavailable"
        with self.assertRaisesRegex(self.namespace["APIError"], "HTTP 503: unavailable"):
            self.client._get("/failed")
        self.assertEqual(self.client._cache, {})

    def test_get_raises_on_api_error_and_retries_on_next_call(self):
        self.response.json.side_effect = [{"status": "error", "message": "denied"}, {"status": "ok"}]
        with self.assertRaisesRegex(self.namespace["APIError"], "API error: denied"):
            self.client._get("/api/v0/system")
        self.assertEqual(self.client._get("/api/v0/system"), {"status": "ok"})
        self.assertEqual(self.session.get.call_count, 2)

    def test_get_does_not_cache_invalid_json_or_transport_errors(self):
        self.response.json.side_effect = ValueError("invalid JSON")
        with self.assertRaises(ValueError):
            self.client._get("/invalid")
        self.session.get.side_effect = OSError("offline")
        with self.assertRaises(OSError):
            self.client._get("/offline")
        self.assertEqual(self.client._cache, {})

    def test_post_and_patch_forward_payload_and_raise_on_http_errors(self):
        for method in ("post", "patch"):
            with self.subTest(method=method):
                transport = getattr(self.session, method)
                response = transport.return_value
                response.ok = True
                response.json.return_value = {"status": "ok"}
                request = getattr(self.client, f"_{method}")
                payload = {"hostname": "router1"}
                self.assertEqual(request("/api/v0/devices", payload), {"status": "ok"})
                transport.assert_called_once_with("https://nms.example.test/api/v0/devices", json=payload, timeout=12)
                response.ok = False
                response.status_code = 403
                response.text = "forbidden"
                with self.assertRaisesRegex(self.namespace["APIError"], "HTTP 403: forbidden"):
                    request("/api/v0/devices", payload)

    def test_read_wrappers_select_expected_endpoint_and_response_key(self):
        cases = (
            ("list_bills", (), "/api/v0/bills", {"bills": [{"bill_id": 7}]}, [{"bill_id": 7}]),
            ("get_bill", (7,), "/api/v0/bills/7", {"bills": [{"bill_id": 7}]}, {"bill_id": 7}),
            ("get_bill_history", (7,), "/api/v0/bills/7/history", {"bill_history": [{"rate_95th": 100}]}, [{"rate_95th": 100}]),
            ("list_devices", (), "/api/v0/devices", {"devices": [{"device_id": 1}]}, [{"device_id": 1}]),
            ("get_device", ("router1",), "/api/v0/devices/router1", {"devices": [{"device_id": 1}]}, {"device_id": 1}),
            ("get_all_ports", (), "/api/v0/ports", {"ports": [{"port_id": 2}]}, [{"port_id": 2}]),
            ("list_links", (), "/api/v0/resources/links", {"links": [{"id": 3}]}, [{"id": 3}]),
        )
        for method, arguments, endpoint, response, expected in cases:
            with self.subTest(method=method):
                self.client._get = Mock(return_value=response)
                self.assertEqual(getattr(self.client, method)(*arguments), expected)
                self.client._get.assert_called_once_with(endpoint)

    def test_ping_always_fetches_fresh_data(self):
        self.client._get = Mock(return_value={"status": "ok"})
        self.assertEqual(self.client.ping(), {"status": "ok"})
        self.client._get.assert_called_once_with("/api/v0/system", cache=False)

    def test_bill_ports_bypasses_cache_and_defaults_to_empty(self):
        for bill, expected in (({"ports": [{"port_id": 2}]}, [{"port_id": 2}]), ({}, [])):
            with self.subTest(bill=bill):
                self.client._get = Mock(return_value={"bills": [bill]})
                self.assertEqual(self.client.get_bill_ports(7), expected)
                self.client._get.assert_called_once_with("/api/v0/bills/7", cache=False)

    def test_get_port_accepts_object_or_single_item_list_and_bypasses_cache(self):
        port = {"port_id": 2, "ifName": "eth1"}
        for value in (port, [port]):
            with self.subTest(value=value):
                self.client._get = Mock(return_value={"port": value})
                self.assertEqual(self.client.get_port(2), port)
                self.client._get.assert_called_once_with("/api/v0/ports/2", cache=False)

    def test_device_mutations_forward_payloads(self):
        payload = {"hostname": "router1"}
        self.client._post = Mock(return_value={"devices": [{"device_id": 1}]})
        self.assertEqual(self.client.add_device(payload), [{"device_id": 1}])
        self.client._post.assert_called_once_with("/api/v0/devices", payload)
        self.client._patch = Mock(return_value={"status": "ok"})
        self.assertEqual(self.client.update_device_field("router1", {"location": "DC1"}), {"status": "ok"})
        self.client._patch.assert_called_once_with("/api/v0/devices/router1", {"location": "DC1"})

    def test_list_oxidized_only_returns_lists_and_handles_http_error(self):
        for response, expected in (([{"name": "router1"}], [{"name": "router1"}]), ({"status": "ok"}, [])):
            with self.subTest(response=response):
                self.response.json.return_value = response
                self.assertEqual(self.client.list_oxidized(), expected)
        self.response.ok = False
        self.assertEqual(self.client.list_oxidized(), [])
        self.session.get.assert_called_with("https://nms.example.test/api/v0/oxidized/", timeout=12)

    def test_get_oxidized_config_accepts_string_or_line_list(self):
        for config, expected in (("hostname router1", "hostname router1"), (["line1", "line2"], "line1\nline2")):
            with self.subTest(config=config):
                self.response.json.return_value = {"config": config}
                self.assertEqual(self.client.get_oxidized_config("router1"), expected)
        self.session.get.assert_called_with("https://nms.example.test/api/v0/oxidized/config/router1", timeout=12)

    def test_get_oxidized_config_returns_none_for_failures_or_missing_config(self):
        for value in ([], {}, {"config": None}):
            with self.subTest(value=value):
                self.response.json.return_value = value
                self.assertIsNone(self.client.get_oxidized_config("router1"))
        self.response.ok = False
        self.assertIsNone(self.client.get_oxidized_config("router1"))
        self.session.get.side_effect = OSError("offline")
        self.assertIsNone(self.client.get_oxidized_config("router1"))