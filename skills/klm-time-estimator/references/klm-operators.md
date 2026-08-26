# KLM Operator Reference

Ground-truth timing constants for the calculator. Values are drawn from
the classic KLM-GOMS literature (Card, Moran & Newell 1980; Card, English
& Burr 1978 for pointing; Olson & Olson 1990 for mental-prep placement
refinements) and are **defaults, not gospel** — override any of them with
a project's own calibration data (see `docs/calibration.md`) once you
have it.

## Classic operators

| Op | Name | Default (s) | Notes |
|----|------|-------------|-------|
| `K` | Keystroke | persona-dependent, see below | One key press or click on a physical key |
| `P` | Point (mouse/pointer to target) | 1.10 (flat default) or Fitts's law when target dims given | See Fitts's law below |
| `H` | Home (hand switch, e.g. keyboard ↔ mouse) | 0.40 | Once per switch, not per operator |
| `D` | Draw (freehand line segments) | 1.00 (flat default, low confidence) | Highly task-specific — override with a measured value whenever possible |
| `M` | Mental preparation | 1.35 | See placement rules below — this is the operator most often mis-used |
| `R` | System response (wait) | none — required input | Always supplied explicitly (`measured` or `assumed`), never defaulted |

### K — persona-dependent typing/click speed

| Persona | Seconds/keystroke | Basis |
|---|---|---|
| `expert` | 0.12 | Skilled typist, ~90 wpm |
| `intermediate` | 0.28 | Average non-specialist typist, ~40 wpm |
| `novice` | 0.50 | Unfamiliar with the keyboard/interface, hunt-and-peck |

A first-time-use penalty of **+50%** on `K` and `M` is applied automatically
when a flow is marked `first_use: true` (e.g. onboarding, unfamiliar
tools) — first-time performance is not steady-state expert performance
and shouldn't be reported as such.

### P — Fitts's law for pointing

When `target: {width, height, distance}` (px) is supplied on a `P`
operator or a composite action that resolves to one:

```
MT = a + b * log2(D / W + 1)
```

- `D` = distance from current position to target center
- `W` = target width along the axis of movement (use the smaller of
  width/height for a conservative estimate, or the true approach axis if
  known)
- `a` = 0.0 s (offset)
- `b` = 0.20 s/bit (≈ index of performance 5.0 bits/s for mouse pointing,
  per Card/English/Burr-derived constants commonly used in KLM tooling)

These constants are approximations — real values vary by input device,
target density, and user population. **Recalibrate `a`/`b` against real
click-to-target timing data whenever you have it**, and always report
which constants were used.

When no target dimensions are available (screenshot-only input with no
real pixel data, or shorthand mode), fall back to the flat KLM average of
**1.10 s** and mark the estimate `source: estimated`.

### M — placement rules (Card, Moran & Newell + Olson & Olson)

`M` placement is the single largest source of KLM estimate variance.
Apply these rules in order; do not place an `M` anywhere that isn't
justified by one of them:

1. **Rule 0 (default):** insert an `M` before each cognitive "chunk" —
   not before every keystroke. A chunk is a set of keystrokes typed as
   one unit (e.g., an entire field value), not one per character.
2. **Rule 1 (anticipation):** if the operator following a `K` is fully
   determined by the same cognitive act (e.g., pressing Enter to submit
   a value the user already committed to), no `M` before it.
3. **Rule 2 (collapse):** if two `M`s would be adjacent (nothing but
   anticipated operators between them), delete the second — consecutive
   mental units collapse to one.
4. **Rule 3 (habitual actions):** fully habitual, low-choice actions
   (toggling a familiar checkbox, clicking a consistently-placed "Next"
   button in a flow the user has done many times) get no `M` by default.
5. **Rule 4 (unit-task-initial):** place an `M` at the start of any new
   sub-task that requires a decision not yet made (choosing between
   options, deciding what to enter, recalling where something is).

In the notation, every `M` — whether explicit or auto-inserted by the
action library — should be traceable to one of these rules. The
calculator surfaces this in its trace output so a reviewer can see *why*
each `M` is there, not just that it is.

## Mobile/touch extensions (not classic KLM)

Touch interaction doesn't map cleanly onto desktop KLM operators. These
are practitioner-level approximations (Holleis et al. 2007 and later
refinements), flagged as extensions — lower confidence than the
desktop-KLM constants above.

| Op | Name | Default (s) | Notes |
|----|------|-------------|-------|
| `T` | Tap | 0.20 | Roughly comparable to `K`, but includes touch-target acquisition |
| `TL` | Long-press | 0.80 | |
| `SW` | Swipe/flick | 0.30 | Highly dependent on distance; treat as a rough default |
| `TH` | Thumb-reach home (switching grip/reach zone) | 0.30 | Touch analog of `H` |

## Non-KLM extension: reading/scanning

Classic KLM has no operator for reading or visually scanning content —
it assumes expert, fully-anticipated interaction. For content-heavy
steps (scanning a list, reading a paragraph before deciding), use the
`W` (word-scan) extension rather than pretending it's mental prep:

```
W_time = word_count * 0.24   # ≈ 250 wpm silent reading
```

Always label `W` time separately in output — it is not a validated KLM
operator and mixing it into the `M` total would misrepresent the model.

## Stated limitations (surface these in every report)

- KLM models **expert, error-free** performance. It does not model
  errors, backtracking, or open-ended search/exploration.
- It is a **point estimate**, not a distribution. Real task times are
  roughly lognormal; treat the KLM number as a floor/best-case, not a
  prediction of the median.
- Fitts's law constants and persona K-rates are defaults from the
  literature, not measurements of your actual users, until calibrated.
