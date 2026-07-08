#!/usr/bin/env python3
"""Run a real fbbench episode with the backend routed through BackendWrapper —
end-to-end interception with ZERO edits to the fbbench package.

It monkeypatches `make_backend` in the in-process runner entry
(`python -m fbbench.runner`, where make_backend is called at __main__.py:121),
so the episode is byte-identical to a normal run except the backend is wrapped.
A `wrap.jsonl` is written into the run's out-dir, proving the wrapper saw the
full history on every turn.

Usage:
    python tools/run_wrapped.py <bug> --model claude-haiku-4-5 [extra runner args]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend_wrapper import BackendWrapper  # noqa: E402

import fbbench.runner.__main__ as entry     # noqa: E402
from fbbench.paths import REPO              # noqa: E402


def _next_run_dir(bug: str, model: str) -> Path:
    base = REPO / "runs" / "wrapped" / bug / model
    base.mkdir(parents=True, exist_ok=True)
    n = 0
    while (base / f"run-{n}").exists():
        n += 1
    d = base / f"run-{n}"
    d.mkdir()
    return d


def main(argv: list[str]) -> int:
    if not argv or argv[0].startswith("-"):
        print("usage: python tools/run_wrapped.py <bug> --model <m> [args]",
              file=sys.stderr)
        return 2
    bug = argv[0]
    rest = argv[1:]
    model = "claude-haiku-4-5"
    if "--model" in rest:
        model = rest[rest.index("--model") + 1]

    out_dir = _next_run_dir(bug, model)
    wrap_log = str(out_dir / "wrap.jsonl")

    # Patch the name the runner's main() actually resolves (it did
    # `from ...backends import make_backend`, so patch it on the entry module).
    _orig = entry.make_backend

    def _wrapped(m, api_key=None):
        return BackendWrapper(_orig(m, api_key=api_key), log_path=wrap_log)

    entry.make_backend = _wrapped
    print(f"[run_wrapped] backend wrapped; out-dir {out_dir}", file=sys.stderr)

    # Hand the runner a normal argv; force our out-dir so wrap.jsonl sits beside
    # score.json/transcript.jsonl.
    sys.argv = ["fbbench.runner", "--bug", bug, "--out-dir", str(out_dir), *rest]
    return entry.main()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
