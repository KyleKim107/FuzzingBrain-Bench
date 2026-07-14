#!/usr/bin/env python3
"""Pass-through Backend wrapper — the shim seam for cost levers (Kyle, thesis).

Implements the fbbench `Backend` Protocol (fbbench/runner/backends/base.py) by
wrapping a real backend. Each episode turn the runner calls
`.complete(system, messages, tools, max_tokens)`; this wrapper sees the FULL
accumulated neutral history every time, optionally rewrites it via a `transform`
(a cost lever), forwards to the inner backend, and logs what it saw.

With the default identity transform it is a provable no-op: the inner backend
receives the SAME objects and its Completion is returned unchanged — wrapping
never alters an episode. A lever plugs in as
`transform(system, messages, tools) -> (system, messages, tools)`; nothing else
in the loop changes. Standalone: does NOT import or edit the fbbench package
(duck-typed on `.model` / `.complete`), so it stays a separable thesis artifact.

Neutral message shapes (base.py):
  {"role":"user","content":str}
  {"role":"assistant","text":str,"tool_calls":[ToolCall...]}
  {"role":"tool","results":[ToolResult...], "note"?:str}
"""
from __future__ import annotations

import json
import time
from typing import Callable

Transform = Callable[[str, list, list], tuple]


def identity(system, messages, tools):
    """The no-op lever: forward everything untouched (same objects)."""
    return system, messages, tools


def _attr(x, name, default=None):
    """Read a field from a dict OR a dataclass (ToolCall/ToolResult)."""
    if isinstance(x, dict):
        return x.get(name, default)
    return getattr(x, name, default)


def _msg_chars(m) -> int:
    """Char-mass of one neutral message (role-aware, same accounting as measure)."""
    role = _attr(m, "role")
    if role == "user":
        return len(_attr(m, "content") or "")
    if role == "assistant":
        c = len(_attr(m, "text") or "")
        for tc in (_attr(m, "tool_calls") or []):
            c += (len(_attr(tc, "name", "") or "")
                  + len(json.dumps(_attr(tc, "input", {}), default=str)))
        return c
    if role == "tool":
        c = sum(len(_attr(r, "content", "") or "")
                for r in (_attr(m, "results") or []))
        return c + len(_attr(m, "note", "") or "")
    return 0


def measure(system, messages, tools) -> dict:
    """Char-mass of one prompt by category — the same buckets context_growth
    uses, but computed live on the neutral history the wrapper is handed."""
    chars = {"system": len(system or ""),
             "tools": len(json.dumps(tools, default=str)),
             "user": 0, "assistant": 0, "tool": 0}
    roles: dict[str, int] = {}
    for m in messages:
        role = _attr(m, "role")
        roles[role] = roles.get(role, 0) + 1
        if role in chars:
            chars[role] += _msg_chars(m)
    return {"n_messages": len(messages), "roles": roles,
            "chars": chars, "total_chars": sum(chars.values())}


class BackendWrapper:
    """Wrap a backend; forward `.complete()` (optionally through a lever)."""

    def __init__(self, inner, transform: Transform = identity,
                 log_path: str | None = None):
        self.inner = inner
        self.model = inner.model            # Protocol requires a .model attr
        self._transform = transform
        self._call = 0
        self._fp = open(log_path, "w") if log_path else None
        # Post-transform history from the previous call, for cache-break detection.
        self._prev_msgs: list | None = None

    def _cache_break(self, cur: list) -> dict:
        """Where does this turn's post-transform prefix first diverge from last
        turn's? Baseline history is append-only, so an unbroken prefix means the
        provider's prompt cache stays valid and only the new tail is (re)written.
        A lever that rewrites an OLD message shifts the divergence earlier => the
        cache from that point must be re-written (1.25x) => a real cost the pure
        token count hides. `at` is the message index of first divergence (None if
        only the tail grew); `chars_after` estimates the re-written mass."""
        prev = self._prev_msgs
        if prev is None:
            return {"at": None, "chars_after": 0}
        for i in range(min(len(prev), len(cur))):
            if prev[i] != cur[i]:
                return {"at": i, "chars_after": sum(_msg_chars(m) for m in cur[i:])}
        return {"at": None, "chars_after": 0}

    def complete(self, system, messages, tools, max_tokens):
        self._call += 1
        pre = measure(system, messages, tools)
        system2, messages2, tools2 = self._transform(system, messages, tools)
        post = measure(system2, messages2, tools2)
        brk = self._cache_break(messages2)
        t0 = time.time()
        comp = self.inner.complete(system2, messages2, tools2, max_tokens)
        dt = time.time() - t0
        self._prev_msgs = messages2
        self._log(pre, post, comp, brk, dt)
        return comp

    def _log(self, pre, post, comp, brk, dt) -> None:
        if not self._fp:
            return
        self._fp.write(json.dumps({
            "call": self._call,
            "n_messages": pre["n_messages"], "roles": pre["roles"],
            "chars_pre": pre["total_chars"], "chars_post": post["total_chars"],
            "chars_removed": pre["total_chars"] - post["total_chars"],
            # true when the lever changed nothing (identity => always True)
            "unchanged": pre["total_chars"] == post["total_chars"],
            # cache-break: where the lever forced a prefix re-write (None = clean)
            "cache_break_at": brk["at"],
            "chars_after_break": brk["chars_after"],
            "input_tokens": getattr(comp, "input_tokens", 0),
            "output_tokens": getattr(comp, "output_tokens", 0),
            "cache_read_tokens": getattr(comp, "cache_read_tokens", 0),
            "cache_write_tokens": getattr(comp, "cache_write_tokens", 0),
            "stop_reason": getattr(comp, "stop_reason", ""),
            "n_tool_calls": len(getattr(comp, "tool_calls", []) or []),
            "duration_s": round(dt, 3),
        }) + "\n")
        self._fp.flush()

    def close(self) -> None:
        if self._fp:
            self._fp.close()
            self._fp = None
