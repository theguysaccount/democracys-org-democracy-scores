# Decisions

1. **Build on top, replace nothing.** democracys.org is live and complete. This companion indexes only what it adds
   (embeds, reproducibility); its country, ranking, compare and data pages are `noindex` with democracys.org as canonical.
   One setting (`COUNTRY_PAGES_INDEXABLE=true`) flips them if this edition ever carries newer data than the live site or the
   live site is retired.
2. **Static Python build, no Next.js.** The original pipeline is already Python; static SVG charts need no JavaScript, so
   embeds work everywhere and add no tracking.
3. **Keep the original build script.** Only its V-Dem constants moved into `release/vdem.json`; the v16 output is
   byte-identical to the original script's.
4. **Publish the reproducibility result as it is.** 18 of 153,720 values differ by 0.1 on rebuild (floating-point rounding
   at .x5 boundaries). The report lists them rather than hiding them; the check fails only beyond one rounding step.
5. **Adopt a new V-Dem release only with V-Dem's own citation.** CC BY-SA attribution must be exact, so the release watch
   reads "The proper citation for the vN dataset is: …" from V-Dem's dataset page and waits if it is absent. A new release
   replaces the whole series, because V-Dem advises against comparing values across versions.
6. **No email, no accounts, no analytics by default.** Matches the original's data-minimisation stance.
