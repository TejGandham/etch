# Audience-aware diagram generation — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make audience a first-class input to etch's diagram generation by adding a thin `audience` parameter to the MCP and shipping a Claude skill that authors per-audience guidance.

**Architecture:** Skill carries the reasoning (audience inference, interview, prose authoring, canvas inference); MCP gains exactly one optional parameter and a small prompt-prefix block. See `docs/specs/2026-05-04-audience-aware-etch-design.md` for the full design.

**Tech Stack:** Python 3.11+, FastMCP, google-genai, pytest (new dev dep), Claude Code skill markdown.

---

## File structure

**Created:**
- `tests/__init__.py` — empty marker
- `tests/test_etch.py` — pytest test cases for prompt construction and audience validation
- `skills/etch/SKILL.md` — the user-facing skill

**Modified:**
- `etch.py` — add `audience` parameter, prompt-construction helper, validation
- `pyproject.toml` — add `pytest` as dev dependency
- `README.md` — document the new parameter and reference the skill

The MCP changes are tightly bounded: one new optional parameter, one helper function for prompt construction, four lightweight tests. The skill is markdown content with no executable code; correctness is evaluated by manual use, not unit tests.

---

## Task 1: Add pytest dev dependency and test scaffolding

**Files:**
- Modify: `pyproject.toml` (add dev dependency group)
- Create: `tests/__init__.py`
- Create: `tests/test_etch.py` (placeholder structure)

- [ ] **Step 1: Add pytest to pyproject.toml**

Add the dev dependency group to `pyproject.toml` after the `[project]` table:

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
]
```

- [ ] **Step 2: Create empty test package marker**

Create `tests/__init__.py` as an empty file:

```python
```

(File is intentionally empty.)

- [ ] **Step 3: Create test file scaffold**

Create `tests/test_etch.py`:

```python
"""Tests for etch.py — prompt construction and audience validation."""

import pytest

import etch
```

(`pytest` is imported now even though it's unused until Task 4 — keeping all test-file imports at the top is cleaner than adding one mid-file later.)

- [ ] **Step 4: Verify pytest runs and discovers no tests**

Run: `pytest tests/ -v`
Expected: `no tests ran` (or `collected 0 items`), exit code 5 (pytest's "no tests collected" code) or 0. Either is acceptable; we just want pytest to load the file without error.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/__init__.py tests/test_etch.py
git -c user.name='TejGandham' -c user.email='TejGandham@users.noreply.github.com' commit -m "test: scaffold pytest dev dep and tests/ directory"
```

---

## Task 2: Test that audience=None preserves byte-identical prompt

**Files:**
- Modify: `tests/test_etch.py` (add test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_etch.py`:

```python
def test_build_prompt_without_audience_returns_description_unchanged():
    """Backward-compat: audience=None must produce a prompt identical to today's."""
    description = "Architecture diagram with three services and a database."
    assert etch._build_prompt(description, None) == description


def test_build_prompt_treats_empty_audience_as_none():
    """Empty string audience behaves like None."""
    description = "Some description."
    assert etch._build_prompt(description, "") == description


def test_build_prompt_treats_whitespace_audience_as_none():
    """Whitespace-only audience behaves like None."""
    description = "Some description."
    assert etch._build_prompt(description, "   \n\t  ") == description
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_etch.py -v`
Expected: 3 failures with `AttributeError: module 'etch' has no attribute '_build_prompt'`.

- [ ] **Step 3: Implement `_build_prompt` for the no-audience case**

Add to `etch.py`, just after the constants block (before `_cleanup_jobs`):

```python
def _build_prompt(description: str, audience: Optional[str]) -> str:
    """Construct the prompt sent to the image model.

    When audience is None, empty, or whitespace-only, returns the description
    unchanged (byte-identical to the pre-audience behavior).
    """
    if audience is None or not audience.strip():
        return description
    # Audience-present branch implemented in Task 3.
    raise NotImplementedError("audience prompt frame implemented in Task 3")
```

- [ ] **Step 4: Run tests — first three should pass**

Run: `pytest tests/test_etch.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add etch.py tests/test_etch.py
git -c user.name='TejGandham' -c user.email='TejGandham@users.noreply.github.com' commit -m "feat(etch): add _build_prompt helper, no-audience path"
```

---

## Task 3: Test and implement the audience prompt frame

**Files:**
- Modify: `tests/test_etch.py` (add tests)
- Modify: `etch.py` (complete `_build_prompt`)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_etch.py`:

```python
def test_build_prompt_with_audience_wraps_in_frame():
    """When audience is present, prompt is wrapped with the audience frame."""
    description = "Three services and a database."
    audience = "Reader is a software architect evaluating system structure."
    result = etch._build_prompt(description, audience)

    assert "[Target audience]" in result
    assert "[Diagram]" in result
    assert audience in result
    assert description in result
    # Audience block must precede diagram block.
    assert result.index("[Target audience]") < result.index("[Diagram]")
    assert result.index(audience) < result.index(description)


def test_build_prompt_strips_audience_whitespace():
    """Surrounding whitespace on the audience string is stripped before framing."""
    description = "A diagram."
    result = etch._build_prompt(description, "  Some audience.  \n")
    assert "  Some audience.  " not in result
    assert "Some audience." in result


def test_build_prompt_includes_tailoring_directive():
    """The frame must instruct the model to tailor its output."""
    result = etch._build_prompt("desc", "exec audience")
    assert "Tailor" in result
    assert "audience" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_etch.py -v`
Expected: 3 new failures (NotImplementedError or assertion failures).

- [ ] **Step 3: Complete `_build_prompt`**

Replace the placeholder in `etch.py`:

```python
def _build_prompt(description: str, audience: Optional[str]) -> str:
    """Construct the prompt sent to the image model.

    When audience is None, empty, or whitespace-only, returns the description
    unchanged (byte-identical to the pre-audience behavior).
    """
    if audience is None or not audience.strip():
        return description
    audience_text = audience.strip()
    return (
        f"[Target audience]\n{audience_text}\n"
        "Tailor abstraction level, vocabulary, what to emphasize, "
        "what to omit, and visual register to suit this audience.\n\n"
        f"[Diagram]\n{description}"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_etch.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add etch.py tests/test_etch.py
git -c user.name='TejGandham' -c user.email='TejGandham@users.noreply.github.com' commit -m "feat(etch): wrap description with audience frame when audience present"
```

---

## Task 4: Test and implement the audience length cap

**Files:**
- Modify: `tests/test_etch.py` (add test)
- Modify: `etch.py` (add length cap and constant)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_etch.py`:

```python
def test_build_prompt_rejects_audience_over_cap():
    """An audience string over the cap must raise ValueError."""
    description = "A diagram."
    too_long = "x" * (etch.MAX_AUDIENCE_LEN + 1)
    with pytest.raises(ValueError, match="audience"):
        etch._build_prompt(description, too_long)


def test_build_prompt_accepts_audience_at_cap():
    """An audience string exactly at the cap must succeed."""
    description = "A diagram."
    at_cap = "x" * etch.MAX_AUDIENCE_LEN
    result = etch._build_prompt(description, at_cap)
    assert at_cap in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_etch.py -v`
Expected: 2 new failures (`AttributeError: ... no attribute 'MAX_AUDIENCE_LEN'`).

- [ ] **Step 3: Add the cap constant and length check**

In `etch.py`, add the constant near the other module-level constants:

```python
MAX_AUDIENCE_LEN = 4000
```

Update `_build_prompt` to enforce it (insert the check after the strip):

```python
def _build_prompt(description: str, audience: Optional[str]) -> str:
    """Construct the prompt sent to the image model.

    When audience is None, empty, or whitespace-only, returns the description
    unchanged (byte-identical to the pre-audience behavior).
    """
    if audience is None or not audience.strip():
        return description
    audience_text = audience.strip()
    if len(audience_text) > MAX_AUDIENCE_LEN:
        raise ValueError(
            f"audience must be {MAX_AUDIENCE_LEN} characters or fewer "
            f"(got {len(audience_text)})"
        )
    return (
        f"[Target audience]\n{audience_text}\n"
        "Tailor abstraction level, vocabulary, what to emphasize, "
        "what to omit, and visual register to suit this audience.\n\n"
        f"[Diagram]\n{description}"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_etch.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add etch.py tests/test_etch.py
git -c user.name='TejGandham' -c user.email='TejGandham@users.noreply.github.com' commit -m "feat(etch): cap audience parameter at 4000 chars"
```

---

## Task 5: Wire `audience` into `start_diagram_job` and `_run_generation`

**Files:**
- Modify: `etch.py` (parameter and call wiring)

This task threads the new parameter through the existing async pipeline. No tests added — `_build_prompt` is already covered, and the threading is mechanical.

- [ ] **Step 1: Update `_run_generation` signature and prompt construction**

Replace the current `_run_generation` definition in `etch.py` with this version. The change adds `audience` to the parameter list and replaces the inline `description` with `_build_prompt(description, audience)` in the `contents` argument.

```python
def _run_generation(
    job_id: str,
    api_key: str,
    description: str,
    audience: Optional[str],
    aspect_ratio: str,
    resolution: str,
    output_dir: Path,
) -> None:
    try:
        with _jobs_lock:
            _jobs[job_id]["status"] = "generating"

        prompt = _build_prompt(description, audience)

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                max_output_tokens=32768,
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio, image_size=resolution),
            ),
        )

        if not response.candidates:
            feedback = getattr(response, "prompt_feedback", None)
            raise RuntimeError(f"no candidates returned (prompt_feedback={feedback})")
        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            reason = getattr(candidate, "finish_reason", None)
            raise RuntimeError(f"empty content (finish_reason={reason})")

        image_bytes = None
        for part in candidate.content.parts:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                data = inline.data
                image_bytes = base64.b64decode(data) if isinstance(data, str) else data
                break
        if not image_bytes:
            raise RuntimeError("response had no inline image data")

        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"diagram_{datetime.now():%Y%m%d_%H%M%S}_{job_id[:8]}.png"
        file_path.write_bytes(image_bytes)

        with _jobs_lock:
            _jobs[job_id]["status"] = "complete"
            _jobs[job_id]["file_path"] = str(file_path)
    except Exception as e:
        with _jobs_lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = f"{type(e).__name__}: {e}"
```

- [ ] **Step 2: Update `start_diagram_job` signature, validation, and dispatch**

Replace the current `start_diagram_job` definition with this version. Three changes: new `audience` parameter at the end, an early `_build_prompt` call to fail fast on cap-exceeded audiences (before the job is queued), and `audience` threaded into the thread args.

```python
@mcp.tool()
def start_diagram_job(
    description: str,
    aspect_ratio: str = "16:9",
    resolution: str = "2K",
    output_dir: Optional[str] = None,
    audience: Optional[str] = None,
) -> str:
    """Start an async diagram-generation job. Returns a job_id; poll check_job_status.

    Args:
        description: What to draw — components, labels, relationships.
        aspect_ratio: 1:1, 16:9, 9:16, 4:3, 3:4, or 21:9.
        resolution: 1K or 2K.
        output_dir: Where to save the PNG (defaults to cwd).
        audience: Optional free-form description of the target audience.
            When provided, the description is wrapped with a frame instructing
            the model to tailor abstraction, vocabulary, emphasis, and visual
            register accordingly. Skill callers (see skills/etch/SKILL.md) are
            expected to author rich audience prose; raw human-typed audience
            strings ("for developers") also work but produce weaker steering.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY environment variable is not set")
    if aspect_ratio not in ALLOWED_ASPECT_RATIOS:
        raise ValueError(f"aspect_ratio must be one of {sorted(ALLOWED_ASPECT_RATIOS)}")
    if resolution not in ALLOWED_RESOLUTIONS:
        raise ValueError(f"resolution must be one of {sorted(ALLOWED_RESOLUTIONS)}")

    # Validate audience eagerly: raises ValueError if over cap, before queuing.
    _build_prompt(description, audience)

    _cleanup_jobs()
    job_id = str(uuid.uuid4())
    out_dir = Path(output_dir) if output_dir else Path.cwd()

    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "created": datetime.now()}

    threading.Thread(
        target=_run_generation,
        args=(job_id, api_key, description, audience, aspect_ratio, resolution, out_dir),
        daemon=True,
    ).start()

    return job_id
```

- [ ] **Step 3: Run all tests to confirm no regression**

Run: `pytest tests/ -v`
Expected: 8 passed.

- [ ] **Step 4: Smoke-test that the module still imports and the MCP tool decorator did not break**

Run: `python -c "import etch; print(etch.start_diagram_job.__doc__[:60])"`
Expected: prints the first ~60 chars of the docstring (`Start an async diagram-generation job...`). The `@mcp.tool()` decorator wraps the function but the underlying docstring stays accessible; this is just a sanity check that the import path is healthy.

- [ ] **Step 5: Commit**

```bash
git add etch.py
git -c user.name='TejGandham' -c user.email='TejGandham@users.noreply.github.com' commit -m "feat(etch): thread audience through start_diagram_job and _run_generation"
```

---

## Task 6: Create the etch skill — frontmatter and activation guidance

**Files:**
- Create: `skills/etch/SKILL.md`

The skill is markdown content. Each task adds one section so each commit is reviewable.

- [ ] **Step 1: Create the skill file with frontmatter and the "When to use" section**

Create `skills/etch/SKILL.md`:

```markdown
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
```

- [ ] **Step 2: Verify the file is well-formed markdown**

Run: `python -c "import pathlib; p = pathlib.Path('skills/etch/SKILL.md'); content = p.read_text(); assert content.startswith('---'); assert '\n---\n' in content; print('frontmatter ok')"`
Expected: prints `frontmatter ok`.

- [ ] **Step 3: Commit**

```bash
git add skills/etch/SKILL.md
git -c user.name='TejGandham' -c user.email='TejGandham@users.noreply.github.com' commit -m "feat(skill): add etch skill scaffold with narrow activation guidance"
```

---

## Task 7: Add the flow and inference policy to the skill

**Files:**
- Modify: `skills/etch/SKILL.md` (append sections)

- [ ] **Step 1: Append the flow and inference policy**

Append the following to `skills/etch/SKILL.md`:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add skills/etch/SKILL.md
git -c user.name='TejGandham' -c user.email='TejGandham@users.noreply.github.com' commit -m "feat(skill): document etch flow and inference policy"
```

---

## Task 8: Add the six audience anchor prose blocks

**Files:**
- Modify: `skills/etch/SKILL.md` (append sections)

These six blocks are the heart of the skill — they are the actual text sent as the `audience` parameter to the MCP. Keep them tight (one paragraph each).

- [ ] **Step 1: Append the audience anchors section**

Append the following to `skills/etch/SKILL.md`:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add skills/etch/SKILL.md
git -c user.name='TejGandham' -c user.email='TejGandham@users.noreply.github.com' commit -m "feat(skill): add six curated audience anchor prose blocks"
```

---

## Task 9: Add canvas inference table, interview format, and MCP call template

**Files:**
- Modify: `skills/etch/SKILL.md` (append remaining sections)

- [ ] **Step 1: Append the remaining sections**

Append the following to `skills/etch/SKILL.md`:

```markdown
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

- `start_diagram_job(description, aspect_ratio="16:9", resolution="2K", output_dir=None, audience=None)` — returns a `job_id` immediately.
- `check_job_status(job_id)` — poll every ~10s. Returns `queued (Xs)`, `generating (Xs)`, `complete (Xs) — saved to <path>`, or `failed (Xs): <reason>`.

Pass the full audience prose block (verbatim from the anchor list, or your on-the-fly block) as the `audience` argument. Pass the description the user wrote — do NOT modify it. Pass the inferred (or user-specified) `aspect_ratio` and `resolution`.

After dispatching the job, poll `check_job_status` every ~10 seconds. Generation typically takes 30–60s. Surface the final result line to the user: either `Generated for <audience-name>, <ratio> <res> — saved to <path>`, or the failure reason verbatim.

## What this skill does NOT do

- Compose or edit the description itself. The user (or the brainstorming skill) supplies it.
- Multi-audience or comparison diagrams. One diagram, one audience.
- Any caching or persistence of audience choices across calls. Each invocation is independent.
- Style controls beyond what the audience prose conveys (no `style="blueprint"` knob — register is in the prose).
```

- [ ] **Step 2: Verify final skill file is complete**

Run: `python -c "import pathlib; lines = pathlib.Path('skills/etch/SKILL.md').read_text().splitlines(); print(f'lines={len(lines)}'); print('has all six anchors:', all(a in '\n'.join(lines) for a in ['### Architect', '### Developer', '### Product manager', '### End user', '### Executive', '### Ops / SRE']))"`
Expected: `lines=` shows roughly 130–180 lines and `has all six anchors: True`.

- [ ] **Step 3: Commit**

```bash
git add skills/etch/SKILL.md
git -c user.name='TejGandham' -c user.email='TejGandham@users.noreply.github.com' commit -m "feat(skill): add canvas inference, interview format, MCP call template"
```

---

## Task 10: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the Tools section to document the new parameter**

In `README.md`, find the line that lists `start_diagram_job(description, aspect_ratio="16:9", resolution="2K", output_dir=None)` (around line 29) and replace that single bullet with:

```markdown
- `start_diagram_job(description, aspect_ratio="16:9", resolution="2K", output_dir=None, audience=None)` — kicks off generation, returns a `job_id` immediately. When `audience` is provided (free-form string up to 4000 chars), the description is wrapped with a frame instructing the model to tailor abstraction, vocabulary, emphasis, and visual register to that audience. When `audience` is `None` or empty, the prompt is byte-identical to the no-audience case.
```

- [ ] **Step 2: Add a "Skill" section just before the Architecture section**

Insert this section between the Tools section and the Architecture section in `README.md`:

```markdown
## Skill

For audience-aware generation from inside Claude Code, this repo also ships an `etch` skill at `skills/etch/SKILL.md`. The skill activates when the user asks for a technical or architecture diagram aimed at a specific audience (architect, developer, PM, end user, executive, ops/SRE, or anything else describable), infers the audience and canvas shape from context, runs a single multi-choice interview only when context is too thin, and calls the MCP with a rich `audience` prose block. The MCP itself is audience-agnostic — the skill carries the per-audience guidance, which means future skills (or different clients) can call the MCP without buying into this audience model.

```

- [ ] **Step 3: Verify README still renders cleanly**

Run: `python -c "p = open('README.md').read(); assert 'audience=None' in p; assert '## Skill' in p; print('README ok')"`
Expected: `README ok`.

- [ ] **Step 4: Commit**

```bash
git add README.md
git -c user.name='TejGandham' -c user.email='TejGandham@users.noreply.github.com' commit -m "docs(readme): document audience parameter and skill"
```

---

## Task 11: Final verification

**Files:** none modified.

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: 8 passed, no failures, no warnings about deprecated APIs introduced by this change.

- [ ] **Step 2: Verify the MCP module imports cleanly**

Run: `python -c "import etch; assert callable(etch._build_prompt); assert hasattr(etch, 'MAX_AUDIENCE_LEN'); print('module ok')"`
Expected: `module ok`.

- [ ] **Step 3: Verify the skill file is intact and well-structured**

Run:

```bash
python <<'EOF'
import pathlib
content = pathlib.Path('skills/etch/SKILL.md').read_text()
required = [
    '---', 'name: etch', 'description:',
    '## When to use this skill',
    '## Flow',
    '## Inference confidence',
    '## The six audience anchors',
    '### Architect', '### Developer', '### Product manager',
    '### End user', '### Executive', '### Ops / SRE',
    '## Canvas inference',
    '## Interview format',
    '## Calling the MCP',
]
missing = [r for r in required if r not in content]
assert not missing, f"missing sections: {missing}"
print('skill complete')
EOF
```

Expected: `skill complete`.

- [ ] **Step 4: Verify backward compatibility — `start_diagram_job` without `audience` works exactly as before**

Run:

```bash
python <<'EOF'
import etch
# Old-style call: prompt should be exactly the description.
assert etch._build_prompt("hello world", None) == "hello world"
# Empty/whitespace audience: same.
assert etch._build_prompt("hello world", "") == "hello world"
assert etch._build_prompt("hello world", "   ") == "hello world"
# New-style call: prompt should contain both blocks.
out = etch._build_prompt("hello world", "test audience")
assert "[Target audience]" in out
assert "[Diagram]" in out
assert "test audience" in out
assert "hello world" in out
print('backward compat ok')
EOF
```

Expected: `backward compat ok`.

- [ ] **Step 5: Integration test — install in MCP client and use the skill end-to-end**

The unit tests cover prompt construction. The end-to-end correctness check is a manual run through the MCP client. Skip if no `GOOGLE_API_KEY` is available; otherwise:

1. Confirm the MCP client config points at this repo (per `README.md`'s setup section) and that `GOOGLE_API_KEY` is in the `env` block.
2. Restart the MCP client so it picks up the new `audience` parameter.
3. Confirm the skill is on Claude Code's skill path (or symlink `skills/etch/` into a discovered skills directory).
4. In a Claude Code session, ask: *"etch a diagram of this codebase for a developer onboarding"* — verify the skill activates, announces an inferred developer audience and 16:9/2K canvas, fires `start_diagram_job` with a populated `audience` argument (the developer anchor block), polls, and reports a saved path.
5. Run a second prompt: *"draw the same thing for an exec slide"* — verify the audience flips to the executive anchor block and the diagram visibly differs in register (bigger, fewer labels, business framing).

Expected: both diagrams generate, and the executive one is visually less detailed and more "deck-ready" than the developer one. If the difference is not visible, the audience prose is not steering the model strongly enough — file as a follow-up issue rather than blocking the plan.

- [ ] **Step 6: Final commit (if any cleanup needed) and report**

If any of the steps above surfaced issues that needed fixing inline, commit those fixes:

```bash
git -c user.name='TejGandham' -c user.email='TejGandham@users.noreply.github.com' commit -am "chore: post-implementation fixes from final verification"
```

If all steps passed cleanly, no further commit is needed. Report to the user: implementation complete, X commits added on top of the spec commit, all tests passing.
