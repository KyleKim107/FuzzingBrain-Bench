#!/usr/bin/env python3
"""Offline test of lever #1 (structured_diagnosis) against REAL grade results
pulled from a recorded transcript. No API / no $ spent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_wrapper import measure                      # noqa: E402
from levers import (distill_sanitizer, structured_diagnosis,  # noqa: E402
                    _is_sanitizer_report)
from fbbench.runner.backends.base import ToolCall, ToolResult  # noqa: E402

TRANSCRIPT = ("runs/wrapped/avro-03/claude-haiku-4-5/run-1/transcript.jsonl")


def load_grades():
    recs = [json.loads(l) for l in open(TRANSCRIPT)]
    return [r for r in recs if r.get("tool") == "grade" and "result" in r]


def main() -> int:
    grades = load_grades()
    assert grades, "no grade results found in transcript"

    # --- 1) distill_sanitizer on the real ASan report -----------------------
    print("=== distill_sanitizer on real grade results ===")
    total_raw = total_new = 0
    for g in grades:
        content = json.dumps({"harness_output": g["result"]["harness_output"]})
        raw = len(content)
        se = g["result"]["harness_output"].get("stderr", "") or ""
        is_san = _is_sanitizer_report(se)
        if is_san:
            d = distill_sanitizer(se)
            # idempotent
            assert distill_sanitizer(d) == d, "distill must be idempotent"
            # must retain the crash class + a source frame
            assert "Sanitizer:" in d, "lost the crash headline"
            assert "/src/" in d, "lost the target-source stack frame"
            # must drop the noise
            assert "BuildId" not in d, "BuildId noise survived"
            assert "0x" not in d.split("Sanitizer:")[0], "address noise survived"
            assert "INFO:" not in d and "fuzzer::" not in d, "harness noise survived"
        newc = json.dumps({"harness_output": {
            "exit_code": g["result"]["harness_output"].get("exit_code"),
            "signal": g["result"]["harness_output"].get("signal", ""),
            "stderr": distill_sanitizer(se) if is_san else se}})
        total_raw += raw
        total_new += len(newc)
        print(f"  turn {g['turn']:>2}  sanitizer={str(is_san):>5}  "
              f"{raw:>5} -> {len(newc):>5} chars")
    print(f"  TOTAL grade mass: {total_raw:,} -> {total_new:,} chars "
          f"({100*(total_raw-total_new)/total_raw:.0f}% smaller)")

    # show one distilled report in full
    big = max(grades, key=lambda g: len(g["result"]["harness_output"].get("stderr","") or ""))
    print(f"\n--- distilled report, turn {big['turn']} ---")
    print(distill_sanitizer(big["result"]["harness_output"]["stderr"]))

    # --- 2) structured_diagnosis on a neutral history (BOTH shapes) ---------
    print("\n=== structured_diagnosis on neutral messages ===")
    for shape in ("dataclass", "dict"):
        msgs = [{"role": "user", "content": "start"},
                {"role": "assistant", "text": "check",
                 "tool_calls": [ToolCall(id="a", name="read_file", input={})]},
                {"role": "tool", "results": [
                    ToolResult(id="a", name="read_file", content="FILE-BODY-KEEP")]}]
        for i, g in enumerate(grades):
            gc = json.dumps({"harness_output": g["result"]["harness_output"]})
            if shape == "dataclass":
                res = ToolResult(id=f"g{i}", name="grade", content=gc)
            else:
                res = {"id": f"g{i}", "name": "grade", "content": gc,
                       "is_error": False}
            msgs.append({"role": "tool", "results": [res]})

        _, out, _ = structured_diagnosis("SYS", msgs, [])
        pre, post = measure("SYS", msgs, []), measure("SYS", out, [])
        print(f"  [{shape}] chars {pre['total_chars']:,} -> {post['total_chars']:,}"
              f"  removed={pre['total_chars']-post['total_chars']:,}")
        # non-grade content preserved verbatim
        def _c(r):
            return r.get("content") if isinstance(r, dict) else r.content
        assert _c(out[2]["results"][0]) == "FILE-BODY-KEEP", "clobbered read_file!"
        # grade with sanitizer report was shrunk; clean/empty grade untouched
        for src_m, out_m in zip(msgs[3:], out[3:]):
            sr = src_m["results"][0]
            orr = out_m["results"][0]
            se = json.loads(_c(sr))["harness_output"].get("stderr", "") or ""
            if _is_sanitizer_report(se):
                assert len(_c(orr)) < len(_c(sr)), "sanitizer grade not shrunk"
            else:
                assert _c(orr) == _c(sr), "clean grade should be untouched"
        # inputs not mutated
        assert msgs[3]["results"][0] is not None
        assert post["total_chars"] < pre["total_chars"], "no net reduction?"

    # --- 3) idempotency at the transform level ------------------------------
    _, out1, _ = structured_diagnosis("SYS", msgs, [])
    _, out2, _ = structured_diagnosis("SYS", out1, [])
    assert measure("SYS", out1, []) == measure("SYS", out2, []), \
        "transform must be idempotent (cache-prefix stability)"
    print("\nidempotent at transform level ✅")

    print("\nALL ASSERTIONS PASSED ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
