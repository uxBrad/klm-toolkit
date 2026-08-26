# Calibration: model vs. real behavioral data

A KLM estimate is a **floor** — expert, error-free performance. Real users
run slower, and the gap is informative if you decompose it instead of
shrugging at one number.

## Method

1. **Get a real task time.** Pull it from analytics event timing (e.g. a
   GA4 funnel step, a Mixpanel event pair, session-recording timestamps),
   scoped to the *same* start/end boundary as the modeled flow. Boundary
   mismatch is the single most common source of a confusing delta —
   double-check what the analytics event actually starts/stops on before
   trusting the comparison.
2. **Use the median, not the mean.** Task completion times are roughly
   lognormal; a mean gets dragged around by a long tail of stalled or
   abandoned sessions in a way the median doesn't.
3. **Attach it as `calibration:`** on the flow or comparison document
   (see `docs/notation.md`) and run the calculator. It reports the model
   total, the actual median, the delta, and — critically — how much of
   the model's own total was `assumed` vs. `measured` system-response
   (`R`) time.
4. **Attribute the gap in this order:**
   - **Assumed R time first.** If a meaningful share of the model's total
     is unmeasured system response, that's the cheapest thing to fix —
     go get real load/render/API timing before attributing anything else
     to "cognitive load."
   - **First-use unfamiliarity.** If the flow wasn't marked
     `first_use: true` but the real users were seeing it for the first
     time, remodel with that flag rather than inflating other constants.
   - **Unmodeled decision/search time.** Classic KLM has no operator for
     open-ended scanning, comparing options, or backtracking. If the task
     involves real choice-making (not a fully anticipated expert path),
     the remaining gap is plausibly this — and it's a legitimate finding,
     not a modeling failure. Consider adding `W` (reading/scan) time for
     content-heavy steps you under-counted.
   - **Errors/backtracking.** KLM assumes error-free execution. A flow
     with a real-world error rate needs that acknowledged separately —
     don't fold it into inflated `M` or `K` constants.
5. **A negative delta (real users faster than the model) is a flag, not a
   win.** Against an expert-floor estimate this shouldn't normally
   happen. Check event-boundary mismatch first, then whether the
   analytics population differs from who the flow was modeled for.

## What this is not

This process produces a reasoned attribution, not a statistically
partitioned variance decomposition. Treat the buckets above as places to
look, not as a formula that outputs an exact split. If the same flow gets
calibrated repeatedly across projects, record the correction factors you
converge on (e.g. "this audience runs ~1.4x slower than expert KLM") and
reuse them as documented `persona`/multiplier overrides rather than
re-deriving from scratch each time.
