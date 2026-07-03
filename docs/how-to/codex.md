# Use etch with Codex CLI

etch runs on Codex CLI with the same skill it uses on Claude Code. Two pieces make it work: the **skill** (installable as a Codex plugin, or auto-discovered from a repo checkout) and the **MCP server** (one entry in Codex's `config.toml` — Codex plugins can't register MCP servers, so this step is manual).

## 1. Register the MCP server (required)

Add etch to `~/.codex/config.toml`:

```toml
[mcp_servers.etch]
command = "uvx"
args = ["--from", "git+https://github.com/TejGandham/etch", "etch"]
env = { "GOOGLE_API_KEY" = "your_api_key_here" }
```

Working from a local clone instead? Point `--from` at the clone's path. `uvx` builds an isolated environment on first launch and caches it. MAI-Image-2.5 needs extra env vars — see [`install.md`](../../install.md#using-mai-image-25-optional).

## 2. Get the skill

### As a plugin (any project)

etch is packaged as a Codex plugin published through the repo marketplace (`.agents/plugins/marketplace.json`). The marketplace points at `./plugins/etch`, a generated real-directory install projection of the canonical `.codex-plugin/plugin.json` and `skills/` tree.

1. In Codex, open the plugin browser: `/plugins`.
2. Add this repository as a marketplace source and install **etch**.

From the CLI, the equivalent commands are:

```bash
codex plugin marketplace add https://github.com/TejGandham/etch.git
codex plugin add etch@etch-local
```

Invoke the skill explicitly with `$etch` (type `$` to mention a skill), or just describe the task — "diagram of the auth service for the runbook" — and let Codex match the skill by its description.

### Clone and run (repo-local)

Run `codex` from inside an etch checkout. Codex scans `.agents/skills/` from your working directory up to the repo root and discovers the skill with no install step. The mirror is committed real directories, so this works the same on macOS, Linux, and Windows.

## Verify

Ask: *"etch a diagram of three boxes connected by arrows."* If the MCP server is wired up, you get a `job_id`, then ~30–60s later a saved PNG path.

## Notes

- **Reloading.** Codex loads skills and MCP config at session start. After installing or editing `config.toml`, restart Codex (or start a new session).
- **Windows.** The `.agents/skills/` mirror and `plugins/etch/` install projection are real directories, not symlinks — Codex does not detect symlinked skills on Windows ([openai/codex#8400](https://github.com/openai/codex/issues/8400)). Nothing extra is needed on Windows.
- **Duplicate listing.** If you both install the etch plugin and run Codex inside the etch repo, the skill can appear twice in `/skills` (Codex does not de-duplicate by name across sources). Harmless — pick either entry.
- **Per-skill metadata.** The skill carries an `agents/openai.yaml` (display name, short description, implicit-invocation policy) that Codex uses for presentation; it fails open if absent.

## For contributors

The Codex artifacts (`.agents/skills/`, `plugins/etch/`) are **generated** from the canonical `skills/` tree. Never hand-edit them. After editing the skill or a manifest:

```bash
uv run scripts/sync_codex_skills.py       # regenerate the projections
uv run scripts/validate_plugin.py --self-test   # manifests, version lockstep, drift
```

The validator also enforces version lockstep across `pyproject.toml`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and `.codex-plugin/plugin.json` — bump all four together.
