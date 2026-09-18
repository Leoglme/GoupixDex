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
        base: 'cursor-pointer rounded-full font-semibold transition-all disabled:cursor-not-allowed',
      },
    },
    card: {
      slots: {
        root: 'rounded-xl shadow-none',
        header: 'p-4 sm:px-4',
        body: 'p-4 sm:p-4',
        footer: 'p-4 sm:px-4',
      },
    },
    modal: {
      slots: {
        overlay: 'bg-(--app-overlay)',
        content: 'rounded-xl',
      },
    },
    slideover: {
      slots: {
        overlay: 'bg-(--app-overlay)',
      },
    },
    badge: {
      slots: {
        base: 'rounded-full font-medium',
      },
    },
    tabs: {
      slots: {
        trigger: 'cursor-pointer',
      },
    },
  },
})
