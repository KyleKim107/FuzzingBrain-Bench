#!/bin/bash
# Build script for printing-cups-ppd-empty-paperlist-oob.
#
# !!! BUILD NOT VALIDATED — CHROMIUM-INTERNAL !!!
# This is a Chromium `printing/` component bug. Both the libFuzzer harness
# (printing_print_settings_conversion_dict_fuzzer.cc) and the Path-B repro
# (repro_ppd_empty_papers.cc) depend on //printing/backend + //base and can
# only be built inside a full chromium/src checkout via gn+ninja with libcups.
# A standalone-library Dockerfile build (the pattern used by the avro / spirv /
# openscreen-jsoncpp entries) is INFEASIBLE here. The recipe below is the real
# chromium build path from the source bug_report, recorded for fidelity; it
# requires `fetch chromium` + `gclient sync` (tens of GB, hours) and is not run
# by this bundle's Dockerfile. See NOTES.md.
set -euo pipefail
cmd="${1:?usage: build.sh build-libs | harness <config>}"

CHROMIUM_SRC=${CHROMIUM_SRC:-/src/chromium/src}
VULN_COMMIT=${VULN_COMMIT:-d3ea842c93e59fec607736bd605f77216264483e}

if [ "${cmd}" = "build-libs" ]; then
    echo "ERROR: chromium-internal build. Provide a synced chromium checkout at" >&2
    echo "       CHROMIUM_SRC=${CHROMIUM_SRC} pinned to ${VULN_COMMIT}." >&2
    echo "       Steps (outside this bundle):" >&2
    echo "         fetch --no-history chromium && gclient sync" >&2
    echo "         git -C ${CHROMIUM_SRC} checkout ${VULN_COMMIT} && gclient sync -D" >&2
    exit 3
fi

if [ "${cmd}" = "harness" ]; then
    CONFIG="${2:?harness needs <config>}"
    OUT=/out/${CONFIG}
    mkdir -p "${OUT}"

    # Reference recipe (run inside ${CHROMIUM_SRC}); NOT executed here.
    # Drop the in-tree harness into the build and target it directly:
    #   cp /src/harness/printing_print_settings_conversion_dict_fuzzer.cc \
    #      ${CHROMIUM_SRC}/printing/<custom_fuzzers location>/
    #   cat > ${CHROMIUM_SRC}/out/${CONFIG}/args.gn <<'EOF'
    #   is_debug = false
    #   is_component_build = false
    #   use_libfuzzer = true
    #   is_asan = true
    #   enable_nacl = false
    #   symbol_level = 1
    #   optimize_for_fuzzing = true
    #   use_cups = true
    #   EOF
    #   gn gen out/${CONFIG}
    #   ninja -C out/${CONFIG} printing_print_settings_conversion_dict_fuzzer
    echo "ERROR: chromium-internal build cannot run in this bundle (see NOTES.md)." >&2
    exit 3
fi
exit 2
