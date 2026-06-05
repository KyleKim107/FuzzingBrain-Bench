// Copyright 2026 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Logic Group: printing_print_settings_conversion_dict (lib = printing).
//
// Pivot rationale: spec preferred PrintSettingsFromJobSettings(Dict) but that
// is already covered in batch 1 (printing_settings_from_job_settings_fuzzer).
// Spec fallback was GetPaperSizeFromString / ParseCustomPaperSize -- those
// don't exist as exported APIs in this revision; print_backend_utils owns
// `ParsePaperSize` which is also already covered
// (printing_parse_paper_size_fuzzer).
//
// Selected entry: `printing::ParsePpdCapabilities` from
// printing/backend/cups_helper.h. This parses an attacker-supplied PPD blob
// (printer_capabilities, std::string_view) into a PrinterSemanticCapsAndDefaults
// struct. PPD blobs flow into Chromium from the local CUPS daemon -- which
// itself fetches them over IPP from network printers -- so the bytes here are
// reachable by a malicious printer on the user's network. cups_helper.cc
// builds a temp file and invokes libcups' ppdOpenFile, then post-processes
// every option/choice/conflict; that string handling is the bug magnet this
// fuzzer hunts.
//
// Linux-only: ParsePpdCapabilities is gated on BUILDFLAG(IS_LINUX).

#include <stddef.h>
#include <stdint.h>

#include <string_view>

#include "base/containers/heap_array.h"
#include "base/containers/span.h"
#include "base/strings/string_view_util.h"
#include "build/build_config.h"

#if BUILDFLAG(IS_LINUX)
#include "printing/backend/cups_helper.h"
#include "printing/backend/print_backend.h"
#endif

#include "testing/libfuzzer/libfuzzer_base_wrappers.h"

DEFINE_LLVM_FUZZER_TEST_ONE_INPUT_SPAN(base::span<const uint8_t> data) {
  if (data.empty()) {
    return 0;
  }

#if BUILDFLAG(IS_LINUX)
  // Cap to keep iterations cheap; real PPD files are small (KiB-range).
  if (data.size() > 64 * 1024) {
    return 0;
  }

  // Defensive copy so an over-read past the end of the input is caught.
  auto owned = base::HeapArray<unsigned char>::CopiedFrom(data);
  std::string_view ppd = base::as_string_view(owned);

  printing::PrinterSemanticCapsAndDefaults caps;
  // dest=nullptr matches every cups_helper_unittest call site; locale="" picks
  // the C locale path inside the helper. Return value is intentionally
  // ignored -- both true and false branches are interesting.
  (void)printing::ParsePpdCapabilities(/*dest=*/nullptr, /*locale=*/"", ppd,
                                       &caps);
#endif  // BUILDFLAG(IS_LINUX)
  return 0;
}
