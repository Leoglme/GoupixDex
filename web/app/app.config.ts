export default defineAppConfig({
  /**
   * Rendu SVG natif : le mode `css` (masques / fonts) peut produire des glyphes tronqués
   * dans WebView2 (app Tauri), notamment sur les icônes « refresh » à arcs multiples.
   */
  icon: {
    mode: 'svg',
  },
  ui: {
    colors: {
      primary: 'primary',
      neutral: 'zinc',
    },
    button: {
      slots: {
        base: 'cursor-pointer',
      },
    },
  },
})
