# KLM Toolkit

A Claude skill that applies Keystroke-Level Modeling (KLM-GOMS) to estimate
time-on-task for websites, design concepts, and prototypes — and compares
proposed changes or competing workflows to quantify time and cost savings.

**Status: working v1.** The skill, calculator, reference tables, and a
worked example all run end to end — see `skills/klm-time-estimator/`.
Not yet pushed to GitHub (repo isn't created there yet).

## What it does

- Estimates task completion time for a flow from a screenshot, a Figma
  prototype link, or a coded prototype (live URL or source) — no manual
  operator-sequence authoring required.
- Compares a baseline flow against a proposed redesign and reports time
  saved per task, with a sensitivity range from expert/novice persona
  bounds.
- Rolls up time savings into cost savings: time and money saved per
  person/year and per organization/year, given wage rate, task
  frequency, and population.
- Compares the model's estimate against real behavioral/analytics data
  and gives structured guidance for attributing the gap to system
  response time, unmodeled decision/search time, or first-use
  unfamiliarity — see `docs/calibration.md`.

## How it works

1. **Input**: a screenshot, Figma link, or coded prototype, plus a
   plain-language description of the task.
2. **Extraction**: the skill maps the artifact and task description onto
   a structured operator sequence (see `docs/notation.md`), pulling real
   element sizes/positions from Figma or a live DOM where available for
   Fitts's-law pointing-time accuracy.
3. **Calculation**: a deterministic script sums operator times (with
   documented mental-prep placement rules) into a total estimate.
4. **Output**: a plain-language report — no YAML-reading required — with
   the underlying model available as an optional "show your work"
   appendix.

## Example

**Prompt:**

> Here's our checkout page today — users have to manually type in their
> card number, expiry, and CVC every time [screenshot attached]. I mocked
> up a redesign that lets them pay with a saved card in one click
> [Figma link]. Can you tell me how much time and money that redesign
> would actually save us? We've got about 450 employees doing this 12
> times a year, and their loaded rate is about $28.50/hr.

**Output:**

*(this is real output from `klm_calc.py --table` on the flows in
`skills/klm-time-estimator/examples/`, not a mockup — see "Try it" below)*

### Current: manual card entry

*persona: intermediate · device: desktop*

| Step | KLM operators | Time (s) |
|---|---|---|
| **Log in** | | |
| Enter Email | `P M K*20` | 8.05 |
| Enter Password | `P M K*12` | 5.81 |
| Click "Log in" | `M P` | 1.92 |
| System responds | `R1.2` | 1.20 |
| **Open payment form** | | |
| Click "Add payment method" | `M P` | 1.89 |
| Decide new card vs saved card | `M` | 1.35 |
| **Fill card fields** | | |
| Enter Card number | `P M K*16` | 6.93 |
| Enter Expiry | `P M K*4` | 3.57 |
| Enter CVC | `P M K*3` | 3.29 |
| Click "Save card" | `M P` | 1.97 |
| **System processes** | | |
| System responds | `R1.8` | 1.80 |
| **Total** | | **37.78** |

### Proposed: one-click saved wallet

*persona: intermediate · device: desktop*

| Step | KLM operators | Time (s) |
|---|---|---|
| **Log in** | *(same 4 steps as above)* | 16.98 |
| **Pay with saved wallet** | | |
| Click "Pay with saved card" | `M P` | 1.74 |
| Confirm this is the right saved card | `M` | 1.35 |
| **System processes** | | |
| System responds | `R1.5` | 1.50 |
| **Total** | | **21.58** |

### Summary

| | Current | Proposed |
|---|---|---|
| Time per task | 37.78s | 21.58s |

| Saved | Worst case | Average | Best case |
|---|---|---|---|
| Per task | 12.52s | **16.20s** | 21.26s |
| Per person/year | USD 1.19 | **USD 1.54** | USD 2.02 |
| Per org/year | USD 535.36 | **USD 692.68** | USD 908.99 |

*Basis: 450 users × 12x/year × $28.50/hr (internal_tool). Worst/best case
from expert↔novice persona bounds; average uses the flow's stated persona
(intermediate). Keystroke-Level Modeling assumes expert, error-free
performance, so this is a best-case floor — real completion times will
run somewhat higher, and it's best used to compare two designs against
each other rather than as a prediction of the exact median.*

This is what the conversation looks like — no YAML is written or read by
the designer. See `skills/klm-time-estimator/examples/` for the actual
flow files behind this example.

## Repo layout

```
klm-toolkit/
├── LICENSE                       CC BY 4.0
├── README.md
├── docs/
│   ├── notation.md               Task notation spec (flow / comparison / shorthand / includes)
│   └── calibration.md            Model-vs-real-data methodology
└── skills/
    └── klm-time-estimator/
        ├── SKILL.md              The Claude skill definition
        ├── references/
        │   ├── klm-operators.md      Operator timing constants, Fitts's law, M-placement rules
        │   └── action-library.yaml   Composite actions (click_button, fill_text_field, ...)
        ├── scripts/
        │   └── klm_calc.py            Deterministic calculator (flow + comparison + economics + calibration)
        └── examples/                  Worked flows, fragments, and a comparison — see examples/README.md
```

## Try it

```bash
cd skills/klm-time-estimator
python3 scripts/klm_calc.py compare examples/comparisons/checkout-redesign.yaml --table
```

Drop `--table` for a shorter plain-text summary, or use `--json` for
machine-readable output.

## License

CC BY 4.0 — see `LICENSE`. Give credit, link the license, note changes.
