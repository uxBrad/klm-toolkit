#!/usr/bin/env python3
"""
KLM calculator — deterministic scoring for the klm-toolkit task notation.

Usage:
    python3 klm_calc.py flow <flow.yaml> [--json]
    python3 klm_calc.py compare <comparison.yaml> [--json]

No network access, no LLM calls — this is pure arithmetic over the
notation defined in docs/notation.md, so estimates are reproducible and
auditable.
"""

import argparse
import json
import math
import os
import sys

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ACTION_LIBRARY = os.path.join(SCRIPT_DIR, "..", "references", "action-library.yaml")

# --- Constants (mirrors references/klm-operators.md — keep in sync) ---

K_SECONDS_BY_PERSONA = {"expert": 0.12, "intermediate": 0.28, "novice": 0.50}
M_SECONDS = 1.35
H_SECONDS = 0.40
D_SECONDS_DEFAULT = 1.00
P_SECONDS_FLAT_DEFAULT = 1.10
FITTS_A = 0.0
FITTS_B = 0.20
W_SECONDS_PER_WORD = 0.24

MOBILE_DEFAULTS = {"T": 0.20, "TL": 0.80, "SW": 0.30, "TH": 0.30}

FIRST_USE_MULTIPLIER = 1.5


class KlmError(Exception):
    pass


# --- Loading ---

def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_action_library(path=DEFAULT_ACTION_LIBRARY):
    return load_yaml(path)


# --- Shorthand parsing ---

def parse_shorthand(ops_string):
    instances = []
    for tok in ops_string.split():
        instances.append(_parse_shorthand_token(tok))
    return instances


def _parse_shorthand_token(tok):
    if tok.startswith("K"):
        rest = tok[1:]
        if rest.startswith("*"):
            rest = rest[1:]
        count = int(rest) if rest else 1
        return {"op": "K", "count": count, "reason": "shorthand"}
    if tok.startswith("R"):
        rest = tok[1:]
        if not rest:
            raise KlmError("Shorthand 'R' requires an explicit seconds value, e.g. R1.8")
        return {"op": "R", "seconds_override": float(rest), "source": "assumed", "reason": "shorthand"}
    if tok.startswith("W"):
        rest = tok[1:]
        if not rest:
            raise KlmError("Shorthand 'W' requires an explicit word count, e.g. W40")
        return {"op": "W", "count": int(rest), "reason": "shorthand"}
    if tok in ("P", "H", "D", "M", "T", "TL", "TH", "SW"):
        return {"op": tok, "reason": "shorthand"}
    raise KlmError(f"Invalid shorthand token: {tok!r}")


# --- Action-library expansion ---

def expand_action(action, library):
    """Expand a composite `action:` entry into raw operator instances."""
    name = action.get("action")
    if name is None:
        raise KlmError(f"Action entry missing 'action' key: {action}")
    if name not in library:
        raise KlmError(f"Unknown action '{name}' — not in action-library.yaml")
    spec = library[name]
    auto_mp_default = spec.get("auto_mental_prep", False)
    mental_prep = action.get("mental_prep", "auto")
    if mental_prep == "auto":
        use_mp = auto_mp_default
    else:
        use_mp = bool(mental_prep)

    out = []
    for step in spec.get("sequence", []):
        op = step["op"]
        if op == "M" and step.get("condition") == "auto_mental_prep":
            if not use_mp:
                continue
            out.append({"op": "M", "reason": f"{name}: auto mental-prep (Rule 0/4)"})
            continue
        inst = {"op": op, "reason": name}
        if step.get("uses_target") and "target" in action:
            inst["target"] = action["target"]
        if "count_from" in step:
            param = step["count_from"]
            if param not in action:
                raise KlmError(f"Action '{name}' requires parameter '{param}'")
            inst["count"] = action[param]
        out.append(inst)
    return out


# --- Timing ---

def fitts_seconds(target):
    width = target.get("width")
    height = target.get("height")
    distance = target.get("distance")
    if width is None or distance is None:
        return P_SECONDS_FLAT_DEFAULT, "estimated (no target dims — flat KLM default)"
    w = min(width, height) if height else width
    if w <= 0:
        return P_SECONDS_FLAT_DEFAULT, "estimated (invalid target width)"
    mt = FITTS_A + FITTS_B * math.log2(distance / w + 1)
    return mt, "fitts (from target dims)"


def operator_seconds(inst, persona, first_use):
    op = inst["op"]
    fu = FIRST_USE_MULTIPLIER if first_use else 1.0

    if op == "K":
        count = inst.get("count", 1)
        per = K_SECONDS_BY_PERSONA[persona] * fu
        return per * count, f"{persona} typing rate"
    if op == "P":
        if "target" in inst:
            secs, basis = fitts_seconds(inst["target"])
        else:
            secs, basis = P_SECONDS_FLAT_DEFAULT, "flat KLM default (no target dims)"
        return secs, basis
    if op == "H":
        return H_SECONDS, "fixed KLM default"
    if op == "D":
        return inst.get("seconds_override", D_SECONDS_DEFAULT), "flat default — low confidence, override if possible"
    if op == "M":
        return M_SECONDS * fu, "fixed KLM default"
    if op == "R":
        if "seconds_override" not in inst:
            raise KlmError("R operator requires an explicit 'seconds' value")
        return inst["seconds_override"], inst.get("source", "assumed")
    if op == "W":
        count = inst.get("count", 1)
        return count * W_SECONDS_PER_WORD, "extension (reading estimate, not classic KLM)"
    if op in MOBILE_DEFAULTS:
        return MOBILE_DEFAULTS[op], "mobile extension default"
    raise KlmError(f"Unknown operator: {op}")


# --- Flow resolution (includes, steps -> flat operator trace) ---

def resolve_steps(steps, base_dir, library, persona, device, first_use, seen_includes):
    trace = []
    warnings = []
    for step in steps:
        if "include" in step:
            inc_path = os.path.normpath(os.path.join(base_dir, step["include"]))
            if inc_path in seen_includes:
                raise KlmError(f"Circular include detected: {inc_path}")
            inc_doc = load_yaml(inc_path)
            if inc_doc.get("type") != "fragment":
                warnings.append(f"Included file {step['include']} is not type: fragment")
            inc_device = inc_doc.get("device")
            if inc_device and inc_device != device:
                warnings.append(
                    f"Included fragment '{step['include']}' declares device={inc_device}, "
                    f"parent flow is device={device} — mismatch not resolved automatically"
                )
            sub_trace, sub_warnings = resolve_steps(
                inc_doc.get("steps", []), os.path.dirname(inc_path), library,
                persona, device, first_use, seen_includes | {inc_path},
            )
            trace.extend(sub_trace)
            warnings.extend(sub_warnings)
            continue

        phase = step.get("phase", "(unnamed phase)")
        for action in step.get("actions", []) or []:
            if "action" in action:
                for inst in expand_action(action, library):
                    trace.append({**inst, "phase": phase})
            elif "op" in action:
                inst = dict(action)
                if "seconds" in inst and "seconds_override" not in inst:
                    inst["seconds_override"] = inst.pop("seconds")
                inst["phase"] = phase
                trace.append(inst)
            else:
                raise KlmError(f"Action entry needs 'action' or 'op': {action}")
        if "ops" in step:
            for inst in parse_shorthand(step["ops"]):
                trace.append({**inst, "phase": phase})
    return trace, warnings


def score_flow(flow_doc, base_dir, library, persona_override=None):
    persona = persona_override or flow_doc.get("persona", "intermediate")
    device = flow_doc.get("device", "desktop")
    first_use = bool(flow_doc.get("first_use", False))

    trace, warnings = resolve_steps(
        flow_doc.get("steps", []), base_dir, library, persona, device, first_use, frozenset(),
    )

    total = 0.0
    by_phase = {}
    by_op = {}
    measured_r = 0.0
    assumed_r = 0.0
    scored_trace = []
    for inst in trace:
        secs, basis = operator_seconds(inst, persona, first_use)
        total += secs
        by_phase[inst["phase"]] = by_phase.get(inst["phase"], 0.0) + secs
        by_op[inst["op"]] = by_op.get(inst["op"], 0.0) + secs
        if inst["op"] == "R":
            if inst.get("source") == "measured":
                measured_r += secs
            else:
                assumed_r += secs
        scored_trace.append({**inst, "seconds": round(secs, 3), "basis": basis})

    return {
        "name": flow_doc.get("name", "(unnamed flow)"),
        "persona": persona,
        "device": device,
        "total_seconds": round(total, 3),
        "by_phase": {k: round(v, 3) for k, v in by_phase.items()},
        "by_operator": {k: round(v, 3) for k, v in by_op.items()},
        "measured_r_seconds": round(measured_r, 3),
        "assumed_r_seconds": round(assumed_r, 3),
        "trace": scored_trace,
        "warnings": warnings,
    }


# --- Comparison + economics ---

def score_comparison(comp_doc, base_dir, library):
    baseline_path = os.path.normpath(os.path.join(base_dir, comp_doc["baseline"]))
    proposed_path = os.path.normpath(os.path.join(base_dir, comp_doc["proposed"]))
    baseline_doc = load_yaml(baseline_path)
    proposed_doc = load_yaml(proposed_path)

    baseline = score_flow(baseline_doc, os.path.dirname(baseline_path), library)
    proposed = score_flow(proposed_doc, os.path.dirname(proposed_path), library)

    # Sensitivity bounds: re-score both flows forced to expert/novice persona
    bounds = {}
    for label in ("expert", "novice"):
        b = score_flow(baseline_doc, os.path.dirname(baseline_path), library, persona_override=label)
        p = score_flow(proposed_doc, os.path.dirname(proposed_path), library, persona_override=label)
        bounds[label] = round(b["total_seconds"] - p["total_seconds"], 3)

    time_saved_seconds = round(baseline["total_seconds"] - proposed["total_seconds"], 3)
    low, high = sorted([bounds["expert"], bounds["novice"]])

    result = {
        "name": comp_doc.get("name", "(unnamed comparison)"),
        "baseline": baseline,
        "proposed": proposed,
        "time_saved_seconds_per_task": time_saved_seconds,
        "time_saved_sensitivity_range_seconds": {"low": low, "high": high},
    }

    econ = comp_doc.get("economics")
    if econ:
        wage = econ["wage_per_hour"]
        num_users = econ["num_users"]
        freq = econ.get("frequency_per_year", baseline_doc.get("frequency_per_year"))
        if freq is None:
            raise KlmError("economics.frequency_per_year (or flow-level frequency_per_year) is required")

        def rollup(saved_seconds):
            hours_per_person_year = saved_seconds * freq / 3600.0
            cost_per_person_year = hours_per_person_year * wage
            return {
                "hours_saved_per_person_per_year": round(hours_per_person_year, 2),
                "cost_saved_per_person_per_year": round(cost_per_person_year, 2),
                "hours_saved_per_org_per_year": round(hours_per_person_year * num_users, 2),
                "cost_saved_per_org_per_year": round(cost_per_person_year * num_users, 2),
            }

        result["economics"] = {
            "wage_per_hour": wage,
            "currency": econ.get("currency", "USD"),
            "num_users": num_users,
            "frequency_per_year": freq,
            "scope": econ.get("scope", "internal_tool"),
            "point_estimate": rollup(time_saved_seconds),
            "low_estimate": rollup(low),
            "high_estimate": rollup(high),
        }

    calib = comp_doc.get("calibration")
    if calib:
        result["calibration"] = build_calibration_report(baseline, calib)

    return result


def build_calibration_report(scored_flow, calib):
    actual = calib["actual_median_seconds"]
    model = scored_flow["total_seconds"]
    delta = round(actual - model, 3)

    if delta >= 0:
        guidance = (
            "Real users are slower than the model (expected — KLM models expert, error-free "
            "performance, so it's a floor, not a prediction of the median). Check assumed R "
            f"(system response) time first: {scored_flow['assumed_r_seconds']:.2f}s of this "
            "estimate is unmeasured — get real timing data before attributing further. "
            "Remaining gap is most likely additional decision/search time KLM doesn't model, "
            "or first-use unfamiliarity if this flow wasn't marked first_use: true."
        )
    else:
        guidance = (
            "Real users are FASTER than the model, which shouldn't happen against an "
            "expert-floor estimate — treat this as a data-quality flag, not a real result. "
            "Likely causes: the analytics event boundaries don't match the modeled task "
            "start/end (e.g. actual timing excludes a step the model includes), the actual "
            "figure is a mean pulled down by a differently-scoped cohort, or the model's "
            "operator defaults are too conservative for this population and should be "
            "recalibrated against measured data."
        )

    return {
        "model_seconds": model,
        "actual_median_seconds": actual,
        "actual_source": calib.get("actual_source", "(source not stated)"),
        "delta_seconds": delta,
        "measured_r_seconds_in_model": scored_flow["measured_r_seconds"],
        "assumed_r_seconds_in_model": scored_flow["assumed_r_seconds"],
        "guidance": guidance,
    }


# --- Reporting ---

def format_flow_report(scored):
    lines = [f"=== {scored['name']} ===", f"persona: {scored['persona']}  device: {scored['device']}", ""]
    lines.append(f"Total estimated time: {scored['total_seconds']:.2f}s")
    lines.append("")
    lines.append("By phase:")
    for phase, secs in scored["by_phase"].items():
        lines.append(f"  {phase}: {secs:.2f}s")
    lines.append("")
    lines.append("By operator:")
    for op, secs in scored["by_operator"].items():
        lines.append(f"  {op}: {secs:.2f}s")
    if scored["warnings"]:
        lines.append("")
        lines.append("Warnings:")
        for w in scored["warnings"]:
            lines.append(f"  - {w}")
    return "\n".join(lines)


def format_comparison_report(result):
    lines = [f"=== {result['name']} ===", ""]
    lines.append(f"Baseline ({result['baseline']['name']}): {result['baseline']['total_seconds']:.2f}s")
    lines.append(f"Proposed ({result['proposed']['name']}): {result['proposed']['total_seconds']:.2f}s")
    lines.append(f"Time saved per task: {result['time_saved_seconds_per_task']:.2f}s")
    r = result["time_saved_sensitivity_range_seconds"]
    lines.append(f"Sensitivity range (expert–novice persona bounds): {r['low']:.2f}s to {r['high']:.2f}s")
    lines.append("")

    if "economics" in result:
        e = result["economics"]
        lines.append(f"Economics (scope: {e['scope']}, {e['num_users']} users, "
                      f"{e['frequency_per_year']}x/year, ${e['wage_per_hour']}/hr):")
        pe = e["point_estimate"]
        lines.append(f"  Point estimate — per person/year: {pe['hours_saved_per_person_per_year']:.2f} hrs "
                      f"({e['currency']} {pe['cost_saved_per_person_per_year']:.2f})")
        lines.append(f"  Point estimate — per org/year: {pe['hours_saved_per_org_per_year']:.2f} hrs "
                      f"({e['currency']} {pe['cost_saved_per_org_per_year']:.2f})")
        lo, hi = e["low_estimate"], e["high_estimate"]
        lines.append(f"  Range — per org/year: {e['currency']} {lo['cost_saved_per_org_per_year']:.2f} "
                      f"to {e['currency']} {hi['cost_saved_per_org_per_year']:.2f}")
        lines.append("")

    if "calibration" in result:
        c = result["calibration"]
        lines.append("Calibration vs. real data:")
        lines.append(f"  Model estimate: {c['model_seconds']:.2f}s")
        lines.append(f"  Actual median: {c['actual_median_seconds']:.2f}s  (source: {c['actual_source']})")
        lines.append(f"  Delta: {c['delta_seconds']:.2f}s")
        lines.append(f"  Assumed R time in model: {c['assumed_r_seconds_in_model']:.2f}s "
                      f"(measured: {c['measured_r_seconds_in_model']:.2f}s)")
        lines.append(f"  {c['guidance']}")

    return "\n".join(lines)


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description="KLM calculator")
    parser.add_argument("mode", choices=["flow", "compare"])
    parser.add_argument("file")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--action-library", default=DEFAULT_ACTION_LIBRARY)
    args = parser.parse_args()

    library = load_action_library(args.action_library)
    base_dir = os.path.dirname(os.path.abspath(args.file))

    try:
        if args.mode == "flow":
            doc = load_yaml(args.file)
            result = score_flow(doc, base_dir, library)
            print(json.dumps(result, indent=2) if args.json else format_flow_report(result))
        else:
            doc = load_yaml(args.file)
            result = score_comparison(doc, base_dir, library)
            print(json.dumps(result, indent=2) if args.json else format_comparison_report(result))
    except KlmError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
