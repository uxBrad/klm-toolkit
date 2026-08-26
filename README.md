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
python3 scripts/klm_calc.py compare examples/comparisons/checkout-redesign.yaml
```

## License

CC BY 4.0 — see `LICENSE`. Give credit, link the license, note changes.
