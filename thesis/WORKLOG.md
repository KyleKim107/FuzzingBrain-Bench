# Thesis Worklog — Cost-Layer on FuzzingBrain-Bench

Running diary of Kyle's thesis work (cost/quality levers for LLM vuln-repro
agents). **Read this at the start of a session to resume.** Newest entry on top.
Complements the paste-in handoff (v3) and the auto-memory index (`MEMORY.md`).

- **Repo role:** `origin` = KyleKim107 fork, `upstream` = OwenSanzas (Owen/Ze).
- **Work branch:** `feat/cost-levers` (main is kept a clean mirror of upstream).
- **Thesis artifacts:** `tools/context_growth.py`, `tools/baseline_summary.py`,
  and this `thesis/` dir. Do NOT edit the `fbbench/` package except the two
  agreed patches (see Open items).

---

## 2026-07-11 — Session 2: patch #1 (no-cache switch)

### Built this session
- **Patch #1 — no-cache switch** (`fbbench/runner/backends/anthropic_backend.py`),
  the first of the two agreed fbbench edits. Env-gated: `FBBENCH_NO_CACHE=1`
  skips the `_with_cache(...)` call in `complete()` so every prompt token is
  billed FRESH (1x) instead of riding in `cache_read` (0.1x). **Off by default**
  — normal runs keep all three cache breakpoints, so Ze's behavior is unchanged.
  Chose env-gate (not a CLI flag / ctor arg) because it's the smallest diff and
  matches the existing `FBBENCH_*` convention (`FBBENCH_REPO`, `FBBENCH_IMAGE_PREFIX`).
  This unblocks the caching-OFF half of every lever measurement.
- **Verified offline** (`scratchpad/verify_nocache.py`, no API/$): stubbed
  `_stream_once` to capture the exact payload handed to the SDK. DEFAULT →
  system becomes a cacheable list block + last tool + last content block all carry
  `cache_control`. `FBBENCH_NO_CACHE=1` → system stays a raw str, ZERO
  `cache_control` anywhere, and `blocks == _to_blocks(...)` byte-for-byte (no
  mutation). All assertions pass.

### Next-session starting points (unchanged plan, patch #1 now done)
- **Empirical confirm (optional, cheap):** one real haiku run with
  `FBBENCH_NO_CACHE=1` → expect `cache_read_tokens == 0` in `wrap.jsonl` and a
  visibly higher $ than the cached baseline (data-backs "caching hid the cost").
- **Then lever #1 (structured diagnosis):** a `transform` on `BackendWrapper`
  that rewrites `grade` tool-results containing a sanitizer report → distilled
  signal. Measure vs baseline, caching ON *and* OFF (now possible), N repeats;
  savings must beat the ±40–48% variance band. Reuse `wrap.jsonl` +
  `context_growth.py` for the token delta.
- **Patch #2 (later):** mixed-model cost accounting for lever 4.

---

## 2026-07-05 — Session 1: setup, first real run, measurement rig

### Decisions locked this session
- **Target = MS thesis** (not a top-tier paper). Lowers the variance/generality
  bar; framing risk accepted.
- **Levers 1–3 are the bench primary.** They are pure `messages`/`system`
  transforms inside a `BackendWrapper` (implements the `Backend` Protocol,
  `fbbench/runner/backends/base.py:55`) — NO edits to Ze's episode loop.
- **Lever 4 (adaptive model):** feasible but needs a **mixed-model cost-accounting
  patch** — `pricing.cost_usd` prices all tokens at ONE model
  (`fbbench/models/pricing.py:49`), while the loop sums every turn into one
  `result` (`episode.py:160`). No separate classifier needed — rule-based /
  cascade routing on signals already visible at the seam.
- **Lever 5 (domain rules): mostly DROPPED from the bench.** The bench's unit of
  measurement IS the LLM agent, so "replace an LLM call with code" has no clean
  home: either (a) add a tool = changes the benchmark surface (Go MCP server owns
  tools, not comparable to baseline), or (b) precompute + inject = degenerates
  into lever 1. Also the bench already exposes `exec` for deterministic compute
  (`prompts.py:88`). → Lever 5's real home is the LIVE FuzzingBrain system (a
  pipeline of LLM calls with genuinely swappable deterministic stages). On the
  bench, note it as "degenerates into lever 1."
- **The KEY research axis = lever TRIGGERS, not the transforms.** The transforms
  are simple parsers; what decides cost/quality is WHEN each fires and HOW MUCH
  it cuts. So each lever = a *trigger-parameter sweep* → a `(cost, quality)`
  CURVE, not one point. Overlaying the curves = the Pareto frontier; the
  minimal-signal breakpoint = where a curve bends.
  - Lever 1 trigger: fires on `grade` results that contain a sanitizer report
    (by tool KIND). ~0 params.
  - Lever 3 trigger: fires when a single tool output exceeds a size threshold
    **T** (by SIZE). Sweep T. Its "high-signal region" recognizer is a
    deterministic parser (ASan/UBSan/Jazzer have rigid formats) — **no ML**; the
    ablation certifies the recognizer's definition.
  - Lever 2 trigger: two axes — WHICH turns to drop (age? failed grade?) + WHEN
    to start (cumulative-token threshold). Most params, most risky; must drop
    (assistant, tool-result) PAIRS to keep tool_use↔tool_result adjacency
    (`anthropic_backend.py:45`).
- **Measurement design:** always pair cost with quality; measure caching ON and
  OFF (needs a no-cache switch — patch #1 for Ze); path-dependent lever effects
  → use BOTH replay (mechanical ceiling on a frozen transcript) and live
  (realized cost+quality). Quality axis = capability ladder tier_score (partial
  credit, more sensitive than binary `solved`).

### The capability ladder (quality axis), from README
Five nested rungs, weak→strong: `reach` (got to buggy region) → `crash`
(sanitizer faults) → `differential` (faults buggy build, clean on fixed) →
`class` (fault type matches) → `site` (crash location matches). `tier_score` =
# fired. A bug is "solved" when its required set `K_b` all fires. Graded by a
**remote deterministic oracle** (answer key baked-out of repo/images; agent only
sees `harness_output`, never the verdict — `episode.py:296`).

### Environment (verified working — see memory `fbbench-smoke-setup`)
- `.venv/` + `pip install -e .` done (anthropic 0.116.0). Run via `.venv/bin/fb-bench`.
- `.env` (gitignored): `ANTHROPIC_API_KEY` + **`DOCKER_DEFAULT_PLATFORM=linux/amd64`**
  — challenge images `osanzas/fbbench-challenge-*` are amd64-only; on this Apple
  Silicon Mac they fail with `no matching manifest for linux/arm64/v8` without it.
- `requirements.txt` added (mirrors pyproject).
- GPT usage: add `OPENAI_API_KEY`, run `--model gpt-5.5` (pricier: $5/$30 vs
  haiku $1/$5). Custom endpoint (lab proxy/Azure) only via `OLLAMA_BASE_URL`
  hack; a clean `OPENAI_BASE_URL` would be a small patch. (User to confirm which.)

### Built this session
- **`tools/context_growth.py`** — per-transcript analyzer: (A) per-turn billed
  prompt-token growth curve; (B) content-mass decomposition by category
  (read_file / grade / other tool results / assistant_text / system / tools /
  notes) → which lever has headroom. Committed on `feat/cost-levers` (a3d9119).
- **`tools/baseline_summary.py`** — aggregates a batch into VARIANCE + GENERALITY
  tables (committed ad5588d).
- **`tools/backend_wrapper.py`** — the shim seam: `BackendWrapper` implements the
  `Backend` Protocol, wraps a real backend, sees the full neutral history each
  `.complete()`, applies a `transform` (lever; default identity), logs to
  `wrap.jsonl`. Standalone (no fbbench import). **VERIFIED:** free fake-backend
  test (`test_backend_wrapper.py`) + one real wrapped run
  (`run_wrapped.py avro-03`, tier 4, $0.12) → n_messages 1→47 monotonic,
  `unchanged=True` on all 24 calls, normal artifacts intact. Interception proven
  with zero edits to the episode loop.
- **`tools/run_wrapped.py`** — runs a real episode with the backend wrapped, by
  monkeypatching `make_backend` on the in-process runner entry
  (`fbbench.runner.__main__`, make_backend at `__main__.py:121`). `fb-bench run`
  is a SUBPROCESS so can't be patched — must go through `python -m fbbench.runner`
  (which needs NO host Go binary in image mode; the `--local` guard is the only
  one, `__main__.py:98`).

### First smoke run (avro-03, haiku)
`fb-bench run avro-03 --model claude-haiku-4-5` → **41 turns, tier_score 2**
(reach+crash fired; class/site NOT — an off-target crash, not the documented
defect), voluntary stop, **$0.18**, 84 s.

**First real analyzer output (single run, NOT a finding yet — rig validation):**
- Context grew **17.1×** (turn0 2,219 → peak 37,955 prompt tok). Data-backs the
  "full history replayed every turn" problem (motivation for lever #2).
- `fresh_in` collapses to ~3 tok/turn from turn 3; the growing 38k rides in
  `cache_read`. So caching-ON hides the $ cost of the growth (why it was only
  $0.18) — exactly why caching OFF/ON must both be measured.
- Content mass: **read_file 47%** (→ lever #3), tool_result:other 25%, grade 12%
  (→ lever #1), assistant_text 9.5% (→ lever #2).

### Baseline batch (running at session end — results appended below)
`--exp baseline`, haiku: avro-03 ×4 (variance) + json-java-01, libpng-01, jq-01
×1 (generality). Aggregate with:
`python tools/baseline_summary.py runs/baseline`

**Results (2026-07-05, haiku, `runs/baseline`):**

*(1) VARIANCE — avro-03 ×4 (all 4 SOLVED, tier 4–5):*
| metric | mean | range | spread |
|---|---|---|---|
| tier_score | 4.5 | 4–5 | ±13% |
| **cost usd** | 0.156 | 0.066–0.251 | **±48%** |
| **peak context tok** | 35,201 | 19,267–53,560 | **±40%** |
| turns | 32.5 | 15–43 | ±38% |

→ **KEY METHODOLOGY FINDING:** sampling-only (temp=1.0) cost/context variance is
**~40–48% on a single bug**. A lever's saving must CLEAR this band, or need many
repeats to tighten it — **single-run lever comparisons are meaningless**. One run
solved tier 5 in 15 turns/$0.066 while another needed 43 turns/$0.251 for the
same tier 5 (4× cost for identical outcome). (Note: the earlier smoke run drew
tier 2 → outcome range is tier 2–5 across 5 total draws.)

*(2) GENERALITY — is read_file the dominant context bucket?*
| bug | tier | usd | peak_tok | read% | grade% |
|---|---|---|---|---|---|
| avro-03 | 4 | 0.15 | 35,334 | **53** | 10 |
| jq-01 | 0 (fail) | 0.81 | 60,916 | 38 | 27 |
| json-java-01 | 5 | 0.21 | 32,199 | 33 | 3 |
| libpng-01 | 0 (fail) | 0.45 | 53,252 | **11** | 13 |

→ read_file is the biggest movable bucket in **3 of 4** bugs — but **NOT
universal** (libpng-01 only 11%; its mass is in the `other` bucket). grade% swings
3%→27%. The two FAILED bugs (jq, libpng) are the COSTLY ones with shifted
profiles (jq's grade 27% = repeated failed attempts). Implications: lever #3
(read_file) has broad but not universal headroom; lever #1 (grade) matters more
on some bugs. **TODO: split the `other` bucket (esp. libpng) to find its
dominant source** (likely exec/list_directory).

### Open items / next-session starting points
- **Patches to propose to Ze (PRs):** (1) no-cache switch (bypass `_with_cache`
  in `anthropic_backend.py`); (2) mixed-model cost accounting (for lever 4).
  Optionally (3) `OPENAI_BASE_URL` support.
- **Working arrangement with Ze** still to confirm (PR into upstream vs long-lived
  branch vs co-author); repeat count the lab considers significant.
- **Next build:** ~~`BackendWrapper` pass-through scaffold~~ ✅ DONE (verified
  end-to-end). NEXT = (1) no-cache switch (patch #1 for Ze) so caching-off clean
  measurement is possible, then (2) **lever #1 (structured diagnosis)** as a
  `transform` on the wrapper: rewrite `grade` tool-result crash reports to a
  distilled signal → measure vs baseline, caching on/off, N repeats, savings must
  beat the ±40–48% variance band. Reuse `wrap.jsonl` + `context_growth.py` to
  quantify the token delta.
- **Next measure:** once variance band is known, only trust lever savings that
  exceed it.
