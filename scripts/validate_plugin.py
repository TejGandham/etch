# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Plugin integrity check: manifests, version lockstep, skill frontmatter, projections.

Usage:
  uv run scripts/validate_plugin.py --self-test   # check this repo, exit 0/1
"""
from __future__ import annotations
import argparse, json, re, sys, tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
LINK_RE = re.compile(r"\(([^\s)]+\.(?:md|json|py))\)")        # markdown links (no spaces)
PATH_RE = re.compile(r"`(references/[^`]+|scripts/[^`]+)`")    # backticked paths

# Reuse the generator's projection logic so the validator and the writer can never
# disagree about what "in sync" means. (Importing is side-effect-free: argparse runs
# only under the script's __main__.)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_codex_skills  # noqa: E402


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def _load_json(path: Path, errors: list[str]) -> dict:
    if not path.exists():
        errors.append(f"{path.relative_to(ROOT)}: missing")
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        errors.append(f"{path.relative_to(ROOT)}: invalid JSON ({e})")
        return {}


def check() -> list[str]:
    errors: list[str] = []
    skill_dirs = [p.parent for p in SKILLS.glob("*/SKILL.md")]
    if not skill_dirs:
        errors.append("no skills found under skills/*/SKILL.md")
    for sd in sorted(skill_dirs):
        text = (sd / "SKILL.md").read_text()
        fm = _frontmatter(text)
        for field in ("name", "description"):
            if not fm.get(field):
                errors.append(f"{sd.name}: SKILL.md missing frontmatter '{field}'")
        cited = set(LINK_RE.findall(text)) | set(PATH_RE.findall(text))
        for rel in sorted(cited):
            if rel.startswith(("http://", "https://")):
                continue
            target = (sd / rel).resolve()
            if not str(target).startswith(str(ROOT)):
                continue  # out-of-tree example path, not a repo file
            if not target.exists():
                errors.append(f"{sd.name}: SKILL.md cites missing path '{rel}'")

    present = {sd.name for sd in skill_dirs}

    # Claude plugin manifest — must exist, must bundle the etch MCP server so a
    # plugin install registers the tools with zero extra setup.
    claude = _load_json(ROOT / ".claude-plugin" / "plugin.json", errors)
    if claude:
        for field in ("name", "version", "description"):
            if not claude.get(field):
                errors.append(f".claude-plugin/plugin.json: missing '{field}'")
        etch_server = claude.get("mcpServers", {}).get("etch", {})
        if not etch_server:
            errors.append(".claude-plugin/plugin.json: missing mcpServers.etch (plugin must register the MCP server)")
        elif "${CLAUDE_PLUGIN_ROOT}" not in json.dumps(etch_server):
            errors.append(".claude-plugin/plugin.json: mcpServers.etch must launch from ${CLAUDE_PLUGIN_ROOT} so the server runs the installed plugin's own code")

    # Claude marketplace manifest: a `strict` plugin only loads what it lists, so a
    # skill dir added without a manifest line would silently never register.
    mp = _load_json(ROOT / ".claude-plugin" / "marketplace.json", errors)
    for plugin in mp.get("plugins", []):
        pname = plugin.get("name", "?")
        if plugin.get("source") != "./":
            errors.append(f".claude-plugin/marketplace.json: plugin '{pname}' source must stay './' for Claude plugin installs")
        listed_raw = plugin.get("skills")
        if not isinstance(listed_raw, list):
            continue  # directory-form ("./skills/") or absent — nothing to enumerate
        listed = {Path(s).name for s in listed_raw}
        for name in sorted(present - listed):
            errors.append(f"marketplace.json: skill '{name}' exists under skills/ but plugin '{pname}' does not list it")
        for name in sorted(listed - present):
            errors.append(f"marketplace.json: plugin '{pname}' lists '{name}' but skills/{name}/SKILL.md is missing")

    # Version lockstep — the plugin IS the package, so every manifest must agree
    # with pyproject.toml.
    versions: dict[str, str | None] = {}
    pyproject = ROOT / "pyproject.toml"
    if pyproject.exists():
        versions["pyproject.toml"] = tomllib.loads(pyproject.read_text()).get("project", {}).get("version")
    versions[".claude-plugin/plugin.json"] = claude.get("version")
    versions[".claude-plugin/marketplace.json (metadata.version)"] = mp.get("metadata", {}).get("version")
    codex = _load_json(ROOT / ".codex-plugin" / "plugin.json", errors)
    versions[".codex-plugin/plugin.json"] = codex.get("version")
    distinct = {v for v in versions.values() if v}
    if len(distinct) > 1 or None in versions.values():
        pretty = ", ".join(f"{k}={v!r}" for k, v in versions.items())
        errors.append(f"version lockstep broken: {pretty}")

    _check_codex(errors, present, codex)
    return errors


def _check_codex(errors: list[str], skill_names: set[str], codex: dict) -> None:
    """Guard the Codex artifacts and every generated projection against drift."""
    # 1. Codex plugin manifest — well-formed and consistent with Claude's.
    claude = _load_json(ROOT / ".claude-plugin" / "plugin.json", [])
    if codex:
        for field in ("name", "version", "description"):
            if not codex.get(field):
                errors.append(f".codex-plugin/plugin.json: missing '{field}'")
        if claude:
            for field in ("name", "version"):
                if codex.get(field) != claude.get(field):
                    errors.append(
                        f".codex-plugin/plugin.json: '{field}' ({codex.get(field)!r}) "
                        f"!= .claude-plugin/plugin.json ({claude.get(field)!r})")
        skills_ptr = codex.get("skills")
        if isinstance(skills_ptr, str) and not (ROOT / skills_ptr).is_dir():
            errors.append(f".codex-plugin/plugin.json: skills path '{skills_ptr}' is not a directory")
        iface = codex.get("interface", {})
        for field in ("displayName", "shortDescription", "category"):
            if not iface.get(field):
                errors.append(f".codex-plugin/plugin.json: interface missing '{field}'")

    # 2. Codex repo marketplace — shape + plugin entry policy/category.
    market = _load_json(ROOT / ".agents" / "plugins" / "marketplace.json", errors)
    if market:
        if not market.get("name"):
            errors.append(".agents/plugins/marketplace.json: missing top-level 'name'")
        if not market.get("interface", {}).get("displayName"):
            errors.append(".agents/plugins/marketplace.json: missing interface.displayName")
        for entry in market.get("plugins", []):
            pn = entry.get("name", "?")
            src = entry.get("source", {})
            if not (src.get("source") and src.get("path")):
                errors.append(f".agents/plugins/marketplace.json: plugin '{pn}' missing source.source/source.path")
            expected_path = f"./plugins/{pn}"
            if src.get("path") != expected_path:
                errors.append(
                    f".agents/plugins/marketplace.json: plugin '{pn}' source.path "
                    f"{src.get('path')!r} != {expected_path!r}")
            else:
                plugin_root = ROOT / expected_path
                if not plugin_root.is_dir():
                    errors.append(f".agents/plugins/marketplace.json: plugin '{pn}' path '{expected_path}' is missing")
                elif not (plugin_root / ".codex-plugin" / "plugin.json").exists():
                    errors.append(f"{plugin_root.relative_to(ROOT)}/.codex-plugin/plugin.json: missing")
            pol = entry.get("policy", {})
            if not (pol.get("installation") and pol.get("authentication")):
                errors.append(f".agents/plugins/marketplace.json: plugin '{pn}' missing policy.installation/authentication")
            if not entry.get("category"):
                errors.append(f".agents/plugins/marketplace.json: plugin '{pn}' missing 'category'")
            if codex and pn != codex.get("name"):
                errors.append(f".agents/plugins/marketplace.json: plugin '{pn}' != plugin.json name '{codex.get('name')}'")

    # 3. Repo-local skill mirror — byte-parity with skills/, no orphans.
    want, names = sync_codex_skills.expected()
    for p, content in sorted(want.items()):
        if not p.exists():
            errors.append(f"{p.relative_to(ROOT)}: missing from .agents/skills mirror (run sync_codex_skills.py)")
        elif p.read_bytes() != content:
            errors.append(f"{p.relative_to(ROOT)}: differs from canonical skill (run sync_codex_skills.py)")
    for p in sorted(set(sync_codex_skills.mirror_files()) - set(want)):
        errors.append(f"{p.relative_to(ROOT)}: orphaned in mirror (no canonical source)")
    for name in sorted(sync_codex_skills.mirror_skill_names() - names):
        errors.append(f".agents/skills/{name}: orphaned (no skills/{name})")
    install_want = sync_codex_skills.expected_install_projection()
    install_have = set(sync_codex_skills.install_projection_files())
    for p, content in sorted(install_want.items()):
        if not p.exists():
            errors.append(f"{p.relative_to(ROOT)}: missing from Codex install projection (run sync_codex_skills.py)")
        elif p.read_bytes() != content:
            errors.append(f"{p.relative_to(ROOT)}: differs from canonical Codex install projection (run sync_codex_skills.py)")
    for p in sorted(install_have - set(install_want)):
        errors.append(f"{p.relative_to(ROOT)}: orphaned in Codex install projection (no canonical source)")
    for name in sorted(sync_codex_skills.install_projection_skill_names() - names):
        errors.append(f"plugins/etch/skills/{name}: orphaned (no skills/{name})")

    # 4. Per-skill Codex metadata — present and declares a display name.
    for name in sorted(skill_names):
        yml = SKILLS / name / "agents" / "openai.yaml"
        if not yml.exists():
            errors.append(f"{name}: missing agents/openai.yaml")
        elif "display_name:" not in yml.read_text():
            errors.append(f"{name}: agents/openai.yaml missing interface.display_name")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.parse_args()
    errors = check()
    if errors:
        print("PLUGIN INTEGRITY: FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("PLUGIN INTEGRITY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
