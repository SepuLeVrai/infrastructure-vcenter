"""Reject common private deployment data in the curated distribution."""
import ipaddress
import re
from public_sources import ROOT, public_files

PRIVATE = [ipaddress.ip_network(network) for network in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
IP = re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')
PERSONAL_PATH = re.compile(r'(?:[A-Z]:[\\/]Users[\\/]|/home/[^/\s]+/|-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----)', re.I)


def check():
    failures = []
    for path in public_files():
        if path.suffix == '.png':
            continue
        content = path.read_text(encoding='utf-8')
        if re.search(r'[\u00c2\u00c3\ufffd]', content):
            failures.append(f'{path.relative_to(ROOT)}: possible corrupted text encoding')
        if re.search(r'[\u2010-\u2015\u2212\ufe58\ufe63\uff0d]', content):
            failures.append(f'{path.relative_to(ROOT)}: use ASCII hyphens')
        # The checker contains its own private-range and personal-path patterns.
        if path.name == 'check_public_sources.py':
            continue
        if PERSONAL_PATH.search(content):
            failures.append(f'{path.relative_to(ROOT)}: personal path or private key')
        for candidate in IP.findall(content):
            try:
                address = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if any(address in network for network in PRIVATE):
                failures.append(f'{path.relative_to(ROOT)}: private network address')
    if failures:
        raise SystemExit('\n'.join(failures))
    print(f'Public source checks passed ({len(public_files())} files). Review content before publication.')


if __name__ == '__main__':
    check()
