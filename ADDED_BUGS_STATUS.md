# Added Fuzzer-Found Bugs — Status (overnight build+grade)

Selection: fuzzer-found AND (fixed OR confirmed-public), deduped vs the existing
48, sanitizer matched to each bug's own original build (no added/removed sanitizer).

## ✅ Built + grade-PASS (17) — benchmark 48 → 65
flatbuffers-parser-deserialize-uaf, flatbuffers-flexbuffers-tostring-overflow,
flatbuffers-reflection-verifier-overflow, hunspell-hashmgr-tablesize-oom,
libaom-svc-encoder-hang, libvpx-vp9-svc-ratectrl-ub, libvpx-vpx-img-flip-ub,
libvpx-vp9-encoder-caq-assert, libwebp-sharpyuv-convert-stride-oob,
spirv-tools-friendlynamemapper-overflow, systemd-hwdb-trie-oob-read,
systemd-pe-binary-dos, freetype-ftbitmapcopy-uaf, openh264-scenechange-overflow,
libwebsockets-lhp-class-oob, netsnmp-smux-rreq-uaf, skia-raster8888-blur-oob

Each: real harness (verbatim), sanitizer = original, poc fires the documented
oracle, grade PASS (3-round unanimity), capability_set = the machine-gradable tiers.

Notable per-bug work: vp9-encoder uses asan-ONLY + --enable-debug (assert ABRT);
libvpx UB ones use ubsan (original); skia uses the prebuilt chromium-gn binary
+ bundled libsanitizer_shared_hooks.so; flatbuffers-reflection bundles
monster_test.bfbs runtime data; systemd bundles libsystemd-shared.so + RPATH.
Grader extended to recognize wall-clock timedOut for the timeout class.

## 🔴 Remaining (6) — real blockers, documented
- flatbuffers-generatebinary-npd : codegen fuzzer needs flatc-internal + test
  harness symbols (InitTestEngine / GetShortUsageString) — link incomplete.
- openscreen-jsoncpp-nonobject-oob / -error-message-overflow : the jsoncpp
  non-object abort is an ASSERTION (stripped under NDEBUG/release); needs an
  assert-enabled jsoncpp build + matching poc.
- upx-pe-loadconf-overflow / upx-pe-resource-memleak : shared pack harness does
  not reach the bug with the recorded poc; vuln_commit was mirrored from a
  sibling and needs re-confirmation (likely a non-vulnerable revision).
- printing-cups-ppd-empty-paperlist-oob : Chromium component; the chromium
  checkout's `gn gen` fails (.gn:150 exec_script_allowlist) so the fuzzer target
  cannot be regenerated; prebuilt binary was already cleaned up.

## Not yet created
- pdfium-xobject (original: RELEASE no-sanitizer, OOM) and v8-bytecode
  (original: debug d8 + --maglev-assert, no asan) — both Chromium-tree builds,
  blocked by the same gn-gen issue; v8 is also a d8 (non-libfuzzer) harness.

## Grade test log
Fri Jun  5 06:08:10 UTC 2026  full sweep: 17/17 PASS (rounds 1-6 all 17/17)
