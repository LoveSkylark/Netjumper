"""Load SACI definitions without HTTP packages or import-time log files."""

# pylint: disable=exec-used

import ast
import contextlib
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


class RequestError(Exception):
    pass


class HTTPError(RequestError):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.response = SimpleNamespace(status_code=status_code)


def record(class_name, **attributes):
    return {class_name: {"attributes": attributes}}


def load_saci():
    source_path = SCRIPTS / "saci.py"
    source = ast.parse(source_path.read_text(encoding="utf-8"))
    excluded = {"requests", "urllib3", "config_service"}
    definitions = []
    for node in source.body:
        if isinstance(node, ast.Import):
            if not any(alias.name.split(".")[0] in excluded for alias in node.names):
                definitions.append(node)
        elif isinstance(node, ast.ImportFrom):
            if node.module.split(".")[0] not in excluded:
                definitions.append(node)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            definitions.append(node)
    namespace = {
        "__name__": "saci_under_test",
        "logger": Mock(),
        "requests": SimpleNamespace(
            Session=Mock(), RequestException=RequestError,
            exceptions=SimpleNamespace(HTTPError=HTTPError),
        ),
        "urllib3": Mock(),
        "HTTPAdapter": Mock(),
        "Retry": Mock(),
        "load_apic_settings": Mock(),
        "_log_file": "/unused/saci-test.log",
    }
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source_path), "exec"), namespace)
    return namespace


class SaciTestCase(unittest.TestCase):
    def setUp(self):
        self.namespace = load_saci()
        self.client = self.namespace["ACIClient"].__new__(self.namespace["ACIClient"])
        self.data = {}
        self.client.query_api = Mock(side_effect=self.query)
        self.client.print_tree = Mock()

    def query(self, endpoint, _filter_str=""):
        if endpoint in self.data:
            return self.data[endpoint]
        class_name = endpoint.split("?", 1)[0].rsplit("/", 1)[-1].removesuffix(".json")
        return self.data.get(class_name, [])

    def output(self, function, *args, **kwargs):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            function(*args, **kwargs)
        return stream.getvalue()