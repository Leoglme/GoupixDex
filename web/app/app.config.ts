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
        root: 'rounded-xl shadow-none ring ring-default !divide-y-0 bg-(--app-surface)',
        header: 'p-5 pb-0',
        body: 'p-5',
        footer: 'p-5 pt-4',
      },
      variants: {
        variant: {
          outline: { root: '!divide-y-0' },
          soft: { root: '!divide-y-0' },
          subtle: { root: '!divide-y-0' },
        },
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
    dashboardPanel: {
      slots: {
        body: 'flex flex-col gap-4 sm:gap-6 flex-1 min-w-0 overflow-y-auto overflow-x-hidden p-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] sm:p-6',
      },
    },
    dashboardNavbar: {
      slots: {
        root: 'h-(--ui-header-height) shrink-0 flex items-center justify-between border-b border-default px-3 pt-[max(0px,env(safe-area-inset-top))] sm:px-6 gap-1.5',
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
