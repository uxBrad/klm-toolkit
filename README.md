# KLM Toolkit

A Claude skill that applies Keystroke-Level Modeling (KLM-GOMS) to estimate
time-on-task for websites, design concepts, and prototype. It compares
proposed changes or competing workflows to quantify time and cost savings.

## Install

```bash
npx skills add uxBrad/klm-toolkit
```

Works with Claude Code and other agents supported by the [skills CLI](https://skills.sh).

## What it does

- Estimates task completion time for a flow from a screenshot, a Figma
  prototype link, or a coded prototype (live URL or source)
- Compares a benchmark flow against a proposed redesign and reports time
  saved per task.
- Reports back cost savings based on time saved per
  person/year and per organization/year, given wage rate, task
  frequency, and size of the user base.
- Compares the model's estimate against real behavioral/analytics data
  and gives structured guidance for attributing the gap to system
  response time, unmodeled decision/search time, or first-use
  unfamiliarity. Check out `docs/calibration.md`.
- Renders a timeline visualization — steps laid out on a shared clock,
  icon per step chosen by whichever KLM operator actually dominates that
  step's time (typing, pointing/clicking, thinking, reading, system
  response), with a "Time saved" lane bridging the two flows' END points
  when comparing a baseline against a redesign.

## How it works

1. **Input**: a screenshot, Figma link, or coded prototype, and/or a plain-language description of the task.
2. **Extraction**: the skill maps the artifact and task description onto a structured operator sequence (see `docs/notation.md`), pulling real
   element sizes/positions from Figma or a live DOM where available for
   Fitts's-law pointing-time accuracy.
3. **Calculation**: a script sums operator times (with documented mental-prep placement rules) into a total estimate.
4. **Output**: a plain-language report.

## Example

**Prompt:**

> Here's our checkout page today... Users have to manually type in their
> card number, expiration date, and CVC every time [screenshot attached]. I mocked
> up a redesign that lets them pay with a saved card
> [Figma link]. Can you tell me how much time and money that redesign
> would actually save us? We have about 450 employees doing this 12
> times a year, and their hourly rate is about $28.50/hr.

**Output:**

### Current: manual card entry

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

### Proposed: saved wallet

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

The same comparison, as a timeline (`--svg` / `--svg-out`):

![Timeline comparing the current manual checkout flow against the proposed saved-wallet redesign, showing where the two flows diverge and the time saved between their end points](examples/comparisons/checkout-redesign-timeline.svg)

## Repo Structure

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
        └── examples/                  Worked flows, fragments, a comparison, and its timeline SVG — see examples/README.md
```

## Try it

```bash
cd skills/klm-time-estimator
python3 scripts/klm_calc.py compare examples/comparisons/checkout-redesign.yaml --table
python3 scripts/klm_calc.py compare examples/comparisons/checkout-redesign.yaml --svg-out timeline.svg
```

Drop `--table` for a shorter plain-text summary, use `--json` for
machine-readable output, or `--svg`/`--svg-out path.svg` for the timeline
visualization (stdout or a file, respectively). Works on a bare `flow`
estimate too (single lane, no comparison). Flags can be combined.

## License

CC BY 4.0 — see `LICENSE`. Give credit, link the license, note changes.
