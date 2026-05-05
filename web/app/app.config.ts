export default defineAppConfig({
  /**
   * Native SVG rendering: `css` mode (masks / fonts) can clip glyphs in WebView2 (Tauri app),
   * especially on multi-arc “refresh” icons.
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
