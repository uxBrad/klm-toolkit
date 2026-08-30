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

STEP_LABEL_FIELD = {
    "fill_text_field": ("field", "Enter {}"),
    "click_button": ("label", 'Click "{}"'),
    "select_dropdown": ("field", "Select {}"),
    "toggle_checkbox": ("field", "Toggle {}"),
    "drag_and_drop": ("label", "Drag {}"),
    "scroll_and_read": ("field", "Read {}"),
    "tap": ("label", 'Tap "{}"'),
    "long_press": ("label", 'Long-press "{}"'),
    "swipe": (None, "Swipe"),
    "thumb_reach_home": (None, "Reposition grip"),
}


def step_label_for_action(name, action):
    param, template = STEP_LABEL_FIELD.get(name, (None, name.replace("_", " ").capitalize()))
    if param and param in action:
        return template.format(action[param])
    return template


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

    step_label = step_label_for_action(name, action)
    out = []
    for step in spec.get("sequence", []):
        op = step["op"]
        if op == "M" and step.get("condition") == "auto_mental_prep":
            if not use_mp:
                continue
            out.append({"op": "M", "reason": f"{name}: auto mental-prep (Rule 0/4)", "step": step_label})
            continue
        inst = {"op": op, "reason": name, "step": step_label}
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
                default_step = {"R": "System responds", "M": "Decide"}.get(inst["op"], phase)
                reason = inst.get("reason")
                inst.setdefault("step", reason[0].upper() + reason[1:] if reason else default_step)
                inst["phase"] = phase
                trace.append(inst)
            else:
                raise KlmError(f"Action entry needs 'action' or 'op': {action}")
        if "ops" in step:
            for inst in parse_shorthand(step["ops"]):
                inst.setdefault("step", phase)
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


def summary_bounds(result):
    """Worst/average/best case time (and cost, if economics present), for both report formats."""
    r = result["time_saved_sensitivity_range_seconds"]
    avg = result["time_saved_seconds_per_task"]
    out = {"time": {"worst": min(r["low"], r["high"], avg), "average": avg,
                     "best": max(r["low"], r["high"], avg)}}
    if "economics" in result:
        e = result["economics"]
        pe, lo, hi = e["point_estimate"], e["low_estimate"], e["high_estimate"]

        def bounds(field):
            vals = [lo[field], hi[field], pe[field]]
            return {"worst": min(vals), "average": pe[field], "best": max(vals)}

        out["cost_per_person_year"] = bounds("cost_saved_per_person_per_year")
        out["cost_per_org_year"] = bounds("cost_saved_per_org_per_year")
    return out


def format_comparison_report(result):
    lines = [f"=== {result['name']} ===", ""]
    lines.append(f"Baseline ({result['baseline']['name']}): {result['baseline']['total_seconds']:.2f}s")
    lines.append(f"Proposed ({result['proposed']['name']}): {result['proposed']['total_seconds']:.2f}s")
    lines.append("")

    sb = summary_bounds(result)
    t = sb["time"]
    lines.append(f"Time saved per task — worst case: {t['worst']:.2f}s, "
                  f"average: {t['average']:.2f}s, best case: {t['best']:.2f}s")

    if "economics" in result:
        e = result["economics"]
        pp, org = sb["cost_per_person_year"], sb["cost_per_org_year"]
        lines.append(f"Economics (scope: {e['scope']}, {e['num_users']} users, "
                      f"{e['frequency_per_year']}x/year, ${e['wage_per_hour']}/hr):")
        lines.append(f"  Cost saved per person/year — worst case: {e['currency']} {pp['worst']:.2f}, "
                      f"average: {e['currency']} {pp['average']:.2f}, best case: {e['currency']} {pp['best']:.2f}")
        lines.append(f"  Cost saved per org/year — worst case: {e['currency']} {org['worst']:.2f}, "
                      f"average: {e['currency']} {org['average']:.2f}, best case: {e['currency']} {org['best']:.2f}")
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


def shorthand_token(inst):
    op = inst["op"]
    if op == "K":
        count = inst.get("count", 1)
        return f"K*{count}" if count != 1 else "K"
    if op == "W":
        count = inst.get("count", 1)
        return f"W{count}"
    if op == "R":
        return f"R{inst['seconds']:g}"
    return op


def group_trace_by_step(trace):
    """Group a scored operator trace into one row per step (action instance),
    preserving first-seen order."""
    rows = []
    index_by_key = {}
    for inst in trace:
        key = (inst["phase"], inst.get("step", inst["phase"]))
        if key not in index_by_key:
            index_by_key[key] = len(rows)
            rows.append({"phase": key[0], "step": key[1], "tokens": [], "seconds": 0.0})
        row = rows[index_by_key[key]]
        row["tokens"].append(shorthand_token(inst))
        row["seconds"] += inst["seconds"]
    for row in rows:
        row["seconds"] = round(row["seconds"], 2)
    return rows


def format_flow_table(scored, heading=None):
    lines = [f"### {heading or scored['name']}", ""]
    lines.append(f"*persona: {scored['persona']}  ·  device: {scored['device']}*")
    lines.append("")
    lines.append("| Step | KLM operators | Time (s) |")
    lines.append("|---|---|---|")
    current_phase = None
    for row in group_trace_by_step(scored["trace"]):
        if row["phase"] != current_phase:
            current_phase = row["phase"]
            lines.append(f"| **{current_phase}** | | |")
        lines.append(f"| {row['step']} | `{' '.join(row['tokens'])}` | {row['seconds']:.2f} |")
    lines.append(f"| **Total** | | **{scored['total_seconds']:.2f}** |")
    return "\n".join(lines)


def format_comparison_tables(result):
    lines = [f"## {result['name']}", ""]
    lines.append(format_flow_table(result["baseline"], heading=f"Current: {result['baseline']['name']}"))
    lines.append("")
    lines.append(format_flow_table(result["proposed"], heading=f"Proposed: {result['proposed']['name']}"))
    lines.append("")
    lines.append("### Summary")
    lines.append("")
    lines.append("| | Current | Proposed |")
    lines.append("|---|---|---|")
    b, p = result["baseline"]["total_seconds"], result["proposed"]["total_seconds"]
    lines.append(f"| Time per task | {b:.2f}s | {p:.2f}s |")
    lines.append("")

    sb = summary_bounds(result)
    t = sb["time"]
    lines.append("| Saved | Worst case | Average | Best case |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| Per task | {t['worst']:.2f}s | **{t['average']:.2f}s** | {t['best']:.2f}s |")

    if "economics" in result:
        e = result["economics"]
        pp, org = sb["cost_per_person_year"], sb["cost_per_org_year"]
        lines.append(f"| Per person/year | {e['currency']} {pp['worst']:.2f} | "
                      f"**{e['currency']} {pp['average']:.2f}** | {e['currency']} {pp['best']:.2f} |")
        lines.append(f"| Per org/year | {e['currency']} {org['worst']:.2f} | "
                      f"**{e['currency']} {org['average']:.2f}** | {e['currency']} {org['best']:.2f} |")
        lines.append("")
        lines.append(f"*Basis: {e['num_users']} users × {e['frequency_per_year']}x/year × "
                      f"${e['wage_per_hour']}/hr ({e['scope']}). Worst/best case from expert<->novice "
                      f"persona bounds; average uses the flow's stated persona "
                      f"({result['baseline']['persona']}).*")
    else:
        lines.append("")
        lines.append(f"*Worst/best case from expert<->novice persona bounds; average uses the flow's "
                      f"stated persona ({result['baseline']['persona']}).*")

    if "calibration" in result:
        c = result["calibration"]
        lines.append("")
        lines.append(f"**Calibration vs. real data**: model {c['model_seconds']:.2f}s vs. actual median "
                      f"{c['actual_median_seconds']:.2f}s (source: {c['actual_source']}), "
                      f"delta {c['delta_seconds']:.2f}s. {c['guidance']}")

    return "\n".join(lines)


# --- SVG timeline visualization ---
#
# Renders the same kind of "steps on a clock" diagram as the KLM Toolkit
# blog writeup: one horizontal lane per flow, a shared time ruler, icon
# badges at each phase's midpoint (icon chosen by that phase's dominant
# KLM operator, not by domain guesswork), and — for a comparison — a
# third "Time saved" lane bridging the two END points. Self-contained
# SVG (no external stylesheet dependency) so it works standalone.

SVG_COLORS = {
    "baseline": "#595959",   # neutral/muted — the slower flow
    "proposed": "#0B5FFF",   # accent — the faster flow / the win
    "surface": "#ffffff",
    "circle_fill": "#f2f2f2",
    "grid": "#dddddd",
    "text_muted": "#767676",
}

SVG_MARGIN_LEFT = 220        # x for t=0 (START circle center)
SVG_PX_PER_SEC = 17
SVG_ICON_R = 18
SVG_CIRC_R = 20
SVG_END_CLEARANCE = 15       # min gap between last icon's edge and the END circle's edge
SVG_ICON_MIN_GAP = 46        # min center-to-center spacing between adjacent icons (icon diameter + breathing room)
SVG_LABEL_FONT = 10
SVG_LABEL_CHAR_PX = 5.6      # rough average glyph width at SVG_LABEL_FONT, for collision spacing
SVG_LABEL_GAP = 6

# op -> icon id, chosen by which KLM operator dominates a phase's time
SVG_OP_ICON = {
    "K": "type", "W": "read",
    "R": "clock",
    "P": "click", "H": "click", "D": "click", "T": "click", "TL": "click", "TH": "click",
    "M": "think",
    "SW": "swipe",
}

SVG_ICON_DEFS = """
    <g id="klm-icon-type">
      <rect x="-9" y="-6" width="18" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/>
      <rect x="-6.5" y="-3.5" width="2.5" height="2" fill="currentColor"/>
      <rect x="-2.5" y="-3.5" width="2.5" height="2" fill="currentColor"/>
      <rect x="1.5" y="-3.5" width="2.5" height="2" fill="currentColor"/>
      <rect x="5.5" y="-3.5" width="2.5" height="2" fill="currentColor"/>
      <rect x="-6.5" y="0.5" width="13" height="2" fill="currentColor"/>
    </g>
    <g id="klm-icon-click">
      <path d="M -5,-8 L -5,7 L -1.5,4 L 1,9.5 L 4,8 L 1.5,3 L 6,3 Z" fill="currentColor"/>
      <path d="M 7,-7 L 9.5,-9.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
      <path d="M 8.5,-3 L 11.5,-3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
    </g>
    <g id="klm-icon-clock">
      <circle cx="0" cy="0" r="8" fill="none" stroke="currentColor" stroke-width="1.8"/>
      <line x1="0" y1="0" x2="0" y2="-5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
      <line x1="0" y1="0" x2="3.2" y2="2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
    </g>
    <g id="klm-icon-think">
      <path d="M -6,-2 C -6,-6 -2,-8 0,-7 C 2,-8 6,-6 6,-2 C 6,1 4,2 4,4 C 4,6 2,7 0,7 C -2,7 -4,6 -4,4 C -4,2 -6,1 -6,-2 Z" fill="none" stroke="currentColor" stroke-width="1.6"/>
      <path d="M 0,-7 C 0,-4 -1,-3 0,-1 C 1,1 0,3 0,7" fill="none" stroke="currentColor" stroke-width="1.2"/>
    </g>
    <g id="klm-icon-read">
      <path d="M -8,0 C -8,-4 -3,-7 0,-7 C 3,-7 8,-4 8,0 C 8,4 3,7 0,7 C -3,7 -8,4 -8,0 Z" fill="none" stroke="currentColor" stroke-width="1.6"/>
      <circle cx="0" cy="0" r="2.4" fill="currentColor"/>
    </g>
    <g id="klm-icon-swipe">
      <path d="M -7,2 C -3,-5 3,-5 6,-1" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
      <path d="M 3,-4 L 6,-1 L 2,1" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
    </g>
"""


def dominant_icon(op_seconds):
    if not op_seconds:
        return "click"
    best_op = max(op_seconds, key=op_seconds.get)
    return SVG_OP_ICON.get(best_op, "click")


def phase_timeline(scored):
    """Walk a scored flow's trace into ordered phases with cumulative
    start/mid/end times and a per-phase dominant-operator icon.
    Mirrors the same contiguous-phase assumption format_flow_table uses."""
    phases = []
    cum = 0.0
    cur = None
    for inst in scored["trace"]:
        secs = inst["seconds"]
        ph = inst["phase"]
        if cur is None or cur["phase"] != ph:
            cur = {"phase": ph, "start": cum, "end": cum, "op_seconds": {}}
            phases.append(cur)
        cur["end"] = cum + secs
        cur["op_seconds"][inst["op"]] = cur["op_seconds"].get(inst["op"], 0.0) + secs
        cum += secs
    for p in phases:
        p["mid"] = (p["start"] + p["end"]) / 2.0
        p["icon"] = dominant_icon(p["op_seconds"])
    return phases


def _spread(positions, min_gaps):
    """Left-to-right sweep: push each position right just enough to keep
    at least min_gaps[i] clearance from the previous one. Preserves order,
    never moves anything left."""
    out = list(positions)
    for i in range(1, len(out)):
        need = out[i - 1] + min_gaps[i]
        if out[i] < need:
            out[i] = need
    return out


def _label_positions(centers, labels):
    half_widths = [len(t) * SVG_LABEL_FONT * SVG_LABEL_CHAR_PX / 10.0 / 2.0 for t in labels]
    min_gaps = [0.0] + [half_widths[i - 1] + half_widths[i] + SVG_LABEL_GAP for i in range(1, len(centers))]
    return _spread(centers, min_gaps)


def _text_width(text, font_px):
    """Rough average glyph-width estimate for collision/margin math — not
    exact metrics, just enough to keep labels from overlapping each other
    or running off the canvas edge."""
    return len(text) * font_px * 0.56


def row_label_x0(names):
    """Left margin (t=0 x-position) big enough that the longest row label,
    right-aligned just before the START circle, doesn't clip off the left
    edge of the canvas."""
    widest = max((_text_width(n, 15) for n in names), default=0)
    return max(SVG_MARGIN_LEFT, int(widest + 60))


def _lane_layout(scored, x0):
    """Compute icon x-positions (collision-avoided), the END x (pushed
    right past the last icon if needed — 'continue the line' rather than
    let the END badge crowd the last icon), and phase label x-positions."""
    phases = phase_timeline(scored)
    raw_x = [x0 + p["mid"] * SVG_PX_PER_SEC for p in phases]
    icon_x = _spread(raw_x, [0.0] + [SVG_ICON_MIN_GAP] * (len(raw_x) - 1))
    real_end_x = x0 + scored["total_seconds"] * SVG_PX_PER_SEC
    min_end_x = (icon_x[-1] + SVG_ICON_R + SVG_CIRC_R + SVG_END_CLEARANCE) if icon_x else real_end_x
    end_x = max(real_end_x, min_end_x)
    labels = [p["phase"] for p in phases]
    label_x = _label_positions(list(icon_x), labels)
    return {"phases": phases, "icon_x": icon_x, "label_x": label_x, "end_x": end_x}


def _lane_svg(scored, x0, y, color, name):
    layout = _lane_layout(scored, x0)
    end_x = layout["end_x"]
    parts = [f'  <text x="{x0-40}" y="{y+5}" text-anchor="end" font-size="15" font-weight="600" fill="{color}">{name}</text>']
    parts.append(f'  <g color="{color}">')
    parts.append(f'    <line x1="{x0}" y1="{y}" x2="{end_x:.1f}" y2="{y}" stroke="currentColor" stroke-width="2"/>')
    parts.append(f'    <circle cx="{x0}" cy="{y}" r="{SVG_CIRC_R}" fill="{SVG_COLORS["circle_fill"]}" stroke="currentColor" stroke-width="1.5"/>')
    parts.append(f'    <text x="{x0}" y="{y+4}" text-anchor="middle" font-size="9" fill="currentColor">START</text>')
    parts.append(f'    <circle cx="{end_x:.1f}" cy="{y}" r="{SVG_CIRC_R}" fill="{SVG_COLORS["circle_fill"]}" stroke="currentColor" stroke-width="1.5"/>')
    parts.append(f'    <text x="{end_x:.1f}" y="{y+4}" text-anchor="middle" font-size="9" fill="currentColor">END</text>')
    parts.append(f'    <text x="{end_x:.1f}" y="{y+40}" text-anchor="middle" font-size="14" font-weight="700" fill="currentColor">{scored["total_seconds"]:.2f}s</text>')
    # icon badges sit 40px above the baseline, phase-name labels sit below it —
    # keeps both legible without the label crowding the icon it names.
    icon_cy, icon_bottom, label_y = y - 40, y - 22, y + 18
    for x, lx, p in zip(layout["icon_x"], layout["label_x"], layout["phases"]):
        parts.append(f'    <line x1="{x:.1f}" y1="{icon_bottom}" x2="{x:.1f}" y2="{y}" stroke="currentColor" stroke-width="1.5"/>')
        parts.append(f'    <g transform="translate({x:.1f},{icon_cy})"><circle r="{SVG_ICON_R}" fill="{SVG_COLORS["surface"]}" stroke="currentColor" stroke-width="2"/><use href="#klm-icon-{p["icon"]}"/></g>')
        parts.append(f'    <text x="{lx:.1f}" y="{label_y}" text-anchor="middle" font-size="{SVG_LABEL_FONT}" fill="currentColor">{p["phase"]}</text>')
    parts.append("  </g>")
    return "\n".join(parts), end_x


def _svg_header(width, height, title, desc):
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-labelledby="klm-title klm-desc" '
        f'style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">\n'
        f'  <title id="klm-title">{title}</title>\n'
        f'  <desc id="klm-desc">{desc}</desc>\n'
        f'  <defs>{SVG_ICON_DEFS}  </defs>'
    )


def _svg_ruler(x0, width, top, bottom, max_seconds):
    step = 10 if max_seconds > 25 else 5
    ticks = []
    t = 0
    while t <= max_seconds + step:
        ticks.append(t)
        t += step
    lines, labels = [f'  <g stroke="{SVG_COLORS["grid"]}" stroke-width="1">'], [f'  <g fill="{SVG_COLORS["text_muted"]}" font-size="13" text-anchor="middle">']
    for t in ticks:
        x = x0 + t * SVG_PX_PER_SEC
        if x > width - 20:
            continue
        lines.append(f'    <line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}"/>')
        labels.append(f'    <text x="{x:.1f}" y="30">{t}s</text>')
    lines.append("  </g>")
    labels.append("  </g>")
    return "\n".join(lines) + "\n" + "\n".join(labels)


def build_flow_svg(scored):
    """Single-lane timeline for a bare (non-comparison) flow estimate."""
    x0 = row_label_x0([scored["name"]])
    layout_preview = _lane_layout(scored, x0)
    width = int(layout_preview["end_x"] + 60)
    height = 160
    y = 100
    svg = [_svg_header(width, height, f"Time-on-task: {scored['name']}",
                        f"{scored['name']} takes {scored['total_seconds']:.2f} seconds "
                        f"({scored['persona']} persona, {scored['device']}).")]
    svg.append(_svg_ruler(x0, width, 45, y + 20, scored["total_seconds"]))
    lane_svg, _ = _lane_svg(scored, x0, y, SVG_COLORS["baseline"], scored["name"])
    svg.append(lane_svg)
    svg.append("</svg>")
    return "\n".join(svg)


def build_comparison_svg(result):
    """Two-lane (baseline/proposed) or three-lane (+ time saved) timeline,
    matching the KLM Toolkit blog article's diagram style."""
    baseline, proposed = result["baseline"], result["proposed"]
    max_seconds = max(baseline["total_seconds"], proposed["total_seconds"])
    show_saved = result["time_saved_seconds_per_task"] > 0
    x0 = row_label_x0([baseline["name"], proposed["name"], "Time saved"])
    b_layout, p_layout = _lane_layout(baseline, x0), _lane_layout(proposed, x0)
    width = int(max(b_layout["end_x"], p_layout["end_x"]) + 60)
    height = 400 if show_saved else 290
    y_baseline, y_proposed, y_saved = 110, 230, 340

    svg = [_svg_header(
        width, height, f"Time-on-task comparison: {result['name']}",
        f"Baseline ({baseline['name']}) takes {baseline['total_seconds']:.2f}s. "
        f"Proposed ({proposed['name']}) takes {proposed['total_seconds']:.2f}s. "
        f"Time saved: {result['time_saved_seconds_per_task']:.2f}s per task."
    )]
    svg.append(_svg_ruler(x0, width, 45, (y_saved if show_saved else y_proposed) + 20, max_seconds))

    baseline_svg, baseline_end_x = _lane_svg(baseline, x0, y_baseline, SVG_COLORS["baseline"], baseline["name"])
    proposed_svg, proposed_end_x = _lane_svg(proposed, x0, y_proposed, SVG_COLORS["proposed"], proposed["name"])
    svg.append(baseline_svg)
    svg.append(proposed_svg)

    if show_saved:
        start_x, stop_x = sorted([baseline_end_x, proposed_end_x])
        svg.append(f'  <text x="{x0-40}" y="{y_saved+5}" text-anchor="end" font-size="15" font-weight="600" fill="{SVG_COLORS["proposed"]}">Time saved</text>')
        svg.append(f'  <g color="{SVG_COLORS["proposed"]}">')
        svg.append(f'    <line x1="{start_x:.1f}" y1="{y_saved}" x2="{stop_x:.1f}" y2="{y_saved}" stroke="currentColor" stroke-width="2"/>')
        svg.append(f'    <circle cx="{start_x:.1f}" cy="{y_saved}" r="{SVG_CIRC_R}" fill="{SVG_COLORS["circle_fill"]}" stroke="currentColor" stroke-width="1.5"/>')
        svg.append(f'    <text x="{start_x:.1f}" y="{y_saved+4}" text-anchor="middle" font-size="9" fill="currentColor">START</text>')
        svg.append(f'    <circle cx="{stop_x:.1f}" cy="{y_saved}" r="{SVG_CIRC_R}" fill="{SVG_COLORS["circle_fill"]}" stroke="currentColor" stroke-width="1.5"/>')
        svg.append(f'    <text x="{stop_x:.1f}" y="{y_saved+4}" text-anchor="middle" font-size="9" fill="currentColor">END</text>')
        svg.append(f'    <text x="{stop_x:.1f}" y="{y_saved+40}" text-anchor="middle" font-size="14" font-weight="700" fill="currentColor">{result["time_saved_seconds_per_task"]:.2f}s</text>')
        svg.append("  </g>")

    svg.append("</svg>")
    return "\n".join(svg)


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description="KLM calculator")
    parser.add_argument("mode", choices=["flow", "compare"])
    parser.add_argument("file")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--table", action="store_true", help="Output markdown step-by-step tables")
    parser.add_argument("--svg", action="store_true", help="Output an SVG timeline visualization (steps on a shared clock)")
    parser.add_argument("--svg-out", metavar="PATH", help="Write the SVG visualization to PATH instead of stdout (implies --svg)")
    parser.add_argument("--action-library", default=DEFAULT_ACTION_LIBRARY)
    args = parser.parse_args()
    want_svg = args.svg or args.svg_out
    want_default = not (args.json or args.table or want_svg)

    library = load_action_library(args.action_library)
    base_dir = os.path.dirname(os.path.abspath(args.file))

    try:
        if args.mode == "flow":
            doc = load_yaml(args.file)
            result = score_flow(doc, base_dir, library)
            if args.json:
                print(json.dumps(result, indent=2))
            if args.table:
                print(format_flow_table(result))
            if want_svg:
                svg = build_flow_svg(result)
                if args.svg_out:
                    with open(args.svg_out, "w") as f:
                        f.write(svg)
                    print(f"Wrote {args.svg_out}", file=sys.stderr)
                else:
                    print(svg)
            if want_default:
                print(format_flow_report(result))
        else:
            doc = load_yaml(args.file)
            result = score_comparison(doc, base_dir, library)
            if args.json:
                print(json.dumps(result, indent=2))
            if args.table:
                print(format_comparison_tables(result))
            if want_svg:
                svg = build_comparison_svg(result)
                if args.svg_out:
                    with open(args.svg_out, "w") as f:
                        f.write(svg)
                    print(f"Wrote {args.svg_out}", file=sys.stderr)
                else:
                    print(svg)
            if want_default:
                print(format_comparison_report(result))
    except KlmError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
