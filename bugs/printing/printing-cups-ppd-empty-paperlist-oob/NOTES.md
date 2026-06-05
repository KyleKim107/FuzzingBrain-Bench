# Notes — printing-cups-ppd-empty-paperlist-oob

## Source record
`projects/chromium/oob-printing-cups-helper-ppd-capabilities-empty-papers/`.
There is **no** `data/chrome/.../*.repro/method.yaml` for this finding (unlike
the openscreen/spirv entries). The only build metadata is
`data/chrome/libraries/printing/harnesses/printing_print_settings_conversion_dict/build_info.yaml`,
which records `build_mode: chromium-internal` and a 301 MB chromium-internal
binary — i.e. it was built inside a full chromium tree, not as a standalone
library.

## vuln_commit / repo
- repo: `https://chromium.googlesource.com/chromium/src` (the bug is in
  chromium's `printing/` component, not a vendored library).
- vuln_commit: `d3ea842c93e59fec607736bd605f77216264483e` — the chromium HEAD
  the source bug_report pins (synced 2026-04-22). Taken from the bug_report's
  Production Reproduction build section (no method.yaml exists to read it from).

## Class
Task brief: `oob-read`. The underlying defect is an empty-`std::vector`
`operator[](0)` out-of-bounds read at `printing/backend/cups_helper.cc:950`
(CWE-129). The OBSERVABLE sanitizer signature is NOT a classic ASan
heap-buffer-overflow redzone report — Chromium's release-default libc++
hardening (`_LIBCPP_HARDENING_MODE_EXTENSIVE`) traps the empty access inside
`vector::operator[]` first, firing `__libcpp_verbose_abort` -> `abort()`,
surfaced by libFuzzer as a "deadly signal". The grader uses `class: oob-read`
(the brief's label / true root cause); the deadly-signal nature is documented
here and in `grader/expected.yaml`.

## Build feasibility — INFEASIBLE STANDALONE (flagged per task)
Both the libFuzzer harness
(`printing_print_settings_conversion_dict_fuzzer.cc`) and the Path-B repro
(`repro_ppd_empty_papers.cc`) depend on `//printing/backend` and `//base` and
can only be compiled inside a synced `chromium/src` checkout via `gn`+`ninja`
with `use_cups=true`. A debian-slim standalone library build (the pattern the
avro / spirv-tools / openscreen-jsoncpp entries use) is **not possible** for
this component.

- `harness/build.sh` records the real chromium build recipe from the
  bug_report but exits non-zero (it cannot run without a chromium checkout).
- `Dockerfile` documents the `fetch chromium` + `gclient sync` + `gn`/`ninja`
  path in commented stages but does NOT execute them (impractical: tens of GB,
  hours) — its active step just prints the infeasibility note.

The PoC and grader expectations are real (derived from the verified bug_report
traces), but the Dockerfile build could NOT be validated. Anyone wanting a
runnable artifact must build inside a chromium checkout at the pinned commit.

## PoC
`poc/poc.bin` is the 627-byte malformed PPD from the bug_report's
`generate_poc.py`; `poc/generate_poc.py` rematerializes it. Verified
SHA1 = `6033e36a8873ea14ae621f21e32a972f7a22fd8f` (matches the bug_report).
