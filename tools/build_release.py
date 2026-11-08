"""Validate source/JSON and produce a deployment archive without dev dependencies."""
import ast
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from public_sources import public_files

root = Path(__file__).resolve().parents[1]
component = root / "custom_components" / "infra_vcenter"
for path in component.glob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
for path in component.glob("*.json"):
    json.loads(path.read_text(encoding="utf-8"))
translations = component / "translations"
translations.mkdir(exist_ok=True)
(translations / "fr.json").write_text((component / "strings.json").read_text(encoding="utf-8"), encoding="utf-8")
version = json.loads((component / "manifest.json").read_text(encoding="utf-8"))["version"]
output = root / "dist" / f"infrastructure-vcenter-{version}.zip"
output.parent.mkdir(exist_ok=True)
files = [p for p in public_files() if p.relative_to(root).parts[0] in
         ("custom_components", "dashboards", "www", "collector", "docs")
         or p.name in ("README.md", "LICENSE", "CHANGELOG.md")]
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path, path.relative_to(root))
with ZipFile(output) as archive:
    assert archive.testzip() is None
    assert not any("__pycache__" in name or ".dev-deps" in name for name in archive.namelist())
print(f"Validated archive: {output} ({len(files)} files)")
ui_output = output.parent / f"infrastructure-ui-{version}.zip"
ui_files = [p for p in files if (root / "www") in p.parents]
ui_files.append(root / "dashboards" / "INSTALLATION-VUE.md")
ui_files.append(root / "LICENSE")
with ZipFile(ui_output, "w", ZIP_DEFLATED) as archive:
    for path in ui_files:
        archive.write(path, path.relative_to(root))
with ZipFile(ui_output) as archive:
    assert archive.testzip() is None
print(f"Validated UI archive: {ui_output} ({len(ui_files)} files)")
collector_output = output.parent / f"infrastructure-collector-{version}.zip"
collector_files = [p for p in files if (root / "collector") in p.parents or (root / "www") in p.parents]
collector_files.append(root / "LICENSE")
for path in (root / "collector").glob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
with ZipFile(collector_output,"w",ZIP_DEFLATED) as archive:
    for path in collector_files:
        archive.write(path,path.relative_to(root))
with ZipFile(collector_output) as archive:
    assert archive.testzip() is None
    assert not any(name.endswith(("config.json","secrets.env")) for name in archive.namelist())
print(f"Validated collector archive: {collector_output} ({len(collector_files)} files)")
