#!/usr/bin/env python3
"""Free, deterministic proof that BackendWrapper (a) sees the FULL accumulated
history on every call, and (b) with the identity transform is a byte-for-byte
no-op. Uses a fake backend — no API cost. Run: python tools/test_backend_wrapper.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root for fbbench
from backend_wrapper import BackendWrapper                      # noqa: E402
from fbbench.runner.backends.base import Completion, ToolCall, ToolResult  # noqa: E402


class FakeBackend:
    model = "fake-model"

    def __init__(self):
        self.seen = []

    def complete(self, system, messages, tools, max_tokens):
        # Record EXACTLY what we were handed, to assert the wrapper forwards it.
        self.seen.append((system, messages, tools, max_tokens))
        return Completion(text="ok", input_tokens=len(messages),
                          output_tokens=1, cache_read_tokens=0,
                          cache_write_tokens=0)


def history(n_turns: int) -> list[dict]:
    """Neutral history after n completed turns: seed user + n (assistant, tool)."""
    msgs: list[dict] = [{"role": "user", "content": "start"}]
    for i in range(n_turns):
        msgs.append({"role": "assistant", "text": f"turn {i}",
                     "tool_calls": [ToolCall(id=f"t{i}", name="read_file",
                                             input={"path": "a"})]})
        msgs.append({"role": "tool",
                     "results": [ToolResult(id=f"t{i}", name="read_file",
                                            content="X" * 100)],
                     "note": "[budget]"})
    return msgs


def main() -> int:
    fake = FakeBackend()
    log = str(Path(tempfile.gettempdir()) / "wrap_test.jsonl")
    w = BackendWrapper(fake, log_path=log)

    assert w.model == "fake-model", "must expose inner .model (Protocol)"

    # Simulate the loop calling complete() as history grows: 0, 2, 4 turns.
    for n in (0, 2, 4):
        msgs = history(n)
        comp = w.complete("SYS", msgs, [{"name": "read_file"}], 65536)
        seen_sys, seen_msgs, seen_tools, seen_mt = fake.seen[-1]
        # (b) pass-through: inner got the SAME objects, unchanged
        assert seen_sys == "SYS", "system altered"
        assert seen_msgs is msgs, "messages not forwarded identically"
        assert seen_mt == 65536, "max_tokens altered"
        assert comp.text == "ok", "Completion not returned unchanged"
    w.close()

    # (a) the log proves the wrapper saw the full, growing history each call
    recs = [json.loads(line) for line in open(log)]
    n_messages = [r["n_messages"] for r in recs]
    assert n_messages == [1, 5, 9], f"expected growing history, got {n_messages}"
    assert all(r["unchanged"] for r in recs), "identity transform must be a no-op"

    print("PASS — BackendWrapper scaffold verified:")
    print(f"  • sees FULL history each call (n_messages per call: {n_messages})")
    print("  • identity transform is a byte-for-byte no-op (unchanged=True all calls)")
    print("  • forwards same objects to inner backend; Completion returned as-is")
    print(f"  log: {log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
