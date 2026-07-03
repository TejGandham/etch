# Use etch with Claude Code

etch is a Claude Code plugin: one skill plus the etch MCP server, installed together from the repo marketplace. Installing the plugin is the whole setup — the MCP server is bundled in the plugin manifest and registers automatically.

## Install

```bash
/plugin marketplace add https://github.com/TejGandham/etch.git
/plugin install etch@etch
```

This registers:

- **The etch MCP server** — launched via `uvx` from the installed plugin's own code (`${CLAUDE_PLUGIN_ROOT}`), so the server version always matches the plugin version. Tools: `start_diagram_job`, `start_variant_job`, `check_job_status`.
- **The `etch` skill** — audience-aware diagram generation. It activates when you ask for a technical/architecture diagram aimed at a specific audience ("diagram for the architects", "exec slide of our system"), or when you invoke etch by name.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) on your PATH (`uv` ships `uvx`; the MCP server builds itself on first launch and is cached after that).
- `GOOGLE_API_KEY` exported in your environment — get one at https://aistudio.google.com/. The plugin manifest can't carry your secret; the server inherits Claude Code's environment.
- *(optional)* MAI-Image-2.5 needs its own env vars — see [`install.md`](../../install.md#using-mai-image-25-optional).

## Verify

Start a new session, then ask: *"etch a diagram of three boxes connected by arrows."* You should get a `job_id` back, and ~30–60s later a saved PNG path.

## Notes

- **Reloading.** Claude Code loads plugins at session start. After installing or updating, restart Claude Code (or start a new session).
- **Updating.** Re-add or update from `/plugin` to pull a newer version from the marketplace.
- **Manual MCP config instead.** If you'd rather not install the plugin (e.g. you only want the tools, not the skill), the classic MCP-config route in [`install.md`](../../install.md) still works and is what non-plugin MCP clients (Claude Desktop, etc.) use.
