# Cleanup verification — 23 October 2026

Fresh local source checks used Linux, Python 3.12.14 and Node 24.19.0. Python result: **37 passed**. The project lint and formatting checks passed. This is engineering verification, not a model-accuracy or business-performance result.

Existing numerical browser tests remain part of verification. The MIT dataset scope moved to NOTICE without changing rights.

## What changed and why

- Added current-status navigation and interview practice so a reader can find the supported run path and limits.
- Guarded local environment variants and workstation caches while keeping the example environment file.
- Added local Markdown link checks and a small documentation workflow; online checks report access failures separately from confirmed 404s.
- Preserved historical data, images, videos, evaluation outputs, benchmark labels and recorded failures.

The owner authorized this cleanup. Implementation and review used AI assistance; this does not complete the owner's independent exercises or human annotation.

## Recheck the exact source revision

Use the README's setup and test commands from a fresh clone. Read the checks on the cleanup pull request's exact head for hosted Docker/integration results. This local record does not assert that a future CI run already passed. Full hosted backends, paid-provider experiments and production operation are not newly claimed.
