/**
 * Open the persistent article detail drawer (DevLeadHunter-style stack).
 */
export function useOpenArticleDrawer() {
  const drawerStack = useGoupixDrawerStack()

  /**
   *
   */
  function openArticle(articleId: number, browseIds?: number[]): void {
    drawerStack.restoreStackFromSession()
    if (browseIds?.length) {
      drawerStack.setArticleBrowseList(browseIds)
    }
    drawerStack.pushArticle(articleId)
  }

  /**
   * Left-click opens the drawer; modified clicks keep normal navigation (new tab, etc.).
   */
  function openArticleFromClick(articleId: number, event: MouseEvent, browseIds?: number[]): void {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
      return
    }
    event.preventDefault()
    event.stopPropagation()
    openArticle(articleId, browseIds)
  }

  return { openArticle, openArticleFromClick }
}
