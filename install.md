# Installing etch

The short version: **point your agent at this repo and it'll handle the rest.**

## Prerequisites

- An MCP-aware agent (Claude Desktop, Claude Code, etc.).
- A Google AI Studio API key — get one at https://aistudio.google.com/.
- [uv](https://docs.astral.sh/uv/) installed (`uv` ships `uvx`). Most agents that support MCP already have uv on their PATH; if yours doesn't, install it first.

## Configure your agent

Add etch to your MCP client config. For example, Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "etch": {
      "command": "uvx",
      "args": ["--from", "/path/to/etch", "etch"],
      "env": { "GOOGLE_API_KEY": "your_api_key_here" }
    }
  }
}
```

Replace `/path/to/etch` with the absolute path to your local clone. To install directly from git instead, swap that arg for the repo URL:

```json
"args": ["--from", "git+https://github.com/<owner>/etch", "etch"]
```

`uvx` builds an isolated environment on first launch and caches it; there is no manual install step. Restart your agent to pick up the new MCP server.

## Verify

Ask your agent: *"etch a diagram of three boxes connected by arrows."* If etch is wired up, the agent will get back a `job_id`, then ~30–60s later a saved PNG path.

## Skill (optional but recommended)

The `etch` skill at `skills/etch/SKILL.md` adds audience-aware diagram generation. If your agent has a skills directory, point it at `skills/etch/` (or symlink it in). The skill activates on requests like *"diagram of the auth service for a runbook"* and chooses the right audience prose automatically.

## Troubleshooting

- **Tool not visible after editing config.** Restart your agent fully — many MCP clients only read config at startup.
- **`GOOGLE_API_KEY environment variable is not set`.** The key has to live in the `env` block of the MCP config. The MCP server inherits the agent's env, not your shell's.
- **Generation fails.** Check `check_job_status(job_id)` for the failure reason. Most failures are upstream (Gemini quota or content policy); retry with a tighter description.
