# etch

![how etch works for you](images/etch_user_journey.png)

Etch your codebase into a printable diagram, tailored to whoever needs to see it.

## What it does

Hand etch a description of a system — a service, a feature, your whole codebase — and it produces a polished diagram as a PNG. The diagram is shaped for the audience you have in mind: an architect needs different things from an executive, and a developer onboarding needs different things from an end user. etch handles that shaping for you.

It runs as an MCP server, so it plugs into any MCP-aware agent. Generation runs through Google's Nano Banana Pro (Gemini 3 Pro Image), typically 30–60s per diagram.

## Who it is for

- People who want a diagram and don't want to draw it.
- People who want the same system shown several different ways for several different rooms.
- Anyone whose READMEs, runbooks, slide decks, and onboarding docs feel undersupplied with diagrams.

## How to install

Just point your agent at this repo for install. See [`install.md`](install.md) for the full walkthrough.

## Tools

Generation is async to stay within MCP client tool-call timeouts:

- `start_diagram_job(description, aspect_ratio="16:9", resolution="2K", output_dir=None, audience=None)` — kicks off generation, returns a `job_id` immediately. When `audience` is provided (free-form string up to 4000 chars), the description is wrapped with a frame instructing the model to tailor abstraction, vocabulary, emphasis, and visual register to that audience. When `audience` is `None` or empty, the prompt is byte-identical to the no-audience case.
- `check_job_status(job_id)` — poll every ~10s. Returns `queued (Xs)`, `generating (Xs)`, `complete (Xs) — saved to <path>`, or `failed (Xs): <reason>`.

`aspect_ratio` ∈ `{1:1, 16:9, 9:16, 4:3, 3:4, 21:9}`. `resolution` ∈ `{1K, 2K}`. The PNG is written to `output_dir` (default cwd); the server and client must share a filesystem.

## Skill

For audience-aware generation from inside Claude Code, this repo ships an `etch` skill at `skills/etch/SKILL.md`. The skill activates when you ask for a technical or architecture diagram aimed at a specific audience (architect, developer, PM, end user, executive, ops/SRE, or anything else describable), infers the audience and canvas shape from context, runs a single multi-choice interview only when context is too thin, and calls the MCP with a rich `audience` prose block. The MCP itself is audience-agnostic — the skill carries the per-audience guidance, which means future skills (or different clients) can call the MCP without buying into this audience model.

## How it works

The short version is in [`how-it-works.md`](how-it-works.md): how the MCP server, the audience-aware skill, and Gemini 3 Pro Image fit together, plus links to the full design and implementation plan.
