/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Build-time platform selector: which study flow this build ships. */
  readonly VITE_PLATFORM?: string
  /** Where the education tool's issue reports are PUT. Overrides the default worker. */
  readonly VITE_ISSUE_REPORT_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
