/// <reference types="vite/client" />

    interface ImportMetaEnv {
      readonly VITE_API_BASE_URL: string;
      readonly VITE_CLERK_PUBLISHABLE_KEY: string;
      // Declared explicitly (rather than left to vite/client's index signature)
      // so a typo like VITE_SENTRY_DSN vs VITE_SENTRY_URL is a type error instead
      // of a silently disabled error reporter in production.
      readonly VITE_SENTRY_DSN: string;
      readonly VITE_POSTHOG_KEY: string;
      readonly VITE_POSTHOG_HOST: string;
      // Must match the backend's APP_VERSION so Sentry groups a browser error
      // and the API stack trace it hit under one release. Empty = untagged.
      readonly VITE_APP_VERSION: string;
    }


interface ImportMeta {
  readonly env: ImportMetaEnv;
}
