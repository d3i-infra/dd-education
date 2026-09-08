/**
 * The one place `import.meta.env` is read.
 *
 * Vite substitutes `import.meta.env.X` at build time. Jest runs these modules as
 * CommonJS and cannot so much as parse `import.meta`, so every module that wanted a
 * build-time setting would be untestable. Keeping the reads here means one module is
 * substituted under test (see `jest.config.js`'s `moduleNameMapper` and
 * `src/test_support/build_env_mock.ts`) rather than every module that has a setting.
 *
 * Read through this object rather than destructuring it at module scope, so a test can
 * set a value before the code under test looks at it.
 */
export interface BuildEnv {
  /** True in `pnpm start`, false in a production build. */
  readonly DEV?: boolean
  /** Which study flow this build ships; `education` for the education tool. */
  VITE_PLATFORM?: string
  /** Where the education tool PUTs a submitted issue report. */
  VITE_ISSUE_REPORT_URL?: string
}

export const buildEnv: BuildEnv = import.meta.env as BuildEnv
