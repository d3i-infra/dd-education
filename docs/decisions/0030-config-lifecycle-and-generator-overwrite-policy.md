---
status: accepted
date: "2026-05-22"
tags:
    - configuration
    - lifecycle
    - generator
category: Python architecture
applies_to:
    - scripts/generate_port_config.py
    - scripts/gen_port_config.sh
    - packages/python/port/configs/**
priority: default
---

# Config lifecycle and generator overwrite policy

## Decision

Extractor docstrings are the bootstrap source for a config; after that initial generation the curated JSON is the study-specific source of truth. `scripts/generate_port_config.py` refuses to overwrite an existing `configs/<platform>_config.json` (exits non-zero); re-bootstrapping requires an explicit `rm` of the file first.

## Guidance

- When writing a config, the generator must never overwrite or merge into an existing `configs/<platform>_config.json`; it exits non-zero and leaves the file untouched. `pnpm generate-config <platform>` (via `scripts/gen_port_config.sh`) is therefore safe but intentionally *non-idempotent* — it either creates the file or fails once it exists. The `--stdout` mode writes no file and is outside this policy.
- To re-bootstrap a platform, delete the config first (`rm configs/<platform>_config.json`), then regenerate — a deliberate two-step action.
- The hand-editable surface of a config is: title, description, headers, `variables` (a subset and ordering of columns), table inclusion/exclusion, and visualizations — the runtime honors these because it iterates only the config's tables. Hand-edited and externally tool-generated (e.g. the external Selector) configs are treated identically at runtime.
- Adding a new extractor does not propagate into an existing config; the researcher must notice and rm-and-regenerate (there is no merge tooling).
- The education fork commits its menu platforms' edited configs (`configs/{education,chatgpt,youtube,netflix,instagram,linkedin,whatsapp,google}_config.json`) under a `.gitignore` allowlist carved out of the general `*_config.json` ignore rule — the generator's no-overwrite policy above is exactly what makes committing a hand-curated config safe: a future `pnpm generate-config` on an already-committed file still refuses to overwrite it.

## Why

After bootstrap, researchers curate the JSON heavily — titles, removed tables, `variables` restricted to IRB-approved columns. That curation *is* the study design and must never be silently destroyed, so after generation the JSON, not the docstring, is the source of truth: the generator bootstraps once and then refuses to overwrite. Merge-on-regenerate was rejected — deciding which entries are "the researcher's" is ambiguous and fails subtly. Costs: a new extractor doesn't reach an existing config without rm-and-regenerate (which loses that file's curation), and "start over" is a deliberate two-step so the default action can never destroy curated content.

## Checks

- Behavioral test: `generate_port_config.py` exits non-zero and leaves an existing `configs/<platform>_config.json` byte-for-byte unchanged when the file already exists.
