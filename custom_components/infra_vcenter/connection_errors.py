"""Actionable connection diagnostics without credentials or raw tracebacks."""
import re
import socket
import ssl


def connection_diagnostic(error, config):
    """Return a UI error key and a bounded, redacted technical detail."""
    if isinstance(error, ssl.SSLCertVerificationError):
        code = "invalid_certificate"
    elif isinstance(error, ssl.SSLError):
        code = "tls_error"
    elif isinstance(error, socket.gaierror):
        code = "dns_error"
    elif isinstance(error, (TimeoutError, socket.timeout)):
        code = "timeout"
    elif isinstance(error, ConnectionRefusedError):
        code = "connection_refused"
    elif type(error).__name__ == "NoPermission":
        code = "no_permission"
    elif type(error).__name__ == "EndpointTypeError":
        code = "wrong_endpoint"
    elif type(error).__name__ == "HostSelectionError":
        code = "host_selection"
    else:
        code = "cannot_connect"
    # Redact known credentials before truncating. Never include config/repr or locals.
    detail = str(error)
    for key in ("password", "username"):
        secret = config.get(key)
        if secret:
            detail = detail.replace(str(secret), "[masqué]")
    detail = re.sub(r"(?i)(https?://)[^\s/@]+:[^\s/@]+@", r"\1[masqué]@", detail)
    detail = " ".join(detail.split())
    return code, f"{type(error).__name__}: {detail}"[:500]
