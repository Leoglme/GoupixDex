/**
 * Chemin interne demandé en paramètre d'URL, ou le repli : jamais une adresse hors de GoupixDex.
 * @param {unknown} requestedPath - Valeur du paramètre (`back`…).
 * @param {string} fallbackPath - Chemin utilisé quand la valeur n'est pas un chemin interne.
 * @returns {string} Le chemin où naviguer.
 */
export function internalPathOrFallback(requestedPath: unknown, fallbackPath: string): string {
  return typeof requestedPath === 'string' && requestedPath.startsWith('/') && !requestedPath.startsWith('//')
    ? requestedPath
    : fallbackPath
}
