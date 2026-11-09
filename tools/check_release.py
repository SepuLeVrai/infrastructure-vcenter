"""Verify release/HACS metadata, archives and checksums before uploading."""
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
component = ROOT / 'custom_components/infra_vcenter'
manifest = json.loads((component / 'manifest.json').read_text(encoding='utf-8'))
hacs = json.loads((ROOT / 'hacs.json').read_text(encoding='utf-8'))
version = manifest['version']
assert hacs['zip_release'] is True and hacs['filename'] == 'infra_vcenter.zip'
assert json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version'] == version
assert re.search(r'VERSION = "' + re.escape(version) + r'"', (component / 'const.py').read_text(encoding='utf-8'))
dist = ROOT / 'dist'
expected = {'infra_vcenter.zip', f'infrastructure-vcenter-{version}.zip',
            f'infrastructure-ui-{version}.zip', f'infrastructure-collector-{version}.zip'}
seen = set()
for line in (dist / 'SHA256SUMS').read_text(encoding='ascii').splitlines():
    checksum, name = line.split('  ', 1)
    assert name in expected and name not in seen
    assert checksum == hashlib.sha256((dist / name).read_bytes()).hexdigest()
    seen.add(name)
    with ZipFile(dist / name) as archive:
        assert archive.testzip() is None
        for member in archive.namelist():
            assert not member.startswith('/') and '..' not in Path(member).parts
            assert Path(member).name not in ('config.json', 'secrets.env')
            assert '__pycache__' not in member and not member.endswith('.pyc')
assert seen == expected
with ZipFile(dist / 'infra_vcenter.zip') as archive:
    assert json.loads(archive.read('manifest.json'))['version'] == version
    assert archive.read('frontend/infrastructure-card.js') == (ROOT / 'www/infra-vcenter/infrastructure-card.js').read_bytes()
    assert not any(name.startswith(('custom_components/', 'collector/', 'www/')) for name in archive.namelist())
print(f'Release {version} validated: HACS metadata, bundled card, 4 archives, checksums and excluded runtime configuration.')
