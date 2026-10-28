#!/usr/bin/env python3
"""Repository checks (run locally or in CI): python3 tools/check_repo.py
- every JSON file parses
- every Python file compiles
- every skills/*/SKILL.md has front matter with name == folder name and a description <= 1024 chars
- the API client copies in skills/*/scripts/invoice_api.py are identical
- no .env file and no API key pattern is committed (files git would commit)
"""
import hashlib
import json
import pathlib
import py_compile
import re
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parent.parent
skip = {".git", "__pycache__", ".tmp-check", "node_modules"}
files = [p for p in root.rglob("*") if p.is_file() and not (set(p.relative_to(root).parts) & skip)]
try:  # only what git would commit: a local, ignored .env with the user's key is fine
    listed = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=root,
                            capture_output=True, text=True, check=True).stdout.splitlines()
    files = [p for p in files if str(p.relative_to(root)) in set(listed)]
except (OSError, subprocess.CalledProcessError):
    pass
errors = []

for p in files:
    rel = p.relative_to(root)
    if p.suffix == ".json":
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"{rel}: invalid JSON ({e})")
    if p.suffix == ".py":
        try:
            py_compile.compile(str(p), doraise=True, cfile=None)
        except py_compile.PyCompileError as e:
            errors.append(f"{rel}: {e.msg}")
    if p.name == ".env" or p.name.startswith(".env."):
        errors.append(f"{rel}: .env file must not be committed")
    if p.suffix in (".py", ".md", ".json") and re.search(r"sk_(live|test)_[A-Za-z0-9]{16,}", p.read_text(encoding="utf-8", errors="ignore")):
        errors.append(f"{rel}: looks like an API key")

for skill in sorted((root / "skills").iterdir()):
    if not skill.is_dir():
        continue
    md = skill / "SKILL.md"
    if not md.exists():
        errors.append(f"{skill.name}: SKILL.md missing")
        continue
    m = re.match(r"^---\n(.*?)\n---\n", md.read_text(encoding="utf-8"), re.S)
    if not m:
        errors.append(f"{skill.name}: SKILL.md without front matter")
        continue
    fm = dict(l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)
    if fm.get("name", "").strip() != skill.name:
        errors.append(f"{skill.name}: front matter name '{fm.get('name', '').strip()}' != folder name")
    desc = fm.get("description", "").strip()
    if not desc or len(desc) > 1024:
        errors.append(f"{skill.name}: description missing or longer than 1024 characters")

clients = sorted(root.glob("skills/*/scripts/invoice_api.py"))
digests = {hashlib.sha256(c.read_bytes()).hexdigest() for c in clients}
if len(digests) > 1:
    errors.append("skills/*/scripts/invoice_api.py copies differ - keep them identical: " + ", ".join(str(c.relative_to(root)) for c in clients))

if errors:
    print("\n".join("FAIL " + e for e in errors))
    sys.exit(1)
print(f"OK - {len(files)} files, {len(list((root / 'skills').glob('*/SKILL.md')))} skills, {len(clients)} identical API clients")
