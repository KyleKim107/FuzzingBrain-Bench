// repro_ppd_empty_papers.cc
//
// Path-B (Chromium-internal-API) reproduction for
// printing-cups-ppd-empty-paperlist-oob. Uses ONLY the public //printing/backend
// surface the browser process drives when querying printer capabilities:
//
//   printing::ParsePpdCapabilities          (public //printing/backend)
//   printing::PrinterSemanticCapsAndDefaults (public //printing/backend)
//
// Verbatim from the source bug_report. This STILL requires building inside a
// chromium checkout (it depends on //printing/backend and //base) — it is not
// standalone-compilable. See NOTES.md.

#include <cstdio>
#include <cstdlib>
#include <string>
#include <string_view>

#include "base/compiler_specific.h"
#include "base/logging.h"
#include "printing/backend/cups_helper.h"
#include "printing/backend/print_backend.h"

int main(int argc, char** argv) {
  if (argc != 2) {
    LOG(ERROR) << "usage: repro_ppd_empty_papers <ppd_file>";
    return 1;
  }
  // SAFETY: argv[1] is null-terminated by libc.
  const char* path = UNSAFE_BUFFERS(argv[1]);
  FILE* f = UNSAFE_BUFFERS(std::fopen(path, "rb"));
  if (!f) { LOG(ERROR) << "fopen failed"; return 1; }
  std::fseek(f, 0, SEEK_END);
  long n = std::ftell(f);
  std::fseek(f, 0, SEEK_SET);
  if (n <= 0) { LOG(ERROR) << "empty input"; return 1; }
  std::string ppd(static_cast<size_t>(n), '\0');
  // SAFETY: ppd.data() is sized to hold exactly n bytes.
  if (UNSAFE_BUFFERS(std::fread(ppd.data(), 1, n, f)) !=
      static_cast<size_t>(n)) {
    LOG(ERROR) << "fread failed"; return 1;
  }
  std::fclose(f);

  printing::PrinterSemanticCapsAndDefaults caps;
  // dest=nullptr matches every cups_helper_unittest call site; the production
  // browser-process caller passes a valid cups_dest_t* but the OOB site at
  // cups_helper.cc:950 does not consult `dest`.
  bool ok = printing::ParsePpdCapabilities(/*dest=*/nullptr,
                                           /*locale=*/"",
                                           std::string_view(ppd), &caps);
  LOG(INFO) << "ParsePpdCapabilities returned " << (ok ? "true" : "false");
  return 0;
}
