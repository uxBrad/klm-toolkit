---
name: klm-time-estimator
description: Use this skill when the user wants to estimate time-on-task for a website, app, design concept, or prototype using Keystroke-Level Modeling (KLM-GOMS); compare two workflows or a proposed redesign against a baseline to quantify time savings; roll up time savings into cost savings (time and money saved per person/year and per organization/year, given a wage rate and usage frequency); or compare a KLM estimate against real analytics/behavioral data to see whether a gap is driven by system response time, unmodeled decision/search time, or first-use unfamiliarity. Triggers on requests like "how long would this take a user", "estimate time on task", "KLM" / "keystroke level model", "compare these two flows", "time savings from this redesign", "what would this save us a year", or when the user hands over a screenshot, Figma prototype link, or coded prototype and asks about efficiency, friction, or usability cost in time/money terms.
license: CC-BY-4.0
---

# KLM Time Estimator

Applies Keystroke-Level Modeling to estimate task completion time from a
design artifact, compares flows, and rolls estimates up into cost
savings. The math is never done by hand or estimated in prose — it
always runs through `scripts/klm_calc.py` so numbers are reproducible.

Full notation spec: `../../docs/notation.md` (repo root `docs/`).
Calibration methodology: `../../docs/calibration.md`.
Operator timing constants: `references/klm-operators.md`.
Composite action definitions: `references/action-library.yaml`.

## The user never writes YAML

Designers provide an **artifact** (screenshot, Figma link, or coded
prototype) plus a **plain-language task description** ("user adds a
payment method"). You do the translation into the flow notation, run the
calculator, and report back in plain language. The YAML/trace is an
optional "show your work" appendix, never the primary deliverable, unless
the user is clearly a developer working with the notation directly.

## Step 1 — figure out what's being asked

- **Single estimate**: one flow, one number.
- **Comparison**: baseline vs. proposed (a redesign, or two competing
  workflows) — time saved and, optionally, cost saved.
- **Calibration**: an estimate checked against real analytics/behavioral
  data — read `docs/calibration.md` before doing this.

These aren't mutually exclusive — a comparison can also carry
calibration data on its baseline flow.

## Step 2 — get the artifact and extract the flow

| Input given | How to extract | Fitts's-law fidelity |
|---|---|---|
| Screenshot(s) | Read the image directly; identify the interactive elements relevant to the described task; estimate bounding boxes as a fraction of image size | Low — mark `source: estimated` in the trace, and say so in the report unless the user also gives real viewport pixel dimensions |
| Figma link | Use the Figma MCP tools (`get_design_context`, `get_metadata`, `get_screenshot`) to pull exact node x/y/width/height, and prototype interactions to sequence steps in click-through order | High — real px values |
| Coded prototype, live URL | Drive it with the `run` skill / browser automation to read actual DOM element positions and sizes; if you can capture real navigation/render timing, use it as a `measured` `R` value instead of assuming one | Highest |
| Coded prototype, source only (not running) | Read the markup/layout for approximate structure | Medium — mark lower confidence |

Map each step of the plain-language task onto entries in
`references/action-library.yaml` (`click_button`, `fill_text_field`,
`select_dropdown`, `toggle_checkbox`, `scroll_and_read`,
`drag_and_drop`, and the mobile variants `tap`/`long_press`/`swipe`).
Fall back to raw `op:` entries only when nothing in the library fits.
Never invent a new composite action ad hoc without checking the library
first — consistency across estimates is the point.

## Step 3 — ask only for what you can't infer

Default assumptions (state them in the final report, don't bury them):
- `persona: intermediate` unless the user says otherwise or the audience
  is clearly novice/expert (e.g. internal power-user tool → expert;
  public first-time signup → consider `first_use: true`).
- `device: desktop` unless the artifact is clearly mobile/touch.

Only ask the user directly for:
- Wage/burdened rate, task frequency per user per year, and number of
  users/customers — **only if they want cost savings**, not for a bare
  time estimate.
- Whether this is a first-time-use flow (onboarding) vs. steady-state
  repeat use, when it's not obvious from context.

## Step 4 — write the flow(s) and run the calculator

Write flow/comparison YAML files (following `docs/notation.md`) to a
working location — ask the user where they'd like estimates saved if
they're building a library of them, otherwise use a scratch path. Then:

```bash
python3 scripts/klm_calc.py flow path/to/flow.yaml --table
python3 scripts/klm_calc.py compare path/to/comparison.yaml --table
```

`--table` produces the primary deliverable: a step-by-step KLM breakdown
table for each flow (one row per step, with its operators and time) plus
a worst-case/average/best-case summary table for time and — when
economics were given — cost saved per person/year and per org/year. Use
plain `--json` instead when you need to parse the result yourself (e.g.
to build a chart) rather than relaying a report.

## Step 5 — report back in plain language

Lead with the tables from `--table`, not a prose restatement of the same
numbers:
- Show the current flow's step-by-step table, the proposed flow's
  step-by-step table, and the summary table (worst case / average / best
  case, time and cost) exactly as the calculator produces them — don't
  hand-recompute or re-derive these numbers yourself.
- For a bare single-flow estimate (no comparison), the flow table plus
  its total is the whole answer — no summary table needed.
- Always state the persona/device assumptions used and flag anything
  estimated (vs. measured) — that's what makes the number defensible
  when someone pushes back.
- Note the model's limitations briefly: KLM assumes expert, error-free
  performance, so this is a best-case floor, not a prediction of the
  median real-world time — worth saying once, not hedging every line.
  The summary table's "worst case" column is about persona variation,
  not about this floor-vs-reality gap — don't conflate the two.
- If calibration data was provided, report the delta and the attribution
  guidance from `docs/calibration.md` rather than a bare number.
- Offer the underlying flow YAML as an appendix for anyone who wants to
  audit or hand-edit it.

## Building a reusable flow library

If the user is doing this repeatedly (an ongoing design practice, a
portfolio of case studies), suggest saving flows under a project
directory following the `examples/` layout in this skill
(`flows/`, `fragments/`, `comparisons/`) so common subtasks (login,
address entry, payment) become `include:`-able fragments instead of
being re-derived each time.
