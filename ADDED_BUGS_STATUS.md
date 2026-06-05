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
Fri Jun  5 06:09:35 UTC 2026  round 7: 17/17 PASS
Fri Jun  5 06:10:31 UTC 2026  round 8: 17/17 PASS
Fri Jun  5 06:11:20 UTC 2026  round 9: 17/17 PASS

## upx investigation result (overnight)
upx-pe-loadconf: tried the real vulnerable version (v5.1.0, commit 779acb1) —
builds fine, but the recorded 370B poc still does NOT fire. Root cause is the
HARNESS, not the commit: the bench reuses the shared `pack_file_fuzzer` (drives
`upx -1 -f -q` pack), but the recorded poc belongs to the original PE-specific
`pack_pe_fuzzer`, whose source was NOT preserved in the records. Blocked on the
real harness source.
Fri Jun  5 06:18:38 UTC 2026  round 10: 17/17 PASS
Fri Jun  5 06:19:28 UTC 2026  round 11: 17/17 PASS
Fri Jun  5 06:20:16 UTC 2026  round 12: 17/17 PASS
Fri Jun  5 06:21:02 UTC 2026  round 13: 17/17 PASS
Fri Jun  5 06:21:49 UTC 2026  round 14: 17/17 PASS
Fri Jun  5 06:22:36 UTC 2026  round 15: 17/17 PASS
Fri Jun  5 06:23:27 UTC 2026  round 16: 17/17 PASS

## Root-cause audit (87 disclosures) — harness-misuse FPs caught
Re-audited the misuse-prone subset (NPD/leak/assertion) by ROOT CAUSE, not link.
Found 2 harness API-misuse FPs that link-matching missed (same bug, different link):
- cups cupsResolveConflicts NPD (#64): caller passes options=NULL with num_options>0
  — matches harness_violations/cups/harness_use_api_wrongly. NOT in benchmark.
- flatbuffers GenerateBinary NPD (#85): IDLOptions::file_saver defaults to nullptr and
  the harness never sets it — caller-induced NULL, not attacker data. REMOVED from
  benchmark additions (this was the un-buildable "flatbuffers-generatebinary-npd").
All other NPD/leak/assertion (webp-muxassemble, jq, ots, freerdp-ntlm-leak, net-snmp-vacm,
harfbuzz size==0 [documented-valid], vp9-encoder-assert [valid-range config]) = real,
data-driven. Parser overflows/UAF/OOB (the majority) are crafted-input driven = real.

## NEW addition after audit: cups-utf8-charset-overflow (grade PASS)
The audit confirmed cups cupsUTF8ToCharset (#63) is a REAL data-driven bug (distinct
from the cupsResolveConflicts harness-misuse #64). Built it: focused fuzz_transcode
harness, libcups built ASan-via-OPTIM (configure stays bare so its run-test passes
under buildkit), poc [0x0A,0xC1]. Grade PASS — reach+crash+class(heap-buffer-overflow)
+site(transcode.c:245) all fire. Benchmark 70 -> 71.
