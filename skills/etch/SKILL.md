---
name: etch
description: Use ONLY when the user asks for a technical/codebase/architecture diagram aimed at a specific audience (e.g., "diagram for the architects", "exec slide of our system", "runbook diagram of the auth service"), or when they explicitly invoke etch by name ("use etch", "etch a diagram"). Both halves are required for implicit activation: a technical/system diagram AND an audience cue. Do NOT activate for generic drawing requests without an audience signal, whiteboard sketches, illustration tasks, org charts, non-codebase flowcharts, or any drawing task that is not specifically a system/codebase/architecture diagram.
---

# etch — audience-aware diagrams

Generate codebase and architecture diagrams that are tailored to a specific reader: an architect, a developer onboarding, a product manager, an end user, an executive, or an SRE. The skill picks the audience (by inference from context, or by a single quick interview when context is too thin), picks the canvas shape and resolution from context, and calls the etch MCP server with a rich audience-guidance string the model uses to steer abstraction, vocabulary, and visual register.

## When to use this skill

Activate when:

1. The user explicitly invokes etch by name.
2. The user asks for a technical or system diagram **and** there is an audience cue in the request — explicit ("for the architects", "exec slide") or strongly implied ("for the runbook" → ops/SRE; "for the README" → developer; "board deck" → executive).

Do NOT activate when:

- The user asks for a generic "diagram" with no audience signal — that's a job for plain `start_diagram_job`, not this skill.
- The user wants a whiteboard sketch, freeform illustration, org chart, or flowchart of a non-system process.
- The user is brainstorming what to put in a diagram (that's brainstorming, not generation). If they need help composing the description itself, exit this skill and use the brainstorming skill or have them write the description by hand.

## Flow

The skill makes one inference attempt and at most one interview, then commits. It does not re-ask. If the diagram comes back wrong, the user redirects on the next turn and the skill regenerates with the correction.

1. **Confirm a description exists.** If the user has not provided enough text for the model to draw from (e.g., "draw the auth system" with no further detail), ask the user to supply a fuller description in their own words. Do not drive a brainstorming workflow over what the diagram should contain — refuse to proceed until you have a description to forward.

2. **Infer audience from context.** Read these signals:
   - Explicit audience mention in the user's message ("for execs", "for the runbook").
   - Output destination if mentioned ("for the README", "for the deck Friday", "to pin in the war room").
   - Recent files and conversation context.
   - Vocabulary and abstraction level in the description itself: class names + method names + interface boundaries → developer; capabilities + journeys → product manager; runtime + topology + datastores → ops/SRE; and so on.

3. **Infer canvas (`aspect_ratio` and `resolution`) from the same signals** (see Canvas inference table below).

4. **Branch on inference confidence:**
   - **Confident** (at least one direct signal present): announce the inferred audience and canvas, then fire the call. Example: `Reading this as ops/SRE for a runbook print — 3:4, 2K. Generating now…`
   - **Not confident** (request is generic, "draw a diagram of the system" with no other signals): run the interview (see below), then announce + proceed once the user picks.

5. **Build the audience guidance string.**
   - If the inferred or selected audience matches one of the six anchors below, embed the anchor's prose block verbatim as the `audience` parameter.
   - For "Other (describe)" or off-list audiences, write a short (3–5 sentence) guidance block on the fly using the same shape: who the reader is, what to emphasize, what to suppress, what visual register fits.

6. **Call `start_diagram_job`** with the description, the audience prose, and the inferred canvas. Poll `check_job_status` every ~10 seconds until the job is `complete` or `failed`. Report the final path (or the failure reason) to the user.

## Inference confidence — what counts as confident

Confidence is **high** when at least one of these holds:
- An audience word is explicit in the user's request.
- An output destination maps cleanly to one anchor (README → developer; runbook → ops; board deck → executive; product spec → PM; user help → end user; architecture review → architect).
- The description's vocabulary clusters strongly around one anchor (e.g., method/class/API names → developer; revenue/customers → executive).

Confidence is **low** when none of the above are present and the request is generic. In that case, interview.

User-provided `aspect_ratio` or `resolution` always wins over inference. Never override an explicit choice.

## The six audience anchors

When the inferred or selected audience matches one of these six, embed the corresponding prose block **verbatim** as the `audience` parameter. The prose is engineered to steer Gemini's image model on abstraction, vocabulary, emphasis, and visual register; do not paraphrase.

### Architect

```
Reader is a software architect or staff/principal engineer evaluating system structure and integration. Show component boundaries, layered architecture (presentation/application/domain/data), deployment topology (services, regions, network zones), and integration seams between subsystems. Suppress code-level detail like class lists, method signatures, or inner module structure. Technical jargon is welcome — use precise terms (bounded context, anti-corruption layer, circuit breaker, blast radius) without softening. Visual register: clean blueprint or whiteboard-style architecture diagram, restrained palette, sharp lines, technical labels. The reader should be able to evaluate scaling, failure isolation, and team ownership boundaries at a glance.
```

### Developer

```
Reader is a software developer onboarding to or working in this codebase. Show modules and packages, the data flow between them, key API surfaces, important types and classes, and sequence flows for common operations. Include enough naming detail (file names, module names, function names where they carry meaning) that the reader can map the diagram to the source tree. Suppress business framing, exec-level abstraction, and feature-roadmap framing. Use precise technical terminology. Visual register: clean technical illustration with clear information hierarchy, restrained palette (one or two accent colors), labeled arrows, monospaced typography for code identifiers. The reader should be able to find the corresponding code within minutes.
```

### Product manager

```
Reader is a product manager or technical PM evaluating features, prioritization, and user-facing surface area. Show the feature and capability map, primary user journeys, value labels per area, and integration points only at the level needed to reason about scope and dependencies. Suppress code references, infrastructure detail, and protocol-level concerns. Use plainspoken language with the product's own feature names; avoid implementation jargon (replace "Postgres write replica lag" with "database sync"). Visual register: presentation-clean, slide-deck-friendly, one or two accent colors, generous whitespace, clear sectioning. The reader should be able to use the diagram to discuss priority, dependencies, and scope with peers.
```

### End user

```
Reader is an end user of the product — non-technical, interested in what the system does for them, not how it is built. Show a what-it-does view: the user's journey, plain-language descriptions of each step, friendly icons that suggest action (send, save, share, search). Suppress anything labeled "system", "service", "module", "API", architectural decomposition, and any internal jargon. Use everyday vocabulary. Visual register: illustrated, friendly palette (warm tones, soft edges), rounded shapes, jargon-free labels in a conversational tone. The reader should feel oriented and confident, not informed about implementation.
```

### Executive

```
Reader is a C-level executive, board member, or senior non-technical stakeholder making business decisions in 30 seconds. Show one big-picture view of the system at the level of business outcomes and major capability clusters; show how parts relate to revenue, customers, or strategic goals. Suppress all components, technical labels, and anything that requires zoom or close reading. Vocabulary should be the language of the business, not engineering. Visual register: bold and minimalist, large bold typography for major elements, two-color accent palette, single eye path. The reader should grasp the message in a single glance and use it as a slide in a board deck.
```

### Ops / SRE

```
Reader is an SRE, on-call engineer, or operations lead responsible for runtime health. Show runtime topology (services, datastores, queues, caches, load balancers), failure modes and their blast radius, observability hooks (where logs, metrics, and traces emit from), escalation paths (who pages when what fails), and protocol or port annotations on key edges. Suppress build-time concerns, source layout, and anything not relevant to a system running in production. Use precise operational terminology (p99 latency, leader election, DLQ depth, saturation). Visual register: reference-document style, suitable for printing and pinning near a workstation, monospace technical labels, clear color-coding for service tiers (critical-path vs. supporting), legend if useful. The reader should be able to use the diagram during an incident.
```
