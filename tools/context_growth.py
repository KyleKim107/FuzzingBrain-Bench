#!/usr/bin/env python3
"""Context-growth + token-mass analyzer for a FuzzingBrain-Bench transcript.

Thesis tooling (Kyle) — deliberately standalone (stdlib only, no import of the
`fbbench` package) so it stays a separable artifact and never perturbs the
benchmark it measures. Input is one `transcript.jsonl` (or a run dir containing
one); the schema is fixed by fbbench/runner/episode.py's `tlog(...)` events.

It answers the two questions that decide WHICH cost lever has headroom:

  (A) Context-growth curve — per turn, the prompt the model was billed for
      (fresh input + cached-prefix read). Because the loop replays the FULL
      history every turn with no truncation, this grows monotonically; the
      curve is the visual motivation for lever #2 (pruning).

  (B) Content-mass decomposition — of the accumulated history at its LARGEST
      (final) turn, how many characters sit in each category:
        system / tools            — fixed, cached, no headroom
        assistant_text            — the model's own reasoning
        tool_result:grade         — crash / sanitizer reports  -> lever #1
        tool_result:read_file     — source dumps               -> lever #3
        tool_result:other         — setup / list_directory / exec / write_file
        notes                     — budget notes + nudges
      Whichever bucket dominates is where a lever can actually save tokens.

Billed tokens (A) are exact (recorded per assistant turn). Content mass (B) is
measured in characters (exact); an empirical chars-per-token ratio, derived from
this same transcript's final prompt, is used ONLY to annotate (B) with a rough
token estimate — it is labeled as an estimate, never billed.

Usage:
    python tools/context_growth.py <transcript.jsonl | run_dir> [--csv OUT.csv]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Category labels for the content-mass decomposition (B).
CATS = ["system", "tools", "assistant_text",
        "tool_result:grade", "tool_result:read_file", "tool_result:other",
        "notes"]


def _load(path: Path) -> list[dict]:
    events = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except ValueError:
            continue  # tolerate a partial last line on a live/crashed run
    return events


def _content_len(obj) -> int:
    """Char length of a tool result stored either as a parsed object or raw str
    (episode.py's `_payload_obj` stores JSON as an object when it parses)."""
    if obj is None:
        return 0
    if isinstance(obj, str):
        return len(obj)
    return len(json.dumps(obj, ensure_ascii=False))


def analyze(events: list[dict]) -> dict:
    # --- fixed prefix (system + tools), from the `start` event ---
    system_chars = tools_chars = 0
    initial_user_chars = 0
    for e in events:
        if e.get("event") == "start":
            system_chars = len(e.get("system_prompt", "") or "")
            tools_chars = len(json.dumps(e.get("tools", []), ensure_ascii=False))
            initial_user_chars = len(e.get("initial_user_message", "") or "")
            break

    # --- content mass by category (cumulative over the whole episode) ---
    # assistant_text and the initial user turn seed the running history; each
    # tool_result / note adds to it. We bucket tool results by the tool name.
    mass = {c: 0 for c in CATS}
    mass["system"] = system_chars
    mass["tools"] = tools_chars
    mass["assistant_text"] = initial_user_chars  # the seed user turn

    # --- per-turn billed-token curve (A), from `assistant` events ---
    curve: list[dict] = []
    for e in events:
        ev = e.get("event")
        if ev == "assistant":
            mass["assistant_text"] += len(e.get("text", "") or "")
            in_tok = e.get("input_tokens", 0) or 0
            cr = e.get("cache_read_tokens", 0) or 0
            cw = e.get("cache_write_tokens", 0) or 0
            out = e.get("output_tokens", 0) or 0
            curve.append({
                "turn": e.get("turn"),
                "input_tokens": in_tok,
                "cache_read_tokens": cr,
                "cache_write_tokens": cw,
                "output_tokens": out,
                # what the model was fed this turn = fresh input + cached prefix
                "prompt_tokens": in_tok + cr,
            })
        elif ev == "tool_result":
            n = _content_len(e.get("result"))
            tool = e.get("tool")
            if tool == "grade":
                mass["tool_result:grade"] += n
            elif tool == "read_file":
                mass["tool_result:read_file"] += n
            else:
                mass["tool_result:other"] += n
        elif ev == "budget_note":
            mass["notes"] += len(e.get("note", "") or "")

    total_chars = sum(mass.values())

    # --- empirical chars/token ratio from the LARGEST billed prompt ---
    # At the peak turn the reconstructed history ~ the whole content mass, so
    # (total content chars) / (that turn's prompt tokens) approximates chars/tok.
    peak = max((c["prompt_tokens"] for c in curve), default=0)
    ratio = (total_chars / peak) if peak else None

    return {
        "curve": curve,
        "mass": mass,
        "total_chars": total_chars,
        "chars_per_token": ratio,
        "peak_prompt_tokens": peak,
    }


def _bar(frac: float, width: int = 32) -> str:
    filled = int(round(frac * width))
    return "█" * filled + "·" * (width - filled)


def _spark(vals: list[int]) -> str:
    if not vals:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    return "".join(blocks[min(7, int((v - lo) / span * 7))] for v in vals)


def report(res: dict) -> None:
    curve, mass = res["curve"], res["mass"]
    ratio = res["chars_per_token"]

    # (A) context-growth curve
    print("\n=== (A) Context growth — billed prompt tokens per turn ===")
    if curve:
        prompts = [c["prompt_tokens"] for c in curve]
        first, last = prompts[0], prompts[-1]
        grow = f"{last / first:.1f}×" if first else "n/a"
        print(f"  turns: {len(curve)}   "
              f"turn0 prompt: {first:,}   peak: {max(prompts):,}   "
              f"growth turn0→last: {grow}")
        print(f"  {_spark(prompts)}")
        print(f"\n  {'turn':>4} {'prompt':>9} {'fresh_in':>9} "
              f"{'cache_rd':>9} {'cache_wr':>9} {'out':>8}")
        for c in curve:
            print(f"  {c['turn']:>4} {c['prompt_tokens']:>9,} "
                  f"{c['input_tokens']:>9,} {c['cache_read_tokens']:>9,} "
                  f"{c['cache_write_tokens']:>9,} {c['output_tokens']:>8,}")
    else:
        print("  (no assistant turns with token accounting)")

    # (B) content-mass decomposition
    print("\n=== (B) Content mass at largest context — where the tokens live ===")
    total = res["total_chars"] or 1
    order = sorted(CATS, key=lambda c: mass[c], reverse=True)
    tok_note = f"  (≈ {res['total_chars'] / ratio:,.0f} tok @ {ratio:.1f} ch/tok)" if ratio else ""
    print(f"  total: {res['total_chars']:,} chars{tok_note}")
    for c in order:
        frac = mass[c] / total
        est = f"  ≈{mass[c] / ratio:>8,.0f} tok" if ratio else ""
        print(f"  {c:<22} {_bar(frac)} {frac*100:5.1f}%  {mass[c]:>10,} ch{est}")

    # lever headroom hint
    lever_map = {"tool_result:grade": "lever #1 (structured diagnosis)",
                 "tool_result:read_file": "lever #3 (signal-aware truncation)",
                 "assistant_text": "lever #2 (pruning prior turns)"}
    top_movable = next((c for c in order if c in lever_map), None)
    if top_movable:
        print(f"\n  → biggest movable bucket: {top_movable} "
              f"({mass[top_movable]/total*100:.0f}%) → {lever_map[top_movable]}")


def write_csv(res: dict, out: Path) -> None:
    lines = ["turn,prompt_tokens,input_tokens,cache_read_tokens,"
             "cache_write_tokens,output_tokens"]
    for c in res["curve"]:
        lines.append(f"{c['turn']},{c['prompt_tokens']},{c['input_tokens']},"
                     f"{c['cache_read_tokens']},{c['cache_write_tokens']},"
                     f"{c['output_tokens']}")
    out.write_text("\n".join(lines) + "\n")
    print(f"\n  wrote per-turn curve → {out}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="transcript.jsonl or a run dir containing one")
    ap.add_argument("--csv", type=Path, help="write the per-turn curve to this CSV")
    args = ap.parse_args(argv)

    p = Path(args.path)
    if p.is_dir():
        p = p / "transcript.jsonl"
    if not p.is_file():
        print(f"error: no transcript at {p}", file=sys.stderr)
        return 2

    res = analyze(_load(p))
    report(res)
    if args.csv:
        write_csv(res, args.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
