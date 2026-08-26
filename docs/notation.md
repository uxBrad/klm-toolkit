# Task Notation Spec (v1)

This is the internal representation the skill uses to compute KLM
estimates. Designers do not author this by hand — it's generated from a
screenshot, Figma link, or coded prototype plus a plain-language task
description (see "Extraction layer" below). It's shown back to users as
an optional "show your work" appendix, and can be hand-edited by anyone
who wants that level of control.

## Design principles

- YAML: parseable by a deterministic calc script, diffable in git.
- Two document types: `flow` (one task, one persona/device) and
  `comparison` (baseline vs. proposed + economics).
- Composite actions (from a reusable action-library) do most of the work;
  raw operators are an escape hatch.
- Mental-prep (`M`) placement is never silent — it's either an explicit
  step with a stated reason, or an auto-inserted default from the action
  library that's visible in the computed trace.

## Flow document

```yaml
klm_version: 1
type: flow
name: "Checkout — Add Payment Method (current)"
persona: intermediate        # novice | intermediate | expert
device: desktop              # desktop | mobile | touch_tablet
source:
  figma: "https://figma.com/file/abc/node-id=123"    # optional
  analytics: "GA4: checkout_payment_step"             # optional
frequency_per_year: 12       # how often ONE user does this

steps:
  - phase: "Open payment form"
    actions:
      - action: click_button
        label: "Add payment method"
        target: {width: 140, height: 40, distance: 220}   # px, Fitts's law inputs
      - op: M
        reason: "decide new card vs saved card"

  - phase: "Fill card fields"
    actions:
      - action: fill_text_field
        field: "Card number"
        chars: 16
      - action: fill_text_field
        field: "Expiry"
        chars: 4
      - action: fill_text_field
        field: "CVC"
        chars: 3
      - action: click_button
        label: "Save card"
        target: {width: 100, height: 40, distance: 300}

  - phase: "System processes"
    actions:
      - op: R
        seconds: 1.8
        source: measured   # measured | assumed

notes:
  - "Assumes saved billing address; no address re-entry."
```

### Field notes

- `action:` entries expand via `references/action-library.yaml` (e.g.
  `fill_text_field` → `P, M, K×chars`).
- `op:` entries are raw classic-KLM operators (`K`, `P`, `H`, `D`, `M`,
  `R`) for anything the library doesn't cover, or to override a default.
- Every action carries an implicit `mental_prep: auto|true|false`
  (default `auto` = library default). Set `false` explicitly when you've
  already placed a manual `M` for that decision point, to avoid double
  counting.
- `phase` groups are for reporting only — lets output show "time to
  complete step 2," not just a grand total.
- `source:` / `notes:` are provenance, not inputs to the math — they're
  what makes an estimate defensible when a stakeholder pushes back.

## Includes (DRY sub-flows)

A step can splice in a shared subtask by reference instead of
copy-pasting it across flows:

```yaml
steps:
  - include: flows/common/login.yaml
  - phase: "Update address"
    actions: [...]
```

Optional parameters can be passed into an included flow:

```yaml
  - include: flows/common/fill_address.yaml
    with:
      country: "US"
```

**Validation rule**: if the included file's `device` or `persona` doesn't
match the parent flow, the calc script emits a warning rather than
silently mixing assumptions.

## Shorthand (fast raw-operator sketches)

For quick sketches only — no Fitts's-law target inputs, no composite
actions. Use full structured YAML when target-size precision matters.

```yaml
ops: "P M K*16 P M K*4 P M K*3 R1.8"
```

Grammar: whitespace-separated tokens.
- `K*n` — n keystrokes (bare `K` = 1)
- bare `P` / `H` / `D` / `M` — one default-time instance
- `R<seconds>` — explicit override, e.g. `R1.8`

Shorthand always expands into the same structured `steps` internally, so
it's inspectable and diffable like any other flow.

## Comparison document

```yaml
klm_version: 1
type: comparison
name: "Checkout payment flow redesign"
baseline: flows/checkout-payment-current.yaml
proposed: flows/checkout-payment-redesigned.yaml

economics:
  wage_per_hour: 28.50
  currency: USD
  num_users: 450
  scope: internal_tool        # internal_tool | customer_facing

calibration:                  # optional — only when real data exists
  actual_median_seconds: 42.0
  actual_source: "GA4 event timing, n=1,240 sessions, Aug 2026"
```

The calc script sums each flow independently, diffs them for time
saved/task, then applies `economics` to compute per-person/year and
per-org/year savings. If `calibration` is present, it also reports the
model-vs-actual delta, bucketed into extra system-response time, extra
decision time, or unmodeled search/error — not a single vague number.

## Extraction layer (input → notation)

Designers never hand-write this notation. They provide an artifact plus
a plain-language task description; the skill derives the flow.

| Input | How it's read | Fitts's-law fidelity |
|---|---|---|
| Screenshot(s) | Vision: identify interactive elements relevant to the task, estimate bounding boxes as % of image | Low — flagged `source: estimated` unless real viewport dims given |
| Figma prototype (link) | Figma MCP pulls exact node x/y/width/height; prototype interactions can auto-sequence steps in click-through order | High — real px values |
| Coded prototype, live URL | Browser automation reads actual DOM element positions/sizes; can measure real system response time instead of assuming R | Highest — production values |
| Coded prototype, source only | Parse markup/layout for approximate structure | Medium — flagged lower confidence |

## Open items for the next design pass

- Operator time table + Fitts's-law constants (`references/klm-operators.md`)
- Action-library reference (`references/action-library.yaml`)
- Calc script behavior (deterministic, testable)
- Cost/value rollup formulas and sensitivity range
- Calibration bucketing methodology
- Output report template
