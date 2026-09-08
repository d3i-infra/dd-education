---
status: accepted
date: "2026-09-08"
tags:
    - education
    - composite-platform
    - menu-dispatch
category: Python architecture
applies_to:
    - packages/python/port/platforms/education.py
    - packages/python/port/platforms/general_ddp_analyzer.py
    - packages/python/port/configs/education_config.json
    - packages/python/port/configs/google_config.json
    - .github/workflows/gh-pages.yml
    - packages/data-collector/src/index.tsx
priority: invariant
companions:
    - packages/python/tests/test_education_platform.py
checks:
    - desc: education.py never yields ph.donate directly
      grep: 'ph\.donate\('
      in: ["packages/python/port/platforms/education.py"]
      expect: absent
---

# Education is a composite platform module

## Decision

`platforms/education.py` is a composite platform module selected by `VITE_PLATFORM=education`: `process()` loops a participant-facing platform-selection menu (`ph.generate_platform_selection_menu`), instantiates the chosen platform's own `FlowBuilder` subclass, sets `donate_enabled=False` and `instruction_image` on that instance, and returns to the menu on `TaskIncompleteError` or after the flow's own completion — the module never yields `ph.donate` itself.

## Guidance

- `PLATFORMS: dict[str, PlatformEntry]` maps a menu label to `(module, cls, instruction_image, review_description)`; `_build_flow()` imports that module, instantiates `cls(session_id)`, and sets `donate_enabled = False` / `instruction_image` on the *instance* after construction, per ADR-0012 — a platform class never sets these on itself.
- `process()` catches `TaskIncompleteError` from the chosen flow and `continue`s back to the menu instead of propagating it; a completed flow renders `ph.generate_platform_completion_prompt()` (a resolving `PropsUIPromptConfirm`) and also loops back. The loop has no exit: closing the tab is the only way out, because the Pages deployment has no host to hand a `CommandSystemExit` to — `education.py`'s `process()` is the ADR-0025 exception, and the completion prompt is not an end page.
- `EXTRACTOR_REGISTRY = {}` and `configs/education_config.json` has no tables: `education.py` extracts nothing itself, it only dispatches to other platforms' own extraction. It is a composite module that keeps only `EXTRACTOR_REGISTRY` (empty, present for the validator) and `process()` — there is no `extraction()` and no `EducationFlow` subclass — an explicit exception to ADR-0029's four-symbol convention, not an instance of it.
- `YouTubeOnlyGoogleFlow(GoogleFlow)` sets `self.platform_name = "YouTube"` and re-runs `_initialize_ui_text()` after `super().__init__()` so every UI_TEXT/header entry re-derives from "YouTube"; `extract_data()` then filters the inherited Google extraction down to tables whose `id` starts with `youtube_`, returning an empty result (not the parent's error) when no YouTube tables are present.
- `.github/workflows/gh-pages.yml` builds and publishes exactly one `VITE_PLATFORM=education` bundle on push to `master`; `configs/google_config.json` stays committed because the menu's plain "Google" entry (`GoogleFlow` unmodified) still needs it, alongside `education_config.json` for the composite module itself.
- `index.tsx`'s hash router (`/`, `/about`, `/privacy-policy`, `/port`) exists because this deployment has no host page around the tool — `education.py`'s menu-and-return design and the router's own landing/about routes are both consequences of the same "no host" fact; don't reintroduce a host-dependent completion page here.

## Why

The Pages deployment has no Eyra Next host: nothing renders a "task complete" checkmark or receives a donation. Composing existing platform flows behind a menu, with donation disabled and completion resolved in-iframe, lets the same battle-tested extraction code teach without either fabricating a host or duplicating every platform's flow. An empty `EXTRACTOR_REGISTRY` and a table-less config keep `education.py` inside the standard platform-module shape (ADR-0029) rather than inventing a second dispatch mechanism in `script.py`; the cost is a module that reads like it does something it doesn't (extract), so `## Checks` pins that it never donates.

## Checks

- Confirm `education.py` never yields `ph.donate` (frontmatter check below).
- Confirm every `PLATFORMS` entry imports and subclasses `FlowBuilder`: `tests/test_education_platform.py::test_every_menu_entry_imports`.
