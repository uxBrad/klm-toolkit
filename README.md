# KLM Toolkit

A Claude skill that applies Keystroke-Level Modeling (KLM-GOMS) to estimate
time-on-task for websites, design concepts, and prototypes — and compares
proposed changes or competing workflows to quantify time and cost savings.

**Status: in design.** This repo is being scaffolded before the skill
itself is built with `skill-creator`.

## What it does (planned)

- Estimate task completion time for a flow from a screenshot, a Figma
  prototype link, or a coded prototype (live URL or source) — no manual
  operator-sequence authoring required.
- Compare a baseline flow against a proposed redesign and report time
  saved per task.
- Roll up time savings into cost savings: time saved per person/year and
  per organization/year, given wage rate, task frequency, and population.
- Compare the model's estimate against real behavioral/analytics data and
  attribute the gap to system response time, cognitive load, or unmodeled
  search/error behavior.

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

## Repo layout (planned)

```
klm-toolkit/
├── LICENSE                  CC BY 4.0
├── README.md
├── docs/
│   └── notation.md          Task notation spec (flow / comparison / shorthand)
├── skills/
│   └── klm-time-estimator/  The Claude skill itself (SKILL.md, references, scripts)
└── examples/                Worked example flows and comparisons
```

## License

CC BY 4.0 — see `LICENSE`. Give credit, link the license, note changes.
