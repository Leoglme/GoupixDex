export default defineNuxtPlugin(async () => {
  const { refreshMe } = useAuth()
  await refreshMe()
})
