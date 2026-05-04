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
