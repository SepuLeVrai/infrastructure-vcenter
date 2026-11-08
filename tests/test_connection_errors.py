"""Check useful diagnoses and credential masking before UI/log output."""
import importlib.util
from pathlib import Path
import socket
import ssl
import unittest

path = Path(__file__).resolve().parents[1] / "custom_components/infra_vcenter/connection_errors.py"
spec = importlib.util.spec_from_file_location("connection_errors", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DiagnosticTests(unittest.TestCase):
    def test_categories(self):
        cases = [
            (ssl.SSLCertVerificationError("bad certificate"), "invalid_certificate"),
            (ssl.SSLError("handshake"), "tls_error"),
            (socket.gaierror("missing host"), "dns_error"),
            (TimeoutError("timeout"), "timeout"),
            (ConnectionRefusedError("refused"), "connection_refused"),
            (TypeError("SDK issue"), "cannot_connect"),
        ]
        for error, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(module.connection_diagnostic(error, {})[0], expected)

    def test_credentials_masked_before_truncating(self):
        error = RuntimeError("user=supervision password=secret-password\nhttps://other:token@vc/sdk " + "x"*600)
        code, detail = module.connection_diagnostic(error, {
            "username": "supervision", "password": "secret-password"})
        self.assertEqual(code, "cannot_connect")
        for secret in ("supervision", "secret-password", "other:token", "\n"):
            self.assertNotIn(secret, detail)
        self.assertLessEqual(len(detail), 500)
        self.assertIn("RuntimeError", detail)

    def test_permission_error(self):
        error = type("NoPermission", (Exception,), {})("denied")
        self.assertEqual(module.connection_diagnostic(error, {})[0], "no_permission")


if __name__ == "__main__":
    unittest.main()
