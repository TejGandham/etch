# How etch works

![etch architecture](images/etch_architecture.png)

Under the hood, etch is a thin MCP server wrapping Google's Gemini 3 Pro Image (Nano Banana Pro). When your agent calls `start_diagram_job`, the server kicks off generation on a background thread, returns a `job_id` immediately, and lets the agent poll `check_job_status` until the PNG lands on disk. The async split exists so MCP tool-call timeouts don't bite — generation typically runs 30–60 seconds.

The audience-aware part lives in the skill at `skills/etch/SKILL.md`, not in the server. The skill reads the conversation, picks an audience (architect, developer, product manager, end user, executive, ops/SRE — or anything else describable), picks the canvas shape, and expands the choice into a curated prose block. That prose flows into the MCP via the `audience` parameter, which the server wraps with a small frame and forwards to the model verbatim. The server itself has no per-audience opinions; the skill carries them all. Different clients (or future skills with a different audience model) can call the same server without buying into this one.

For the full design rationale, see [`docs/specs/2026-05-04-audience-aware-etch-design.md`](docs/specs/2026-05-04-audience-aware-etch-design.md). For the implementation plan that built it, see [`docs/plans/2026-05-04-audience-aware-etch.md`](docs/plans/2026-05-04-audience-aware-etch.md).
