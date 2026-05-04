# etch

![etch](images/etch.png)

Etch your codebase into a printable diagram. An MCP server that turns code and architecture descriptions into PNGs using Google's Nano Banana Pro (Gemini 3 Pro Image).

## Setup

Install [uv](https://docs.astral.sh/uv/) (`uv` ships `uvx`). Get a Google AI Studio API key at https://aistudio.google.com/. Then add etch to your MCP client config — for example Claude Desktop's `claude_desktop_config.json`:

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

`uvx` builds an isolated env on first launch and caches it; no manual `pip install` step. Swap `--from /path/to/etch` for `--from git+https://github.com/<owner>/etch` to install from git instead.

## Tools

Generation is async to stay within MCP client tool-call timeouts:

- `start_diagram_job(description, aspect_ratio="16:9", resolution="2K", output_dir=None)` — kicks off generation, returns a `job_id` immediately.
- `check_job_status(job_id)` — poll every ~10s. Returns `queued (Xs)`, `generating (Xs)`, `complete (Xs) — saved to <path>`, or `failed (Xs): <reason>`.

`aspect_ratio` ∈ `{1:1, 16:9, 9:16, 4:3, 3:4, 21:9}`. `resolution` ∈ `{1K, 2K}`. Generation typically takes 30–60s. The PNG is written to `output_dir` (default cwd); the server and client must share a filesystem.

## Architecture

![etch architecture](images/etch_architecture.png)

## Example

![LangGraph Architecture](images/langgraph_architecture_learning_card.png)

Generated from a prompt asking for a printable LangGraph architecture learning card with sections for core components, the StateGraph workflow, Pregel-inspired execution, checkpointing, monorepo layout, and capabilities.
