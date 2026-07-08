#!/usr/bin/env python3
"""Aggregate a baseline batch into variance + generality tables.

Thesis tooling (Kyle). Walks an experiment dir (runs/<exp>/<bug>/<model>/run-*/),
reads each run's score.json and — via context_growth.analyze on its
transcript.jsonl — the peak billed prompt and the read_file share of the
accumulated context. Prints:

  (1) VARIANCE  — for any bug run more than once, the run-to-run spread of
      tier_score / cost / peak-context (the band a lever must beat, since
      sampling is temperature=1.0 and unseeded).
  (2) GENERALITY — one row per bug: is "read_file dominates the context" a
      general pattern or specific to one bug?

Usage:  python tools/baseline_summary.py runs/baseline [--model claude-haiku-4-5]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from context_growth import analyze, _load  # noqa: E402


def _pct(mass: dict, cat: str) -> float:
    tot = sum(mass.values()) or 1
    return mass.get(cat, 0) / tot * 100


def collect(exp_dir: Path, model: str | None) -> list[dict]:
    rows = []
    for score_path in sorted(exp_dir.glob("*/*/run-*/score.json")):
        run_dir = score_path.parent
        if model and run_dir.parent.name != model:
            continue
        s = json.loads(score_path.read_text())
        kb = set(s.get("config", {}).get("capability_set", []))
        fired = {k for k, v in s.get("capabilities", {}).items() if v == "fired"}
        row = {
            "bug": s.get("bug_id"), "run": run_dir.name,
            "tier": s.get("tier_score"),
            "solved": bool(kb) and kb.issubset(fired),
            "usd": s.get("total_usd"),
            "turns": s.get("turns_used"),
            "term": s.get("terminated_reason"),
            "peak_tok": None, "read_file_pct": None, "grade_pct": None,
        }
        tpath = run_dir / "transcript.jsonl"
        if tpath.is_file():
            res = analyze(_load(tpath))
            row["peak_tok"] = res["peak_prompt_tokens"]
            row["read_file_pct"] = _pct(res["mass"], "tool_result:read_file")
            row["grade_pct"] = _pct(res["mass"], "tool_result:grade")
        rows.append(row)
    return rows


def _fmt(v, spec=""):
    return "-" if v is None else format(v, spec)


def report(rows: list[dict]) -> None:
    by_bug: dict[str, list[dict]] = {}
    for r in rows:
        by_bug.setdefault(r["bug"], []).append(r)

    # (1) variance — bugs run more than once
    rep = {b: rs for b, rs in by_bug.items() if len(rs) > 1}
    print("\n=== (1) VARIANCE — repeated bug(s): run-to-run spread ===")
    if not rep:
        print("  (no bug was run more than once)")
    for bug, rs in rep.items():
        print(f"\n  {bug}  (n={len(rs)})")
        print(f"  {'run':>6} {'tier':>4} {'solved':>6} {'usd':>8} "
              f"{'turns':>5} {'peak_tok':>9} {'read%':>6} {'term':>16}")
        for r in rs:
            print(f"  {r['run']:>6} {_fmt(r['tier']):>4} "
                  f"{('Y' if r['solved'] else '·'):>6} {_fmt(r['usd'],'.3f'):>8} "
                  f"{_fmt(r['turns']):>5} {_fmt(r['peak_tok'],','):>9} "
                  f"{_fmt(r['read_file_pct'],'.0f'):>6} {_fmt(r['term']):>16}")
        for key, spec in [("tier", ".2f"), ("usd", ".3f"),
                          ("peak_tok", ",.0f"), ("turns", ".1f")]:
            vals = [r[key] for r in rs if r[key] is not None]
            if len(vals) > 1:
                mean = statistics.mean(vals)
                sd = statistics.stdev(vals)
                rng = f"{min(vals):g}–{max(vals):g}"
                print(f"    {key:<10} mean {mean:{spec}}  sd {sd:{spec}}  "
                      f"range {rng}  (±{sd/mean*100:.0f}% of mean)" if mean else
                      f"    {key:<10} mean {mean:{spec}}")

    # (2) generality — one row per bug (first run)
    print("\n=== (2) GENERALITY — is read_file the dominant bucket everywhere? ===")
    print(f"  {'bug':>16} {'tier':>4} {'usd':>8} {'peak_tok':>9} "
          f"{'read%':>6} {'grade%':>7} {'term':>16}")
    for bug, rs in by_bug.items():
        r = rs[0]
        print(f"  {bug:>16} {_fmt(r['tier']):>4} {_fmt(r['usd'],'.3f'):>8} "
              f"{_fmt(r['peak_tok'],','):>9} {_fmt(r['read_file_pct'],'.0f'):>6} "
              f"{_fmt(r['grade_pct'],'.0f'):>7} {_fmt(r['term']):>16}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exp_dir", help="e.g. runs/baseline")
    ap.add_argument("--model", default=None, help="filter to one model dir")
    args = ap.parse_args(argv)
    exp = Path(args.exp_dir)
    if not exp.is_dir():
        print(f"error: no dir {exp}", file=sys.stderr)
        return 2
    rows = collect(exp, args.model)
    if not rows:
        print("no runs found (still running?)", file=sys.stderr)
        return 1
    report(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
