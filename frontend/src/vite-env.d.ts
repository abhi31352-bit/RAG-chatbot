/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL for API calls. Empty means "use the Vite dev proxy". */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
