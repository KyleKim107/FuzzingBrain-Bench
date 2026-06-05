# syntax=docker/dockerfile:1.6
#
# !!! BUILD NOT VALIDATED — CHROMIUM-INTERNAL !!!
# This bug lives in the Chromium `printing/` component
# (printing/backend/cups_helper.cc). The harness and the Path-B repro both
# depend on //printing/backend + //base and can only be built inside a full
# chromium/src checkout (gn + ninja, depot_tools, ~tens of GB). A standalone
# debian-slim library build like the other entries is INFEASIBLE here.
#
# The stages below document the real chromium build path from the source
# bug_report but are intentionally left commented/stubbed: actually running
# `fetch chromium` + `gclient sync` is impractical for this bundle and was NOT
# performed. See NOTES.md. This Dockerfile is provided for completeness only.
FROM debian:bookworm-slim
ARG VULN_COMMIT=d3ea842c93e59fec607736bd605f77216264483e
ARG SOURCE_DATE_EPOCH=1735689600
ENV SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH}
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates curl python3 lsb-release sudo \
    && rm -rf /var/lib/apt/lists/*

COPY harness/printing_print_settings_conversion_dict_fuzzer.cc /src/harness/printing_print_settings_conversion_dict_fuzzer.cc
COPY harness/repro_ppd_empty_papers.cc                         /src/harness/repro_ppd_empty_papers.cc
COPY harness/build.sh                                          /src/harness/build.sh
RUN chmod +x /src/harness/build.sh

# --- The following stages require a full chromium checkout and are NOT run. ---
# RUN git clone --depth 1 https://chromium.googlesource.com/chromium/tools/depot_tools /opt/depot_tools
# ENV PATH="/opt/depot_tools:${PATH}"
# RUN mkdir -p /src/chromium && cd /src/chromium \
#  && fetch --no-history chromium \
#  && git -C src checkout ${VULN_COMMIT} \
#  && gclient sync -D
# RUN cp /src/harness/printing_print_settings_conversion_dict_fuzzer.cc \
#        /src/chromium/src/printing/<custom_fuzzers>/ \
#  && cd /src/chromium/src \
#  && printf 'is_debug=false\nis_component_build=false\nuse_libfuzzer=true\nis_asan=true\nenable_nacl=false\nsymbol_level=1\noptimize_for_fuzzing=true\nuse_cups=true\n' > out/fuzzer/args.gn \
#  && gn gen out/fuzzer \
#  && ninja -C out/fuzzer printing_print_settings_conversion_dict_fuzzer
RUN echo "printing-cups-ppd-empty-paperlist-oob: chromium-internal build not performed (see NOTES.md)"
