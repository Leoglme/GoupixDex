import type { AxiosInstance } from 'axios'
import type { Ref } from 'vue'

declare module '#app' {
  interface NuxtApp {
    $api: AxiosInstance
    /** Client HTTP vers le worker Vinted local (127.0.0.1) — desktop uniquement */
    $vintedLocal: AxiosInstance
    $authToken: Ref<string | null>
  }
}

export {}
