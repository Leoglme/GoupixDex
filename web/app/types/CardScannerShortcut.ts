export type CardScannerShortcut = {
  setScanPageCameraOpener: (openCamera: (() => void) | null) => void
  openCardScanner: () => void
}
