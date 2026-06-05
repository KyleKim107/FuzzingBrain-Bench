# Provenance

**Bug**: Heap buffer overflow (OOB read) in PeFile::processLoadConf
**Upstream**: https://github.com/upx/upx/issues/950
**Fix commit**: c9cdc5b (upstream, closed/fixed 2025-12-20)
**Vuln commit (bench)**: 1ebd3356f36780960a03354a8ded23410ebc7e79

## Source

Authored from the vuln-mgmt record
`projects/upx/Heap-Buffer-Overflow-PeFile-processLoadConf/`
(vuln.yaml + asan_report.txt + github_issue.md + crash_input.bin).

## Bug

`PeFile::processLoadConf()` reads `soloadconf` (PE Load Configuration
Directory size, attacker-controlled `get_le32(loadconf)`) and does
`memcpy(oloadconf, loadconf, soloadconf)` at `src/pefile.cpp:1569`
without bounding `soloadconf` against the `isection` buffer
(65,540 bytes allocated in `readSections()` at pefile.cpp:2235). A
crafted PE32 declaring a 9,460,301-byte load-config size causes a
~9.4 MB OOB heap read. The size check at line 1553 only `info()`s a
warning and does NOT return. ASan reports `heap-buffer-overflow` /
READ of size 9460301, 0 bytes after the 65540-byte region.

## Build

Mirrors the sibling `upx-elf64-generate-overflow` entry exactly:
UPX is C++ cmake. `objcopy --redefine-sym main=upx_orig_main` on
`main.cpp.o` so libFuzzer's `main()` wins; `ar rcs libupx.a *.o`;
link harness with `--whole-archive libupx.a` + vendor archives. The
harness writes the fuzz input to a tempfile and calls
`upx_main(7, {"upx","-1","-f","-q",in,"-o",out})` to drive the pack
path. Same vuln_commit as #947 (the ELF64 sibling filed alongside).

## Triggering input

`poc/poc.bin` — the real 370-byte malformed PE32 crash input copied
verbatim from the record's `crash_input.bin`.
