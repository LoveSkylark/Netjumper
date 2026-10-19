"""Client session, authentication, cache, and token-file behavior."""

from ipaddress import ip_network
from pathlib import Path
import tempfile
from unittest.mock import Mock, call, mock_open, patch

from saci_test_support import HTTPError, RequestError, SaciTestCase, record


class ClientTests(SaciTestCase):
    def setUp(self):
        super().setUp()
        self.client.apic_url = "https://apic.example.test"
        self.client.verify_ssl = True
        self.client.session = Mock(cookies={})
        self.client.token = None
        self.client.username = "admin"
        self.client.password = "test-password"

    def test_constructor_configures_retries_and_ssl(self):
        for verify_ssl in (True, False):
            with self.subTest(verify_ssl=verify_ssl), tempfile.TemporaryDirectory() as directory:
                session = self.namespace["requests"].Session.return_value
                session.reset_mock()
                self.namespace["urllib3"].reset_mock()
                client = self.namespace["ACIClient"](
                    self.client.apic_url, token_file=str(Path(directory) / "absent"), verify_ssl=verify_ssl,
                )
                self.assertIsNone(client.token)
                self.assertIs(client.session, session)
                adapter = self.namespace["HTTPAdapter"].return_value
                self.assertEqual(session.mount.call_args_list, [call("http://", adapter), call("https://", adapter)])
                self.namespace["Retry"].assert_called_with(
                    total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
                )
                self.assertEqual(self.namespace["urllib3"].disable_warnings.call_count, int(not verify_ssl))

    def test_token_file_roundtrip_in_file_and_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            for token_path in (Path(directory) / "nested" / "saved-token", Path(directory)):
                with self.subTest(token_path=token_path):
                    self.client.token_file = str(token_path)
                    self.assertIsNone(self.client.load_token_from_file())
                    self.client.token = "example-token\n"
                    self.client.save_token_to_file()
                    self.assertEqual(self.client.load_token_from_file(), "example-token")

    def test_token_validation_sets_cookie_and_checks_status(self):
        self.assertFalse(self.client.is_token_valid())
        self.client.session.get.assert_not_called()
        self.client.token = "existing-token"
        for status_code, expected in ((200, True), (401, False), (500, False)):
            with self.subTest(status_code=status_code):
                self.client.session.get.return_value.status_code = status_code
                self.assertEqual(self.client.is_token_valid(), expected)
        self.assertEqual(self.client.session.cookies["APIC-cookie"], "existing-token")
        self.client.session.get.side_effect = RequestError("unavailable")
        self.assertFalse(self.client.is_token_valid())

    def test_prompt_credentials_reads_password_without_echo(self):
        with patch("builtins.input", return_value="user") as username, patch.object(
            self.namespace["getpass"], "getpass", return_value="secret",
        ) as password:
            self.assertEqual(self.client.prompt_credentials(), ("user", "secret"))
        username.assert_called_once_with("Username: ")
        password.assert_called_once_with("Password: ")

    def test_login_reuses_valid_token(self):
        self.client.token = "valid-token"
        self.client.is_token_valid = Mock(return_value=True)
        self.client.login()
        self.client.session.post.assert_not_called()

    def test_login_uses_config_credentials_and_persists_new_token(self):
        self.client.session.post.return_value.json.return_value = {
            "imdata": [record("aaaLogin", token="new-token")],
        }
        self.client.save_token_to_file = Mock()
        self.client.prompt_credentials = Mock()
        self.client.login()
        self.client.session.post.assert_called_once_with(
            "https://apic.example.test/api/aaaLogin.json",
            json={"aaaUser": {"attributes": {"name": "admin", "pwd": "test-password"}}}, verify=True,
        )
        self.assertEqual(self.client.token, "new-token")
        self.assertEqual(self.client.session.cookies["APIC-cookie"], "new-token")
        self.client.save_token_to_file.assert_called_once_with()
        self.client.prompt_credentials.assert_not_called()

    def test_login_uses_environment_when_config_is_empty(self):
        self.client.username = ""
        self.client.password = ""
        self.client.save_token_to_file = Mock()
        self.client.session.post.return_value.json.return_value = {"imdata": [record("aaaLogin", token="token")]}
        with patch.dict("os.environ", {"APIC_USERNAME": "env-user", "APIC_PASSWORD": "env-password"}, clear=True):
            self.client.login()
        payload = self.client.session.post.call_args.kwargs["json"]
        self.assertEqual(payload["aaaUser"]["attributes"], {"name": "env-user", "pwd": "env-password"})

    def test_login_prompts_when_credentials_are_missing(self):
        self.client.username = " "
        self.client.password = " "
        self.client.prompt_credentials = Mock(return_value=("prompt-user", "prompt-password"))
        self.client.save_token_to_file = Mock()
        self.client.session.post.return_value.json.return_value = {"imdata": [record("aaaLogin", token="token")]}
        with patch.dict("os.environ", {}, clear=True):
            self.client.login()
        self.client.prompt_credentials.assert_called_once_with()
        self.assertEqual(self.client.session.post.call_args.kwargs["json"]["aaaUser"]["attributes"]["name"], "prompt-user")

    def test_login_retries_unauthorized_once_with_prompted_credentials(self):
        response = self.client.session.post.return_value
        response.raise_for_status.side_effect = [HTTPError(401), None]
        response.json.return_value = {"imdata": [record("aaaLogin", token="retried-token")]}
        self.client.prompt_credentials = Mock(return_value=("retry-user", "retry-password"))
        self.client.save_token_to_file = Mock()
        with patch("builtins.open", mock_open()):
            self.client.login()
        self.assertEqual(self.client.session.post.call_count, 2)
        self.client.prompt_credentials.assert_called_once_with()
        self.assertEqual(self.client.token, "retried-token")
        self.assertEqual(self.client.session.post.call_args.kwargs["json"]["aaaUser"]["attributes"]["name"], "retry-user")

    def test_login_stops_after_two_unauthorized_responses(self):
        self.client.session.post.return_value.raise_for_status.side_effect = HTTPError(401)
        self.client.prompt_credentials = Mock(return_value=("retry-user", "retry-password"))
        with patch("builtins.open", mock_open()), self.assertRaises(SystemExit) as raised:
            self.output(self.client.login)
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(self.client.session.post.call_count, 2)

    def test_login_exits_on_transport_http_and_malformed_response_errors(self):
        for failure in (RequestError("offline"), HTTPError(500), None):
            with self.subTest(failure=failure):
                self.client.session.post.return_value.raise_for_status.side_effect = failure
                self.client.session.post.return_value.json.return_value = {"imdata": []}
                with self.assertRaises(SystemExit) as raised:
                    self.output(self.client.login)
                self.assertEqual(raised.exception.code, 1)

    def test_query_api_forwards_filter_and_caches_identical_queries(self):
        del self.client.query_api
        records = [record("fvBD", dn="uni/tn-A/BD-LAN")]
        self.client.session.get.return_value.json.return_value = {"imdata": records}
        endpoint = "/api/node/class/fvBD.json"
        filter_str = 'eq(fvBD.name,"LAN")'
        self.assertEqual(self.client.query_api(endpoint, filter_str), records)
        self.assertEqual(self.client.query_api(endpoint, filter_str), records)
        self.client.session.get.assert_called_once_with(
            self.client.apic_url + endpoint, params={"query-target-filter": filter_str}, verify=True,
        )
        self.client.query_api(endpoint)
        self.assertEqual(self.client.session.get.call_count, 2)
        self.assertIsNone(self.client.session.get.call_args.kwargs["params"])

    def test_query_api_returns_empty_on_request_failure_and_missing_imdata(self):
        del self.client.query_api
        self.client.session.get.side_effect = RequestError("offline")
        self.assertEqual(self.client.query_api("/failed.json"), [])
        self.namespace["logger"].error.assert_called_once()
        self.client.session.get.side_effect = None
        self.client.session.get.return_value.json.return_value = {}
        self.assertEqual(self.client.query_api("/empty.json"), [])

    def test_get_tep_pool_normalizes_network_and_caches_result(self):
        self.data["/api/node/mo/uni/infra/settings.json"] = [record("infraSetPol", tepPool="10.0.0.1/16")]
        self.assertEqual(self.client.get_tep_pool(), ip_network("10.0.0.0/16"))
        self.client.get_tep_pool()
        self.client.query_api.assert_called_once()

    def test_get_tep_pool_ignores_invalid_network(self):
        self.data["/api/node/mo/uni/infra/settings.json"] = [record("infraSetPol", tepPool="invalid")]
        self.assertIsNone(self.client.get_tep_pool())

    def test_inventory_only_includes_active_nodes_and_is_cached(self):
        self.data["fabricNode"] = [
            record("fabricNode", id="101", name="leaf1", fabricSt="active"),
            record("fabricNode", id="102", name="leaf2", fabricSt="inactive"),
        ]
        self.assertEqual(self.client.get_node_inventory(), {"101": "leaf1"})
        self.client.get_node_inventory()
        self.client.query_api.assert_called_once()

    def test_normalize_node_label_handles_single_vpc_and_unknown_nodes(self):
        self.client.get_node_inventory = Mock(return_value={"101": "leaf1", "102": "leaf2"})
        self.assertEqual(self.client.normalize_node_label("1", "101"), "leaf1 [101]")
        self.assertEqual(self.client.normalize_node_label("1", "101-102"), "leaf1 & leaf2 [101-102]")
        self.assertEqual(self.client.normalize_node_label("1", "999"), "Node999 [999]")

    def test_get_pod_for_node_resolves_id_name_and_missing_node(self):
        nodes = [record("topSystem", id="101", name="leaf1", podId="2")]
        self.assertEqual(self.client.get_pod_for_node(nodes, node_id="101"), ("2", "101"))
        self.assertEqual(self.client.get_pod_for_node(nodes, node_name="leaf1"), ("2", "101"))
        self.assertIsNone(self.client.get_pod_for_node(nodes, node_id="999"))