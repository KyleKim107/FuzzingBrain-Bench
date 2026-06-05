# upx-pe-resource-memleak — authoring notes (reuse vs gaps)

## Leak modeling decision
Mirrors the existing sibling leak entry `upx-elf32-pack2-memleak`:
- `class.sanitizer: lsan`, `class.expected: memory-leak`.
- `capability_set: [reach, class, site]` — NO `crash` capability
  (a leak is detected by LSan at exit, not a crashing signal), exactly
  as the sibling models it.

## Reused (verbatim from existing upx bench entries)
- `Dockerfile` — copied from sibling `upx-elf32-pack2-memleak`
  (same upx repo, same `VULN_COMMIT=v5.0.2`, same build steps).
- `harness/build.sh` — copied from `upx-elf32-pack2-memleak`
  (asan libs built with `-fsanitize=address,fuzzer-no-link`).
- `harness/pack_file_fuzzer.cpp` — copied from
  `upx-elf32-pack2-memleak`. Per the upx family PROVENANCE the same
  `pack_file_fuzzer.cpp` is used for bugs 945/946/947/950; #946 is
  this bug.

## Bug-specific content (authored from the record)
- `bench.yaml` — bug_id/title/upstream #946.
- `grader/expected.yaml` — from the LSan trace in the record
  (`asan_output.log` / vuln.yaml): site `src/pefile.cpp:1734`,
  function `convert`, class `memory-leak`, lsan.
- `poc/poc.bin` — real 404,480-byte PE32 reproducer copied from the
  record's `poc.bin`.

## Gaps / discrepancies (real, not fabricated)
- **Harness mismatch with the record.** The record was found with the
  OSS-Fuzz harness `test_packed_file_fuzzer.cpp` (`upx -t file`, the
  unpack/test path), whose source is NOT in the record dir. The bench
  reuses the shared `pack_file_fuzzer.cpp`, which invokes
  `upx -1 -f -q` (pack path), NOT `upx -t`. These are DIFFERENT code
  paths: the record's leak is hit via the `-t` unpack →
  rebuildResources path, which `pack_file_fuzzer.cpp` does not drive
  as-is. The shared harness would need a `-t` invocation variant (or
  the real `test_packed_file_fuzzer.cpp`) to actually reproduce this
  leak. This is the biggest gap and must be resolved before the
  binaries/build step. Not re-run/verified here (NO docker/compile).
- **vuln_commit not pinned by the record.** Record states
  "affected_versions: UPX 5.0.2 (git-8622e2+)"; fix is referenced only
  as "fixed by maintainer" via issue #946, no pre-fix hash. We mirror
  the sibling memleak entry's `v5.0.2` tag.
- Per the sibling `upx-elf32-pack2-memleak` NOTE, short LSan fuzzing
  at the pinned commit previously found zero leaks — the leak's
  reproduction commit/path is not yet bisected. Same caveat applies.
- No binaries shipped (task: NO binaries).
