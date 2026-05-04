import type { AxiosInstance } from 'axios'
import type { Ref } from 'vue'

declare module '#app' {
  interface NuxtApp {
    $api: AxiosInstance
    /** HTTP client for the local Vinted worker (127.0.0.1) — desktop only */
    $vintedLocal: AxiosInstance
    $authToken: Ref<string | null>
  }
}

export {}
