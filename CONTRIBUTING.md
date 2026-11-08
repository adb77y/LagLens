# Contributing

Use Python 3.11+ and run `python -m unittest discover -s tests -v`. Keep UI code dependency-free and bundle any required assets locally.

For a bug report, include LagLens version, Windows version, GPU/driver, selected rendering API, steps to reproduce and a minimal capture you have reviewed for private information. Do not upload full game assets, saves, tokens or executable paths.

For analysis changes, add a small deterministic test that proves the rule and its failure cases. Include missing-value behavior and explain confidence labels. Never replace an unavailable reading with a guessed measurement or describe sample captures as real benchmarks.

For UI changes, verify keyboard access, first-run empty states, error states, and desktop/tablet/phone layouts. Keep figures and units consistent with the methodology.
