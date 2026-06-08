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

4. **Pick the house-style register** (see "Which register to use" above). If the signals favor one register cleanly, announce it. Otherwise present the binary choice to the user in one short line:

   ```
   Style: storybook (default — warm watercolor, matches existing brand assets) or enterprise stark (navy + brass, clean editorial)?
   ```

   Default to storybook if the user does not answer.

5. **Branch on inference confidence:**
   - **Confident** (at least one direct signal present): announce the inferred audience, register, and canvas, then fire the call. Example: `Reading this as ops/SRE for a runbook print, enterprise-stark register — 3:4, 2K. Generating now…`
   - **Not confident** (request is generic, "draw a diagram of the system" with no other signals): run the interview (see below) plus the register pick from step 4, then announce + proceed once the user picks.

6. **Build the audience guidance string.**
   - Prepend the chosen register's house-style block verbatim (storybook or enterprise stark — see "House style" section).
   - Then embed the audience anchor's prose block verbatim as the rest of the `audience` parameter.
   - For "Other (describe)" or off-list audiences, write a short (3–5 sentence) guidance block on the fly using the same shape: who the reader is, what to emphasize, what to suppress, what visual register fits.

7. **Call `start_diagram_job`** with the description, the audience prose (register + anchor), and the inferred canvas. Poll `check_job_status` every ~10 seconds until the job is `complete` or `failed`. Report the final path (or the failure reason) to the user.

## Inference confidence — what counts as confident

Confidence is **high** when at least one of these holds:
- An audience word is explicit in the user's request.
- An output destination maps cleanly to one anchor (README → developer; runbook → ops; board deck → executive; product spec → PM; user help → end user; architecture review → architect).
- The description's vocabulary clusters strongly around one anchor (e.g., method/class/API names → developer; revenue/customers → executive).

Confidence is **low** when none of the above are present and the request is generic. In that case, interview.

User-provided `aspect_ratio` or `resolution` always wins over inference. Never override an explicit choice.

## House style — pick one per image

Two house-style registers are supported. Exactly one is prepended to every `audience` parameter (alongside the per-audience anchor). They give different visual feels and target different output contexts. **The default is storybook** unless the user picks otherwise.

### Storybook (default — warm illustrated)

The original etch register. Use for friendly developer-tool branding, marketing/hero imagery, user-journey illustrations, README artwork, anything where warmth and character matter more than corporate restraint. Matches the existing etch brand assets in `images/` (mascot, user-journey illustration, example diagrams). The full prose, sent verbatim:

```
House style — applies to every etch image regardless of audience:
- Background: warm cream or soft off-white. Never pure white. Subtle paper grain is welcome; sterile digital flatness is not.
- Lines and text: soft charcoal. Never pure #000. Allow gentle line-weight variation (medium for primary forms, thinner for secondary detail).
- Palette: warm and intentional — golden yellows, fresh greens, calm sky and soft navy blues, coral and peach oranges, warm grays, soft browns. Avoid neon, cold harsh tones, garish saturation, and clashing combinations.
- Framing: NO frame, border, or edge decoration. The image IS the artifact, not a photo of one. Content extends fully to the edges.
- Color application: watercolor-like washes with slight transparency; colors may very slightly escape line boundaries to register as hand-applied rather than vector-perfect.
- Typography: warm and readable, never sharp/sterile. Headings can carry a hand-lettered feel; body text stays clean.
- Avoid: corporate clip-art aesthetics, drop shadow around the whole image as if it's a photo, sterile vector perfection, rigid mechanical grid alignment, uniform line weights everywhere.
```

### Enterprise stark (alternate — clean editorial)

Use when the reader expects a serious authored technical document and the watercolor register would feel unprofessional: enterprise architecture reviews, board decks, runbook references, security review artifacts, B2B platform documentation. Trades warmth for the polish of a high-end engineering publication. The full prose, sent verbatim:

```
House style — applies to every etch image regardless of audience:

Visual register: editorial technical illustration. Reference quality: Increment Magazine technical articles, Stripe Press book interior diagrams, "Designing Data-Intensive Applications", Distill.pub. Authored and opinionated. NOT watercolor / storybook / hand-drawn / paper-grain. NOT flat-corporate / clinical / sterile / PowerPoint-default.

- Background: warm off-white / pale cream (~#F4EFE6). Never pure white. No paper texture or grain.
- Lines and primary type: deep ink near-black (~#0E1726). Crisp uniform-weight strokes. No hand-drawn wobble, no watercolor bleed, no color escaping outside line boundaries.
- Shapes: precise rectangles with subtle 4–6px rounded corners. Geometry is sharp.
- Palette (navy-dominant with one warm focal accent — classic-confident, reads as a serious authored technical document):
  - Lane / section header blocks: navy tones varying in depth — deepest navy (~#0F2347), mid navy (~#243E66), dusty indigo (~#4F6691). Cream-on-color labels.
  - Signature accent (used on the most important boundary or focal element, on key identifier highlights, and on focal markers like a star or dot on a critical arrow): warm brass / antique gold (~#B68B3E). The SINGLE warm color in an otherwise cool composition. Classic navy + brass pairing — reads expensive and confident.
  - Module-card interiors: pale cream, ink-navy labels.
- Typography: characterful modern sans (Söhne, GT America, Inter Display feel) for headings and labels; monospaced (JetBrains Mono, IBM Plex Mono feel) for code identifiers, file paths, endpoints, model names, and any text representing literal source. Strong size hierarchy — section titles much larger than body labels.
- Framing: NO frame, border, or edge decoration. The image IS the artifact, not a photo of one. Content extends fully to the edges.
- One expressive design moment per diagram: the focal element (often an external system boundary, an AI call, or the inciting action) gets a subtle halftone or stippled fill in the brass accent AND a brass border — making the focal point visually unmistakable. Just that one element gets the special treatment.
- Negative space: confident. Don't pack wall-to-wall. Let the major regions breathe.
- Avoid absolutely: watercolor, painterly washes, color bleed outside lines, hand-lettering, paper grain, storybook illustration AESTHETIC AND grayscale corporate, drab safe palette, uniform type sizing, sterile flat clinical register, "PowerPoint default" look, decorative flourishes that aren't structural.
```

### Which register to use

- **Storybook** when: the project has illustrated brand assets the image needs to match; the request is a hero, landing-page, or marketing image; the audience is the End user anchor; the user asks for something "warm", "friendly", "illustrated", or "playful".
- **Enterprise stark** when: the user explicitly asks for "enterprise", "stark", "professional", "boardroom", "B2B", or "serious"; the destination is a board deck, an executive review, a security review, or a B2B platform doc; the existing project artifacts read as enterprise/financial-services rather than indie/illustrated.
- **Otherwise** (genuinely ambiguous): present the choice. See Flow step 4 below.

The per-audience anchor still layers on top of whichever register is chosen. Where an anchor specifies a register that conflicts with the chosen house style (for example, the End user anchor's warm friendly tones overriding navy-dominance), the audience anchor wins for that conflict and the house-style elements that don't conflict still apply.

## The six audience anchors

When the inferred or selected audience matches one of these six, embed the chosen register's house-style block (storybook or enterprise stark — see Flow step 4) followed by the corresponding anchor prose **verbatim** as the `audience` parameter. The prose is engineered to steer Gemini's image model on abstraction, vocabulary, emphasis, and visual register; do not paraphrase.

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

## Canvas inference

| Signal in context | aspect_ratio | resolution |
|-|-|-|
| README, blog post, slide deck, "presentation" | 16:9 | 2K |
| Poster, print, "pin it up", "wall" | 3:4 | 2K |
| Banner, header, "wide", "panoramic" | 21:9 | 2K |
| Mobile, social card, "share" | 9:16 (portrait emphasis) or 1:1 | 2K |
| "Quick draft", "rough", explicit speed signal | (keep above ratio) | 1K |
| Nothing detectable | 16:9 | 2K |

User-provided `aspect_ratio` / `resolution` always win over inference.

## Interview format (only when audience inference fails)

Send a single message, multiple choice. Never multi-step:

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

A–F map to the six anchor prose blocks above. G triggers the on-the-fly path: write a 3–5 sentence guidance block matching the structure (who the reader is → what to emphasize → what to suppress → visual register), then proceed.

## Calling the MCP

The etch MCP exposes two tools:

- `start_diagram_job(description, aspect_ratio="16:9", resolution="2K", output_dir=None, audience=None, model="gemini-3-pro-image-preview")` — returns a `job_id` immediately.
- `check_job_status(job_id)` — poll every ~10s. Returns `queued (Xs)`, `generating (Xs)`, `complete (Xs) — saved to <path>`, or `failed (Xs): <reason>`.

Pass the full audience prose block (verbatim from the anchor list, or your on-the-fly block) as the `audience` argument. Pass the description the user wrote — do NOT modify it. Pass the inferred (or user-specified) `aspect_ratio` and `resolution`.

By default, omit `model` — etch uses Google Gemini, which supports the full canvas matrix above (every ratio, 1K and 2K). Only if the user explicitly asks for MAI-Image-2.5, pass `model="mai-image-2.5"` AND constrain the canvas to `1K` and a non-`21:9` ratio. MAI cannot produce 2K or 21:9, so those combos are rejected before the job is queued; pick the closest supported ratio (1:1, 16:9, 9:16, 4:3, or 3:4) at 1K.

After dispatching the job, poll `check_job_status` every ~10 seconds. Generation typically takes 30–60s. Surface the final result line to the user: either `Generated for <audience-name>, <ratio> <res> — saved to <path>`, or the failure reason verbatim.

## What this skill does NOT do

- Compose or edit the description itself. The user (or the brainstorming skill) supplies it.
- Multi-audience or comparison diagrams. One diagram, one audience.
- Any caching or persistence of audience choices across calls. Each invocation is independent.
- Style controls beyond what the audience prose conveys (no `style="blueprint"` knob — register is in the prose).
