# Worked example: checkout payment redesign

A baseline "add a new card manually" flow vs. a proposed "pay with saved
wallet" redesign, both including a shared `login` fragment via `include:`.

```bash
cd skills/klm-time-estimator
python3 scripts/klm_calc.py flow examples/flows/checkout-payment-current.yaml
python3 scripts/klm_calc.py compare examples/comparisons/checkout-redesign.yaml
```

Expected comparison output (rounding may vary slightly if the reference
constants are tuned):

```
=== Checkout payment flow redesign ===

Baseline (Checkout — Add Payment Method (current)): 37.78s
Proposed (Checkout — Add Payment Method (redesigned: one-click saved wallet)): 21.58s
Time saved per task: 16.20s
Sensitivity range (expert–novice persona bounds): 12.52s to 21.26s

Economics (scope: internal_tool, 450 users, 12x/year, $28.5/hr):
  Point estimate — per person/year: 0.05 hrs (USD 1.54)
  Point estimate — per org/year: 24.30 hrs (USD 692.68)
  Range — per org/year: USD 535.36 to USD 908.99

Calibration vs. real data:
  Model estimate: 37.78s
  Actual median: 52.00s  (source: GA4 event timing, n=1,240 sessions, Aug 2026 (baseline flow))
  Delta: 14.22s
  Assumed R time in model: 1.20s (measured: 1.80s)
  Real users are slower than the model (expected — KLM models expert, error-free
  performance, so it's a floor, not a prediction of the median). Check assumed R
  (system response) time first: 1.20s of this estimate is unmeasured — get real
  timing data before attributing further. Remaining gap is most likely additional
  decision/search time KLM doesn't model, or first-use unfamiliarity if this flow
  wasn't marked first_use: true.
```

Add `--json` to either command for machine-readable output.
