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
        if role == "user":
            chars["user"] += len(_attr(m, "content") or "")
        elif role == "assistant":
            chars["assistant"] += len(_attr(m, "text") or "")
            for tc in (_attr(m, "tool_calls") or []):
                chars["assistant"] += (len(_attr(tc, "name", "") or "")
                                       + len(json.dumps(_attr(tc, "input", {}),
                                                        default=str)))
        elif role == "tool":
            for r in (_attr(m, "results") or []):
                chars["tool"] += len(_attr(r, "content", "") or "")
            chars["tool"] += len(_attr(m, "note", "") or "")
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

    def complete(self, system, messages, tools, max_tokens):
        self._call += 1
        pre = measure(system, messages, tools)
        system2, messages2, tools2 = self._transform(system, messages, tools)
        post = measure(system2, messages2, tools2)
        comp = self.inner.complete(system2, messages2, tools2, max_tokens)
        self._log(pre, post, comp)
        return comp

    def _log(self, pre, post, comp) -> None:
        if not self._fp:
            return
        self._fp.write(json.dumps({
            "call": self._call,
            "n_messages": pre["n_messages"], "roles": pre["roles"],
            "chars_pre": pre["total_chars"], "chars_post": post["total_chars"],
            # true when the lever changed nothing (identity => always True)
            "unchanged": pre["total_chars"] == post["total_chars"],
            "input_tokens": getattr(comp, "input_tokens", 0),
            "output_tokens": getattr(comp, "output_tokens", 0),
            "cache_read_tokens": getattr(comp, "cache_read_tokens", 0),
            "cache_write_tokens": getattr(comp, "cache_write_tokens", 0),
        }) + "\n")
        self._fp.flush()

    def close(self) -> None:
        if self._fp:
            self._fp.close()
            self._fp = None
