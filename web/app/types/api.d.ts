import type { AxiosInstance } from 'axios'
import type { Ref } from 'vue'

declare module '#app' {
  interface NuxtApp {
    $api: AxiosInstance
    $authToken: Ref<string | null>
  }
}

export {}
