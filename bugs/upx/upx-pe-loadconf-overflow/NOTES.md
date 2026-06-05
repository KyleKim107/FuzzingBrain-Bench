# upx-pe-loadconf-overflow — authoring notes (reuse vs gaps)

## Reused (verbatim from existing upx bench entries)
- `Dockerfile` — copied from sibling `upx-elf64-generate-overflow`
  (same upx repo, same `VULN_COMMIT=1ebd3356...`, same build steps).
- `harness/build.sh` — copied from `upx-elf64-generate-overflow`
  (cmake + objcopy main-rename + whole-archive link recipe).
- `harness/pack_file_fuzzer.cpp` — copied from
  `upx-elf64-generate-overflow`. Per that entry's harness PROVENANCE,
  the same `pack_file_fuzzer.cpp` drives all four upx FuzzingBrain
  bugs (945/946/947/950); #950 is this bug.

## Bug-specific content (authored from the record)
- `bench.yaml` — bug_id/title/upstream #950, capability_set
  `[reach, crash, class, site]`.
- `grader/expected.yaml` — from the ASan trace in the record
  (`asan_report.txt` / vuln.yaml): site `src/pefile.cpp:1569`,
  function `processLoadConf`, class `heap-buffer-overflow`, asan.
- `poc/poc.bin` — real 370-byte crash input copied from the record's
  `crash_input.bin`.

## Gaps / discrepancies (real, not fabricated)
- **Harness mismatch with the record.** The record was found with the
  OSS-Fuzz harness `pack_pe_fuzzer.cpp` (`upx -1 -f` PE pack path),
  whose source is NOT in the record dir. The bench reuses the shared
  FuzzingBrain `pack_file_fuzzer.cpp` (also `upx -1 -f -q`), as the
  sibling entries do for the upx family. Both drive the same pack
  code path, but this harness is not the byte-exact one named in the
  record. Not re-run/verified here (NO docker/compile per task).
- **vuln_commit not pinned by the record.** The record only states
  "affected_versions: UPX 5.1.0 - latest as of 2025-12-10" with fix
  commit `c9cdc5b`; no pre-fix hash is given. We mirror the sibling
  overflow entry's `1ebd3356...`. The crash must be re-confirmed at
  that commit when binaries are eventually built (deferred).
- No binaries shipped (task: NO binaries).
