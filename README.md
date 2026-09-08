# dd-education

This is an education fork of the [data donation task](https://github.com/d3i-infra/data-donation-task)
(itself a fork of [Feldspar](https://github.com/eyra/feldspar)). It is **not** a
research data-collection instrument: it is a standalone teaching tool that walks a
learner through requesting their own data download package (DDP) from a platform,
extracting it locally in the browser, and showing them what that platform actually
knows about them. There is no consent-to-donate step and no host to hand data to —
**nothing is donated.**

Run the tool at `/#/port`; a landing page, an about page, and a privacy-policy page
live at `/`, `/#/about`, and `/#/privacy-policy`. The platform menu offers YouTube,
Google, Netflix, Instagram, LinkedIn, WhatsApp, ChatGPT, and a General DDP Analyzer
for exports that don't fit those categories.

For detailed tutorials and API reference on the upstream architecture this fork
builds on, see the [documentation site](https://d3i-infra.github.io/data-donation-task/).

See [CHANGELOG.md](CHANGELOG.md) for the full list of changes and
[MIGRATION.md](MIGRATION.md) for how this fork was rebased onto upstream v3.

## Installation and local testing

### Pre-requisites

- Fork or clone this repo
- Install [Node.js](https://nodejs.org/en)
- Install [pnpm](https://pnpm.io/)
- Install [Python](https://www.python.org/)
- Install [Poetry](https://python-poetry.org/)

### Setup

```sh
pnpm install
cd packages/python && poetry install
```

### Check environment

```sh
pnpm doctor
```

### Start local dev server

```sh
VITE_PLATFORM=education pnpm start
# equivalently:
pnpm start:education
```

Visit [`http://localhost:3000/#/port`](http://localhost:3000/#/port).

### Dev-mode notes

A successful donation in dev mode does **not** navigate anywhere — that's
expected, not a hang. The flow exhausts, exits `0`, and the console prints
`[FakeBridge] received exit: 0=` and stays put. Navigating on completion is
the host's job in production (Next); `FakeBridge` only logs the exit, since
there is no host to hand off to locally.

The dev server also accepts the donation POST itself: `vite.config.ts`
registers a dev-only middleware (`devDonateSinkPlugin`, active only under
`pnpm start`, never in a production build) on `POST /data-submission` that
returns `200` and logs `[dev-donate-sink] POST /data-submission key=... bytes=...`
— without it, a bare `pnpm start` run 404s at the donate step, since Vite's
dev server has no such route by default. Playwright specs never touch this
sink; each one stubs `/data-submission` itself before driving the flow.

## Commands

### Development

| Command | Description |
|---|---|
| `VITE_PLATFORM=<platform> pnpm start` | Start dev server with hot reload |
| `VITE_PLATFORM=education pnpm start` / `pnpm start:education` | Start the education tool's dev server |
| `pnpm build:education` | Production build of the education tool |
| `pnpm generate-config <platform>` | Generate `configs/<platform>_config.json` from extractor docstrings |
| `pnpm run build` | Full production build (Python wheel + feldspar + data-collector) |
| `pnpm doctor` | Check environment setup (13 checks) |

Canary tests (`pnpm test:py`) exercise each extractor against real DDP exports.
Those exports are never committed: symlink them into `packages/python/tests/ddp/`
and see that directory's [`README.md`](packages/python/tests/ddp/README.md) for
the naming convention and which fixtures the canaries look for.

### Testing & Type Checking

| Command | Description |
|---|---|
| `pnpm test` | Run the full suite (JS unit tests, then Python) |
| `pnpm test:js` | Run the JS unit tests (`@eyra/feldspar` + `@eyra/data-collector`) |
| `pnpm test:py` | Run the Python tests |
| `pnpm test:py -- tests/test_specific.py -q` | Run specific Python tests |
| `pnpm typecheck:py` | Run Pyright type checker |
| `pnpm verify:py` | Run both tests + type checks |
| `pnpm test:e2e` | Run the Playwright end-to-end suite |

### Releases

| Command | Description |
|---|---|
| `pnpm release` | Build one zip per platform (auto-discovered from `configs/`) |
| `VITE_PLATFORM=<platform> pnpm release` | Build a release zip for a single platform |

Releases are created in `releases/`.

## Working with platforms

Generate a config for a platform, then edit it to suit your study:

```sh
pnpm generate-config instagram
# edit packages/python/port/configs/instagram_config.json
```

To add a new platform, copy `packages/python/port/platforms/example.py` as your starting point.

See the [documentation site](https://d3i-infra.github.io/data-donation-task/) for full tutorials.

## Localization status

The participant-facing UI is localized in two independent layers. They are
translated by different people, cover different locales, and fall back
separately — a page can render German chrome around English table titles.

| UI locale | **Framework chrome**<br>buttons, consent prose, error pages<br>*(ships in this repo)* | **Study content**<br>table titles, column headers, viz titles<br>*(per platform, yours to write)* |
|---|---|---|
| `en` | complete — **the fallback** | **required**; validation fails without it |
| `nl` | complete | shipped for the platforms in this repo |
| `de` | ⚠️ **provisional** — machine-translated, pending native-speaker review | — falls back to English, live |
| `it` | ⚠️ **provisional** — machine-translated, pending native-speaker review | — falls back to English, live |
| `es` | ⚠️ **provisional** — machine-translated, pending native-speaker review | — falls back to English, live |

**Fallback is per string, at render time.** A locale that a given text bundle
does not carry resolves to `en` for that string only; there is no
whole-page language switch and no build step involved. So a `de` participant
sees translated chrome and English table titles until you translate the tables
in `configs/<platform>_config.json`.

Reviewing the provisional translations — register conventions and the specific
judgment calls that need a native speaker's ruling — is documented in
[`docs/localization-translation-notes.md`](docs/localization-translation-notes.md).

Checking your own coverage: `pnpm generate-config <platform>` and `pnpm release`
both run the config validator with `--report`, which prints a per-locale
coverage matrix (provisional locales marked `*`) and fails the build if a text
bundle is missing English.

### UI locale is not `platform_info.languages`

These are two unrelated things and are **never synced**:

- The **UI locale** (`en`/`nl`/`de`/`it`/`es`) is what language the interface
  renders in. It comes from the host at session start.
- **`platform_info.languages`** in a platform config — and `Language` in
  `port/helpers/validate.py` — describe the language of the *participant's DDP
  export*, i.e. what language the filenames and headers inside their downloaded
  zip are in. It is a parsing concern.

A participant can perfectly well read the UI in Spanish while donating a
Dutch-language Instagram export. Changing one must never change the other.

### Setting the locale in development

In production the locale comes only from the host's `live-init` message; there
is no URL override. In **dev builds only**, a `?locale=` query parameter
overrides it — this is the dev-server convenience and the Playwright e2e
injection point:

```
http://localhost:3000/?locale=nl
```

The value is normalized once, at the host boundary, before anything sees it:

| Requested | Rendered | Why |
|---|---|---|
| `nl` | `nl` | supported |
| `es-ES`, `es_ES`, `ES` | `es` | region and case are stripped |
| `ro` | `en` | not a supported UI locale → default |
| *(absent)* | `en` | default |

The supported set lives in
`packages/data-collector/src/locale/ui_locales.json` (mirrored into the Python
package; a test fails if the two drift). See ADR-0038.

## Architecture

See `docs/decisions/` for architectural decision records. Key structure:

```
packages/
  python/         Python extraction scripts (per-platform)
  feldspar/       Workflow UI framework (upstream Eyra)
  data-collector/ Host app / dev server with custom UI components
```

### Platform extraction flow

Each platform (Instagram, Facebook, YouTube, etc.) has a `FlowBuilder` subclass in `packages/python/port/platforms/` that handles:

1. File prompt → participant uploads DDP zip
2. Validation → DDP category detection via `DDP_CATEGORIES`
3. Extraction → `ZipArchiveReader` reads files from cached archive inventory
4. Consent → participant reviews extracted tables
5. Donation → data sent to host platform

In this fork the consent step runs in review-only mode: step 5 never fires.
The participant inspects the extracted tables and can report an issue, but
nothing is donated. The `education` platform module (ADR-0041) composes the
per-platform flows above into the menu below.

### Supported platforms

LinkedIn, Instagram, Facebook, YouTube, TikTok, Netflix, ChatGPT, WhatsApp, X, Chrome
are the platforms this codebase's extractors support. This fork's menu wires up a
subset of them plus a Google Takeout flow and a General DDP Analyzer: YouTube,
Google, Netflix, Instagram, LinkedIn, WhatsApp, ChatGPT, General DDP Analyzer.

## Citation

If you use this repository in your research, please cite it as follows:

```
@article{Boeschoten2023,
  doi = {10.21105/joss.05596},
  url = {https://doi.org/10.21105/joss.05596},
  year = {2023},
  publisher = {The Open Journal},
  volume = {8},
  number = {90},
  pages = {5596},
  author = {Laura Boeschoten and Niek C. de Schipper and Adriënne M. Mendrik and Emiel van der Veen and Bella Struminskaya and Heleen Janssen and Theo Araujo},
  title = {Port: A software tool for digital data donation},
  journal = {Journal of Open Source Software}
}
```

You can find the full citation details in the [`CITATION.cff`](CITATION.cff) file.
