# Third-party components

LagLens's own source is MIT licensed. Dependencies retain their original licenses.

- **Intel PresentMon 2.6.0**, GameTechDev contributors. MIT license; see `vendor/PresentMon-LICENSE.txt`. Official console executable is downloaded by `scripts/fetch_vendor.py`, verified against its published release SHA-256, and included in portable distributions. It is not stored in the source repository. Source: https://github.com/GameTechDev/PresentMon
- **Public Sans**, the Public Sans Project Authors. SIL Open Font License 1.1; bundled with `src/laglens/ui/fonts/PublicSans-OFL.txt`. Source: https://github.com/google/fonts/tree/main/ofl/publicsans
- **IBM Plex Mono**, IBM Corp. SIL Open Font License 1.1; bundled with `src/laglens/ui/fonts/IBMPlexMono-OFL.txt`. Source: https://github.com/google/fonts/tree/main/ofl/ibmplexmono
- **psutil** (BSD-3-Clause), **pywebview** (BSD-3-Clause), **pythonnet** (MIT), **clr-loader** (MIT), and **Bottle** (MIT) are installed from PyPI. Their installed license metadata accompanies the packaged runtime where supplied by their distributions.
- **Python**, Python Software Foundation license; packaged by PyInstaller. **PyInstaller** uses GPL with a bootloader exception permitting distributed applications under their chosen license.

LagLens is not affiliated with Intel, Microsoft, game publishers, or GPU vendors.
