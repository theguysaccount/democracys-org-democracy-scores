# State (2026-11-22)

- **Original:** Next.js (vinext) on Cloudflare Workers via OpenAI Sites, Recharts, data built by one Python script from the
  V-Dem v16 ZIP. **Live at democracys.org** (all routes, including trends, toolkit, briefs and the country API; serves V-Dem v16).
- **Local source gap:** the shipped trends/toolkit/brief/API routes and `product-tools.css` were deleted from the working
  tree but are still staged in the original git index (`git checkout -- <path>` restores them). Not needed here: the live
  site serves them and this companion does not copy the app.
- **Reproducible:** rebuilding from V-Dem's official file (SHA-256 verified) on a Linux runner reproduces all 153,720
  published values exactly. On macOS, 18 derived lower-bound values come out 0.1 different (floating-point rounding at a
  .x5 boundary), which is why the check tolerates one rounding step.
- **Reused:** the build script (release-parameterised, byte-identical v16 output), the published data, the share image.
- **Added:** embeddable charts, reproducibility report, V-Dem release watch, static country pages, rankings, comparison
  and per-country files, weekly self-test.
