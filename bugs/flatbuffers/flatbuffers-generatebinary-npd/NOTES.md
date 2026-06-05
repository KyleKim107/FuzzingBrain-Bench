# Notes / gaps — flatbuffers-generatebinary-npd

- **vuln_commit**: No exact commit recorded. The record
  (`projects/chromium/flatbuffers-null-deref-GenerateBinary/vuln.yaml`)
  lists `affected_versions: "flatbuffers latest (as of 2025-12-29)"`,
  GitHub issue #8902, and an empty `fix.commit`. `bench.yaml` leaves
  `vuln_commit: ""`; the Dockerfile uses the campaign-pinned commit
  `bab10754d93d74d1ff44d46de63558bc4127f7d8` as a best-effort default
  (this commit may be slightly newer than the 2025-12-29 affected tree).
- **poc.bin**: copied verbatim from the record's `poc.bin` (68 bytes).
- **Harness build complexity**: `flatbuffers_codegen_fuzzer.cc` includes
  flatc-internal generator headers (`idl_gen_binary.h`, `idl_gen_cpp.h`,
  `bfbs_gen_lua.h`, etc.) and `test_init.h`. These live under the
  flatbuffers `src/` and `tests/` trees, not the public `include/` dir, so
  `build.sh` adds `-I src -I grpc -I tests` and links the flatc
  code-generator static lib (`libflatc*.a`) in addition to
  `libflatbuffers.a`. The exact flatc archive name is discovered with
  `find` because it has varied across flatbuffers versions. This build was
  NOT compiled/verified here (no docker/compile per task); the link targets
  and include paths are inferred from the harness includes and the
  flatbuffers cmake layout and may need adjustment.
- **class**: ASan reports "SEGV on unknown address 0x0" (a NULL deref),
  not a sanitizer-named memory error. Graded as `null-deref`.
- No `generate_poc.py` exists in the repro bundles for this harness; none
  copied.
