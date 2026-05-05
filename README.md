<p align="center">
  <img src="images/etch_logo.png" alt="etch" width="180" />
</p>

# etch

Etch your codebase into a printable diagram, tailored to whoever needs to see it.

The same description of a single-page app's login-to-dashboard journey, etched for three audiences:

| Developer | Product manager | End user |
|-|-|-|
| ![Developer view: technical sequence with components, REST calls, JWT, and JSON payloads](images/etch_example_developer.png) | ![Product manager view: four-stage feature and capability map with value labels](images/etch_example_pm.png) | ![End user view: illustrated four-step onboarding poster, jargon-free](images/etch_example_end_user.png) |

Same description in. Whichever diagram each audience needs out.

## Why etch

Diagrams are scarce in your docs because drawing them is slow. Worse, the same system needs to look one way in a runbook, another in an exec deck, and a third in onboarding — so the cost compounds. etch generates whichever version you need, from one description, in 30–60 seconds.

It runs as an MCP server, so it plugs into any MCP-aware agent. Generation runs through Google's Nano Banana Pro (Gemini 3 Pro Image).

## Who it is for

- People who want a diagram and don't want to draw it.
- People who want the same system shown several different ways for several different rooms.
- Anyone whose READMEs, runbooks, slide decks, and onboarding docs feel undersupplied with diagrams.

## Quick start

Add etch to your MCP client config (Claude Desktop's `claude_desktop_config.json`, or equivalent):

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

Restart your agent, then try: *"etch a diagram of three boxes connected by arrows."* You'll get back a `job_id`, then ~30–60s later a saved PNG.

For the long version (uv install, alternative install paths, troubleshooting), see [`install.md`](install.md).

## Tools

Generation is async to stay within MCP client tool-call timeouts:

- `start_diagram_job(description, aspect_ratio="16:9", resolution="2K", output_dir=None, audience=None)` — kicks off generation, returns a `job_id` immediately. When `audience` is provided (free-form string up to 4000 chars), etch wraps your description with instructions to tailor abstraction, vocabulary, emphasis, and visual register to that audience. When `audience` is `None` or empty, the prompt is byte-identical to the no-audience case.
- `check_job_status(job_id)` — poll every ~10s. Returns `queued (Xs)`, `generating (Xs)`, `complete (Xs) — saved to <path>`, or `failed (Xs): <reason>`.

`aspect_ratio` ∈ `{1:1, 16:9, 9:16, 4:3, 3:4, 21:9}`. `resolution` ∈ `{1K, 2K}`. The PNG is written to `output_dir` (default cwd); the server and client must share a filesystem.

## Audience-aware mode (Claude Code)

If you use Claude Code, the bundled skill at `skills/etch/SKILL.md` picks the audience from context — when you ask for a "diagram of the auth service for the runbook" or "an exec slide of the system", it infers the audience and shapes the prompt for you. Without the skill, pass `audience` to `start_diagram_job` directly.

The MCP itself is audience-agnostic; the skill carries the per-audience guidance, so different clients (or future skills) can call the MCP without buying into this audience model.

## How it works

The short version is in [`how-it-works.md`](how-it-works.md): how the MCP server, the audience-aware skill, and Gemini 3 Pro Image fit together, plus links to the full design and implementation plan.
