# Provenance

**Bug**: Memory leak (LeakSanitizer) in PeFile::Resource::convert
**Upstream**: https://github.com/upx/upx/issues/946 (closed/fixed 2025-12-10)
**Vuln commit (bench)**: v5.0.2

## Source

Authored from the vuln-mgmt record
`projects/upx/Memory-Leak-PeFile-Resource-convert/`
(vuln.yaml + asan_output.log + github_issue.md + poc.bin).

## Bug

`PeFile::Resource::convert()` allocates `upx_rnode` objects
(`upx_rleaf` at pefile.cpp:1715, `upx_rbranch` at pefile.cpp:1734) and
recurses at pefile.cpp:1745. When `xcheck(child)` throws, recursively
allocated child nodes are never freed — only the `root` branch is
tracked (the developers' partial fix, see comment "prevent leak if
xcheck throws"). LeakSanitizer reports 352 bytes leaked in 9
allocations; the direct leak's top in-tree frame is
`src/pefile.cpp:1734` in `PeFile::Resource::convert`. Reached via the
`upx -t` (test/unpack) path → rebuildResources → Resource::init.

## Build

Mirrors the sibling `upx-elf32-pack2-memleak` entry exactly: UPX is
C++ cmake; asan/lsan libs built with
`-fsanitize=address,fuzzer-no-link`; `objcopy --redefine-sym
main=upx_orig_main`; `ar rcs libupx.a *.o`; harness linked with
`--whole-archive`. LeakSanitizer runs as part of ASan at process exit.

## Triggering input

`poc/poc.bin` — the real 404,480-byte PE32 leak reproducer copied
verbatim from the record's `poc.bin`.
