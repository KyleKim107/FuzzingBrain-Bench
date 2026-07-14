#!/usr/bin/env python3
"""Cost levers as BackendWrapper transforms (Kyle, thesis).

A lever is `transform(system, messages, tools) -> (system, messages, tools)`.
It is handed the FULL neutral history every turn (see backend_wrapper.py) and
returns a possibly-rewritten copy. Levers must NOT mutate their inputs — they
build NEW objects for anything they change and reuse the originals otherwise —
so the wrapper's pre/post measure stays honest and identity is a provable no-op.

Neutral message shapes (fbbench/runner/backends/base.py):
  {"role":"user","content":str}
  {"role":"assistant","text":str,"tool_calls":[ToolCall...]}
  {"role":"tool","results":[ToolResult...], "note"?:str}
A ToolResult is a dataclass with .name / .content (content = JSON-encoded tool
output). For the `grade` tool, content == json.dumps({"harness_output": {...}}),
and a sanitizer crash report rides inside harness_output["stderr"].

Lever #1 — structured diagnosis
  Trigger: fires by tool KIND (name == "grade") when the grade result carries a
  sanitizer report. ~0 params (see worklog).
  Transform: distill the raw ASan/UBSan dump — a rigid, deterministic format —
  down to its high-signal lines (crash kind, target-source stack frames, the
  SUMMARY), dropping libFuzzer banner, sanitizer-interceptor / harness / libc
  frames, hex addresses and BuildIds. No ML; the parser IS the definition of the
  "high-signal region" the ablation certifies. Distilling at arrival (the tail)
  keeps the prompt-cache prefix stable, so it saves tokens WITHOUT breaking cache.
"""
from __future__ import annotations

import dataclasses
import json
import re

# ---- ASan/UBSan (LLVM sanitizer) report parsing -----------------------------
# A stack frame line. Matches BOTH the raw sanitizer form and our own distilled
# form, so distill() is idempotent (re-running it on an already-distilled tail
# every turn must be a no-op or the prompt-cache prefix would churn):
#   raw:       "    #1 0x5b47.. in avro_default_allocator /src/.../allocation.c:36:10"
#   raw noise: "    #0 0x5b47.. in __interceptor_realloc (/out/harness+0xea0e6) (BuildId ..)"
#   distilled: "  #1 avro_default_allocator /src/.../allocation.c:36:10"
_FRAME = re.compile(r"^\s*#(\d+)\s+(?:0x[0-9a-fA-F]+\s+in\s+)?(.*)$")
# A source location "func /path/file.ext:line[:col]" (what we keep).
_SRC = re.compile(r"^(?P<func>.*?)\s+(?P<loc>\S+:\d+(?::\d+)?)\s*$")
# The crash headline (with or without the leading "ERROR:", i.e. also matches our
# own distilled headline) and the canonical summary.
_ERROR = re.compile(r"(?:ERROR:\s*)?(\w*Sanitizer:\s.*)$")
_SUMMARY = re.compile(r"^\s*SUMMARY:\s*(.*)$")
# Address / BuildId noise to scrub from any kept line.
_ADDR = re.compile(r"\s*\((?:/[^)]*\+)?0x[0-9a-fA-F]+\)")
_BUILDID = re.compile(r"\s*\(BuildId:[^)]*\)")


def _is_sanitizer_report(stderr: str) -> bool:
    return bool(stderr) and ("Sanitizer:" in stderr or "runtime error:" in stderr)


def distill_sanitizer(stderr: str) -> str:
    """Raw sanitizer stderr -> distilled high-signal report.

    Keeps: the ERROR headline (crash kind + details), stack frames that name a
    target SOURCE file (func + path:line), and the SUMMARY. Drops: libFuzzer
    banner, address-only interceptor/harness/libc frames, hex addresses, BuildIds.
    Idempotent and deterministic (same input -> same output), so re-running it on
    an already-distilled tail every turn does not perturb the cache prefix.
    """
    error_line = None
    summary_line = None
    frames: list[str] = []
    for raw in stderr.splitlines():
        # SUMMARY first: its text also contains "<X>Sanitizer:", which the
        # headline pattern would otherwise swallow.
        m = _SUMMARY.match(raw)
        if m and summary_line is None:
            summary_line = _BUILDID.sub("", _ADDR.sub("", m.group(1))).strip()
            continue
        m = _ERROR.search(raw)
        if m and error_line is None:
            error_line = _BUILDID.sub("", _ADDR.sub("", m.group(1))).strip()
            continue
        m = _FRAME.match(raw)
        if m:
            body = m.group(2)
            src = _SRC.match(_BUILDID.sub("", body).strip())
            if src:  # keep only frames that resolve to a source file:line
                frames.append(f"  #{m.group(1)} {src.group('func')} {src.group('loc')}")
    parts = []
    if error_line:
        parts.append(error_line)
    parts.extend(frames)
    if summary_line:
        parts.append("SUMMARY: " + summary_line)
    # If we somehow parsed nothing recognizable, fail safe: keep the original.
    return "\n".join(parts) if parts else stderr


def _distill_grade_content(content: str) -> str | None:
    """Rewrite one grade ToolResult.content, or None if nothing to do."""
    try:
        obj = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    ho = obj.get("harness_output") if isinstance(obj, dict) else None
    if not isinstance(ho, dict):
        return None
    stderr = ho.get("stderr") or ""
    if not _is_sanitizer_report(stderr):
        return None  # clean run / empty / non-sanitizer: leave untouched
    new_ho = {"exit_code": ho.get("exit_code"), "signal": ho.get("signal", ""),
              "stderr": distill_sanitizer(stderr)}
    if ho.get("stdout"):  # keep stdout only when it actually carries something
        new_ho["stdout"] = ho["stdout"]
    return json.dumps({"harness_output": new_ho})


def _set_content(result, new_content: str):
    """Return a COPY of a ToolResult (dataclass) or dict with content replaced."""
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        return dataclasses.replace(result, content=new_content)
    if isinstance(result, dict):
        return {**result, "content": new_content}
    # Unknown shape: best-effort attribute copy.
    import copy
    r = copy.copy(result)
    r.content = new_content
    return r


def structured_diagnosis(system, messages, tools):
    """Lever #1: distill sanitizer reports in `grade` tool-results.

    Rebuilds only the tool messages that actually contain a distillable grade
    result; every other message object is reused as-is (so unchanged turns stay
    byte-identical for cache-prefix stability and honest pre/post measurement).
    """
    def _name(r):
        return r.get("name") if isinstance(r, dict) else getattr(r, "name", None)

    def _content(r):
        return r.get("content") if isinstance(r, dict) else getattr(r, "content", None)

    new_messages = []
    for m in messages:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
        results = (m.get("results") if isinstance(m, dict)
                   else getattr(m, "results", None)) if role == "tool" else None
        if not results:
            new_messages.append(m)
            continue
        changed = False
        new_results = []
        for r in results:
            if _name(r) == "grade":
                distilled = _distill_grade_content(_content(r) or "")
                if distilled is not None and distilled != _content(r):
                    new_results.append(_set_content(r, distilled))
                    changed = True
                    continue
            new_results.append(r)
        if not changed:
            new_messages.append(m)
        elif isinstance(m, dict):
            new_messages.append({**m, "results": new_results})
        else:
            new_messages.append(dataclasses.replace(m, results=new_results)
                                if dataclasses.is_dataclass(m)
                                else {**vars(m), "results": new_results})
    return system, new_messages, tools


# Registry so run_wrapped.py can select a lever by name.
LEVERS = {
    "identity": None,               # sentinel: use wrapper's default identity
    "lever1": structured_diagnosis,
    "structured_diagnosis": structured_diagnosis,
}
