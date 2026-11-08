"""Curated source files for distribution; never include runtime configurations."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL = ('README.md', 'LICENSE', 'CHANGELOG.md', '.gitignore', '.editorconfig',
             'requirements-dev.txt', 'package.json', 'package-lock.json')
FOLDERS = ('custom_components', 'www', 'collector', 'dashboards', 'docs', 'tests', 'tools', '.github')
ALLOWED_SUFFIXES = {'.py', '.js', '.cjs', '.json', '.md', '.yaml', '.yml', '.sh', '.service', '.svg', '.png', '.example'}


def public_files():
    files = [ROOT / name for name in TOP_LEVEL if (ROOT / name).is_file()]
    for folder in FOLDERS:
        for path in (ROOT / folder).rglob('*'):
            if (not path.is_file() or '__pycache__' in path.parts or path.suffix not in ALLOWED_SUFFIXES
                    or path.name in {'config.json', 'secrets.env'} or path.name.endswith('.generated.json')):
                continue
            files.append(path)
    return sorted(set(files))
