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
        header: 'p-3 sm:p-4',
        body: 'p-3 sm:p-4',
        footer: 'p-3 sm:p-4',
      },
    },
    modal: {
      slots: {
        // Above GoupixDexAppDrawer (backdrop z-40, panel z-50) and command palette (z-70).
        overlay: 'bg-(--app-overlay) z-[100]',
        content: 'rounded-xl z-[101]',
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
    select: {
      slots: {
        base: 'cursor-pointer',
        item: 'cursor-pointer',
      },
    },
    selectMenu: {
      slots: {
        base: 'cursor-pointer',
        item: 'cursor-pointer',
      },
    },
    inputMenu: {
      slots: {
        base: 'cursor-pointer',
        item: 'cursor-pointer',
      },
    },
    dropdownMenu: {
      slots: {
        item: 'cursor-pointer',
      },
    },
    progress: {
      slots: {
        root: 'flex w-full flex-col gap-2',
        base: 'relative w-full overflow-hidden rounded-full bg-(--app-surface-2)',
        indicator: 'rounded-full bg-(--app-accent) transition-[width] duration-200 ease-out',
      },
      variants: {
        size: {
          xs: { base: 'h-0.5' },
          sm: { base: 'h-1' },
          md: { base: 'h-1.5' },
          lg: { base: 'h-2' },
          xl: { base: 'h-3' },
        },
      },
      defaultVariants: {
        size: 'sm',
        animation: 'carousel',
      },
    },
  },
})
