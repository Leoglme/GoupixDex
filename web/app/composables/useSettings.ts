export function useSettings() {
  const { $api } = useNuxtApp()

  async function getSettings() {
    const { data } = await $api.get<{ margin_percent: number }>('/settings')
    return data
  }

  async function updateSettings(marginPercent: number) {
    const { data } = await $api.put<{ margin_percent: number }>('/settings', {
      margin_percent: marginPercent
    })
    return data
  }

  return { getSettings, updateSettings }
}
