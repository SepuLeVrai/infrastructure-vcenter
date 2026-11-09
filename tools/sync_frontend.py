"""Bundle the canonical card inside the integration for HACS installations."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'www/infra-vcenter/infrastructure-card.js'
TARGET = ROOT / 'custom_components/infra_vcenter/frontend/infrastructure-card.js'


def sync(check=False):
    data = SOURCE.read_bytes()
    if check:
        if not TARGET.is_file() or TARGET.read_bytes() != data:
            raise SystemExit('Bundled card differs. Run python tools/sync_frontend.py')
    else:
        TARGET.parent.mkdir(exist_ok=True)
        TARGET.write_bytes(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    sync(parser.parse_args().check)
