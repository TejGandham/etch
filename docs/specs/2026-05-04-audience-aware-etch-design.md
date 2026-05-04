# Audience-aware diagram generation for etch

**Status:** design approved, ready for implementation plan
**Date:** 2026-05-04

## Problem

`etch.start_diagram_job` accepts a description and image-shape parameters, then hands the description verbatim to Gemini 3 Pro Image. The same description produces the same diagram regardless of who will read it. An "auth system" diagram for a developer onboarding doc, a security architect, a product manager prioritizing work, and an exec slide are four different diagrams — but the MCP has no way to express that, so callers have to bake audience cues into the description prose, which is unreliable and not portable across callers.

## Goal

Make audience a first-class input to diagram generation, while keeping the MCP server thin and stable. Move the "what does it mean to draw for audience X" knowledge into a Claude skill that ships alongside the MCP, so the same MCP can serve future skills (or different clients) without growing audience opinions of its own.

## Non-goals

- Composing the description itself. The skill assumes the user (or upstream brainstorming) has produced one. Skill scope is audience + canvas, not full diagram brief.
- Per-audience visual style enums or color palettes baked into the MCP. Anything stylistic the model needs to know rides in the audience string.
- Multi-audience blending. One diagram, one audience.
- Server-side persistence of audience presets. Each call is independent.

## Architecture

Two artifacts in the same repo, with a clean responsibility split:

```
┌───────────────────────────────────────────────────────────────────┐
│  Skill: etch (lives in this repo, ships with the MCP)             │
│                                                                   │
│  • Description-triggered: activates on codebase/architecture-     │
│    diagram requests.                                              │
│  • Owns: audience inference, audience interview, audience         │
│    guidance authoring, aspect_ratio + resolution derivation.      │
│  • Knows: 6 curated audience anchors, ~5-line guidance blocks     │
│    each. Off-list audiences get on-the-fly guidance from context. │
│                                                                   │
└───────────────────────────────┬───────────────────────────────────┘
                                │  start_diagram_job(
                                │     description, audience=<str>,
                                │     aspect_ratio, resolution)
                                ▼
┌───────────────────────────────────────────────────────────────────┐
│  MCP: etch.py (one new optional param, one prompt-prefix block)   │
│                                                                   │
│  • If audience present, prefix description with a small frame.    │
│  • Otherwise behaves exactly as today.                            │
│  • No per-audience templates server-side; the skill writes them.  │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

Why this split:

- The skill is the natural home for reasoning. It can read conversation context, ask the user, and revise.
- The MCP is a thin tool. Keeping audience opinions out of it means the server stays stable as the skill iterates, and other clients can call it without buying into this audience model.
- Future skills (or a different audience model) can drop in without an MCP version bump.

## MCP changes

`etch.py` gains a single optional parameter on `start_diagram_job`:

```python
@mcp.tool()
def start_diagram_job(
    description: str,
    aspect_ratio: str = "16:9",
    resolution: str = "2K",
    output_dir: Optional[str] = None,
    audience: Optional[str] = None,   # NEW
) -> str:
    ...
```

When `audience` is non-empty (after `strip()`), the description handed to Gemini gets wrapped in a small frame:

```
[Target audience]
{audience}
Tailor abstraction level, vocabulary, what to emphasize, what to omit,
and visual register to suit this audience.

[Diagram]
{description}
```

When `audience` is `None`, empty, or whitespace, the prompt sent to Gemini is byte-identical to today's behavior. This is the backward-compatibility guarantee.

**Validation rules:**
- `audience` is stripped on entry; whitespace-only is treated as `None`.
- Length cap: ~4000 characters. Reject longer with a clear error.
- No enum, no allowlist. The skill is the curator.

`check_job_status` is unchanged. No new tools.

## Skill design

### Activation

Description-triggered, but **narrowly**. The skill activates in exactly two cases:

1. The user explicitly invokes etch by name ("use etch to …", "etch a diagram of …").
2. The user asks for a **technical diagram aimed at a specific audience** — meaning both halves are present in the request: it's a technical/architecture/codebase diagram, *and* there's an audience cue (explicit like "for the architect review" or "exec slide", or strongly implied like "for the runbook"). Generic "draw me a diagram" without an audience cue does not activate the skill.

The skill must NOT activate on: general drawing or sketching requests, whiteboard scribbles, illustration tasks, non-codebase diagrams (org charts, flowcharts unrelated to a system), or any diagram request that doesn't carry an audience signal.

The frontmatter `description` field is written to express exactly these triggers, with explicit "do not activate when …" examples to keep the boundary sharp.

### Flow

Six steps:

1. **Confirm a description exists.** If the user has not provided enough text for the model to draw from (e.g., "draw the auth system" with no follow-up detail), the skill asks the user to supply a fuller description in their own words. The skill does not drive a brainstorming or composition workflow over what the diagram should contain — that's outside scope and belongs to the brainstorming skill or the user's own writing. The skill simply refuses to proceed until it has a description to forward.

2. **Infer audience from context.** Signals the skill consults:
   - Explicit audience mention in the user's message ("for execs", "for the runbook").
   - Output destination if mentioned ("for the README", "for the deck Friday", "to pin in the war room").
   - Recent files and conversation context.
   - Vocabulary and abstraction level in the description itself (a description full of class names and APIs hints at developer; a description full of capabilities hints at PM).

3. **Infer canvas (aspect_ratio / resolution) from the same signals.** See the canvas table below.

4. **Branch on inference confidence:**
   - **Confident:** announce + proceed. The skill states what it inferred, what canvas it picked, and fires the call. Example:
     > Reading this as ops/SRE for a runbook print — 3:4, 2K. Generating now…

     The user can interrupt mid-generation if the inference is wrong; cost of being wrong is one regenerate, which is cheap.
   - **Not confident:** single multi-choice interview (see below), then announce + proceed once the user picks.

5. **Build the audience guidance string.**
   - If the inferred or selected audience matches one of the six anchors, embed that anchor's curated guidance block verbatim.
   - Otherwise, write a short (3–5 line) guidance block on the fly using the same structure (emphasize / de-emphasize / visual register).

6. **Call `start_diagram_job`** with the description, the constructed `audience` string, and the inferred canvas. Poll `check_job_status` until complete or failed; report the result path to the user.

The skill makes one inference attempt and at most one interview. It does not re-ask. If the diagram comes back wrong, the user redirects on the next turn and the skill regenerates with the correction.

### Inference confidence — what counts as "confident enough"

Soft threshold, judged by the skill in context. Confidence is high when at least one direct signal is present:
- Explicit audience word in user request ("for developers", "exec slide").
- Explicit output destination that maps cleanly to one anchor ("README" → developer; "runbook" → ops; "board deck" → executive).
- A description vocabulary that strongly clusters around one anchor (e.g., method names + class names + interface boundaries → developer).

Confidence is low when none of the above are present and the request is generic ("draw a diagram of the system"). In that case, the skill interviews.

### The six audience anchors

Each anchor materializes in the skill as a ~5-line prose block, summarized here:

| Anchor | Emphasize | De-emphasize | Visual register |
|-|-|-|-|
| **Architect** | Boundaries, layers, deployment topology, integration seams | Code-level detail, intra-module structure | Whiteboard / blueprint, technical jargon OK |
| **Developer** | Modules, data flow, API surfaces, key types, sequence flows | Business framing, exec-level abstraction | Clean technical illustration, precise terminology |
| **Product manager** | Feature/capability map, user journeys, value labels, integration points (only as needed for prioritization) | Code references, infra detail | Presentation-clean, plainspoken |
| **End user** | What-it-does view, journey/flow, plain language, friendly icons | Anything labeled "system", architecture decomposition | Illustrated, friendly palette, jargon-free |
| **Executive** | Single big-picture view, business outcomes, relationships | Components, technical labels, anything requiring zoom | Bold minimalist, one-glance comprehension |
| **Ops / SRE** | Runtime topology, failure modes, observability hooks, escalation paths, datastore + queue topology, ports/protocols | Build-time concerns, source layout | Reference-document, runbook-print friendly |

The skill stores the full prose form of each anchor as part of its content. The full prose is what gets sent to the MCP via the `audience` parameter — the table above is just a summary for the spec.

### Off-list audiences

When the user picks `G. Other (describe)` from the interview or when the skill infers an off-list audience from context (e.g., "security reviewer prepping for a pen test"), the skill writes a short guidance block on the fly using the same emphasize / de-emphasize / register structure. No fallback to a generic anchor — the skill reasons from the context.

### Interview format

When inference fails, single message, multiple choice:

```
Who's this diagram for? Quick pick:
  A. Architect — boundaries, layers, deployment
  B. Developer — modules, data flow, APIs
  C. Product manager — features, journeys, value
  D. End user — what-it-does, plain language
  E. Executive / stakeholder — big picture, business outcomes
  F. Ops / SRE — runtime, failure modes, runbook-friendly
  G. Other (describe)
```

Never multi-step. The skill commits as soon as the user answers.

### Canvas inference

| Signal in context | aspect_ratio | resolution |
|-|-|-|
| README, blog post, slide deck, "presentation" | 16:9 | 2K |
| Poster, print, "pin it up", "wall" | 3:4 | 2K |
| Banner, header, "wide", "panoramic" | 21:9 | 2K |
| Mobile, social card, "share" | 9:16 or 1:1 | 2K |
| "Quick draft", "rough", explicit speed signal | (keep above) | 1K |
| Nothing detectable | 16:9 | 2K |

User-provided `aspect_ratio` / `resolution` always win over inference. The skill never overrides an explicit choice.

## Data flow (single call)

```
User → Claude (with skill loaded)
  Skill: read context, infer (audience, aspect_ratio, resolution)
  Skill: [if needed] interview user, get audience pick
  Skill: build audience prose block (anchor or on-the-fly)
  Skill: announce decisions to user

Claude → MCP (start_diagram_job)
  description, audience=<prose block>, aspect_ratio, resolution

MCP: prefix description with audience frame, send to Gemini
MCP: return job_id

Claude → MCP (check_job_status, polling)
MCP: return progress / final path

Claude → User: "Generated for <audience>, <ratio> <res> — saved to <path>"
```

## Error handling

- **No `GOOGLE_API_KEY`:** unchanged from today — `start_diagram_job` raises, skill surfaces the error to the user.
- **`audience` over length cap:** MCP raises `ValueError`. In practice this should not fire — curated anchor blocks are well under 500 chars and on-the-fly blocks follow the same shape. The cap exists to prevent prompt-bloat accidents, not as a routine retry path. If it does fire, the skill surfaces the error to the user; no automatic retry.
- **Generation fails (Gemini error, no candidates, etc.):** unchanged; `check_job_status` returns `failed (Xs): <reason>`, skill surfaces verbatim.
- **User redirects mid-flow** ("no, this is for end users, not architects"): skill restarts the call with the corrected audience. No state to clean up — each call is independent.

## Testing

**MCP changes — small, well-bounded:**
- `audience=None` produces a prompt byte-identical to today (regression guard).
- `audience="…"` injects the framed block correctly.
- `audience="   "` is treated as `None`.
- Audience over the length cap raises `ValueError` with a clear message.

**Skill — prose, evaluated by use:**
- Manual test matrix: one diagram per anchor on a real codebase, eyeball the result.
- One off-list audience generation, eyeball the on-the-fly guidance block.
- One interview-triggering request, confirm the multi-choice prompt fires.
- One canvas-inference case per row of the canvas table.

## Out of scope (for the next sub-project, if desired)

- Composing the description itself (full diagram brief).
- Multi-audience blending or comparison diagrams.
- Caching audience guidance blocks server-side or persisting per-project audience defaults.
- Visual style controls beyond what the audience prose conveys (no `style="blueprint"` enum).
