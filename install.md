# Installing etch

The short version: **point your agent at this repo and it'll handle the rest.**

## Claude Code or Codex CLI? Install the plugin instead

If your agent is Claude Code or Codex CLI, skip the manual MCP config below — etch ships as a plugin for both, and the plugin carries the skill:

- **Claude Code**: `/plugin marketplace add https://github.com/TejGandham/etch.git` then `/plugin install etch@etch`. The MCP server registers automatically. See [docs/how-to/claude-code.md](docs/how-to/claude-code.md).
- **Codex CLI**: install the skill from the repo marketplace and add one `[mcp_servers.etch]` entry to `config.toml`. See [docs/how-to/codex.md](docs/how-to/codex.md).

Everything below is for other MCP clients (Claude Desktop, etc.) or for wiring the server by hand.

## Prerequisites

- An MCP-aware agent (Claude Desktop, Claude Code, etc.).
- A Google AI Studio API key — get one at https://aistudio.google.com/.
- *(optional)* To use MAI-Image-2.5, an Azure AI Foundry MAI deployment — its endpoint and key. See [Using MAI-Image-2.5](#using-mai-image-25-optional) below.
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

## Using MAI-Image-2.5 (optional)

etch generates with **Google Gemini** (`gemini-3-pro-image-preview`) by default — if that's all you need, you can skip this section. **Microsoft MAI-Image-2.5** is available as an additional provider.

Pick the provider per request with the `model` argument on `start_diagram_job`:

```
start_diagram_job(description="...", model="mai-image-2.5")
```

Omit `model` (or pass `gemini-3-pro-image-preview`) to use the default.

MAI reaches the model through one of two transports, chosen by `MAI_TRANSPORT` (default `foundry`): **Azure AI Foundry**, or **OpenRouter** (no Azure provisioning).

#### Azure AI Foundry (default)

Needs three env vars in the MCP config alongside `GOOGLE_API_KEY`:

| Variable | Required | Notes |
|-|-|-|
| `MAI_API_KEY` | yes | Your Azure AI Foundry key. |
| `MAI_ENDPOINT` | yes | The resource base, e.g. `https://<resource>.services.ai.azure.com`. |
| `MAI_DEPLOYMENT` | no | Deployment name; defaults to `MAI-Image-2.5`. |

Deploying MAI-Image-2.5 in Foundry is documented by Microsoft: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai

**Capability note:** MAI supports **1K only** (no 2K) and does **not** support the `21:9` ultrawide ratio. The other ratios (`1:1`, `16:9`, `9:16`, `4:3`, `3:4`) all work. An unsupported combo is rejected up front with a clear error before the job is queued — nothing is silently downscaled.

Example MCP config with the Foundry transport:

```json
{
  "mcpServers": {
    "etch": {
      "command": "uvx",
      "args": ["--from", "/path/to/etch", "etch"],
      "env": {
        "GOOGLE_API_KEY": "your_google_api_key_here",
        "MAI_API_KEY": "your_mai_api_key_here",
        "MAI_ENDPOINT": "https://<resource>.services.ai.azure.com",
        "MAI_DEPLOYMENT": "MAI-Image-2.5"
      }
    }
  }
}
```

#### OpenRouter (no Azure)

Prefer not to stand up a Foundry resource? Route MAI through [OpenRouter](https://openrouter.ai/microsoft/mai-image-2.5) — one API key, no Azure. Set `MAI_TRANSPORT=openrouter` and supply an `OPENROUTER_API_KEY`; the Foundry vars above are not needed.

| Variable | Required | Notes |
|-|-|-|
| `MAI_TRANSPORT` | yes | Set to `openrouter` (default is `foundry`). |
| `OPENROUTER_API_KEY` | yes | Your OpenRouter key (`sk-or-...`). |
| `MAI_OPENROUTER_MODEL` | no | Model slug; defaults to `microsoft/mai-image-2.5`. |
| `OPENROUTER_URL` | no | Override the endpoint (e.g. a gateway/proxy); defaults to OpenRouter's. |

```json
{
  "mcpServers": {
    "etch": {
      "command": "uvx",
      "args": ["--from", "/path/to/etch", "etch"],
      "env": {
        "GOOGLE_API_KEY": "your_google_api_key_here",
        "MAI_TRANSPORT": "openrouter",
        "OPENROUTER_API_KEY": "sk-or-..."
      }
    }
  }
}
```

Same capability surface as Foundry (1K only, no 21:9). Under the hood etch sends an OpenRouter chat-completions request with `modalities: ["image"]` (MAI is image-output-only) and an `image_config` aspect ratio, then decodes the returned base64 image.

## Verify

Ask your agent: *"etch a diagram of three boxes connected by arrows."* If etch is wired up, the agent will get back a `job_id`, then ~30–60s later a saved PNG path.

## Skill (optional but recommended)

The `etch` skill at `skills/etch/SKILL.md` adds audience-aware diagram generation — optional, but recommended if you want diagrams tailored to specific personas (architect, exec, end user, runbook reader, etc.) without rewriting the prompt each time. If your agent has a skills directory, point it at `skills/etch/` (or symlink it in). The skill activates on requests like *"diagram of the auth service for a runbook"* and chooses the right audience prose automatically.

## Troubleshooting

- **Tool not visible after editing config.** Restart your agent fully — many MCP clients only read config at startup.
- **`GOOGLE_API_KEY environment variable is not set`.** The key has to live in the `env` block of the MCP config. The MCP server inherits the agent's env, not your shell's.
- **`MAI_API_KEY environment variable is not set` / `MAI_ENDPOINT is not configured`.** Selecting `model="mai-image-2.5"` requires both in the `env` block (`MAI_ENDPOINT` is the `https://<resource>.services.ai.azure.com` base). A missing `MAI_API_KEY` fails fast before the job is queued; a missing `MAI_ENDPOINT` surfaces as a failed job (check `check_job_status`).
- **`OPENROUTER_API_KEY environment variable is not set`.** With `MAI_TRANSPORT=openrouter`, etch resolves the OpenRouter key instead of the Foundry vars — set `OPENROUTER_API_KEY` (`sk-or-...`) in the `env` block.
- **`mai-image-2.5 does not support ... 2K`/`21:9`.** MAI is 1K-only and has no ultrawide ratio. Use `resolution="1K"` and a non-ultrawide aspect (`1:1`, `16:9`, `9:16`, `4:3`, `3:4`), or switch back to the default Gemini model for 2K/`21:9`.
- **Generation fails.** Check `check_job_status(job_id)` for the failure reason. Most failures are upstream (Gemini quota or content policy); retry with a tighter description.
