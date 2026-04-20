; Custom NSIS hooks for the Tauri Windows bundle.
;
; GoupixDex ships a PyInstaller sidecar `goupix-vinted-worker.exe` that itself
; spawns Chromium through nodriver. During an update NSIS needs to overwrite
; that .exe; if it (or one of its Chromium children) still holds a handle the
; install fails with:
;   "Error opening file for writing: ...\goupix-vinted-worker.exe"
;
; The Tauri app already calls the `stop_local_worker` command before
; `downloadAndInstall`, but this hook is the safety net (manual install from
; GitHub Releases, crashed app, leftover orphans, ...).

!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Stopping GoupixDex worker if it is still running..."
  ; /F = force, /T = kill the whole tree (Chromium spawned by nodriver).
  ; Output redirected to nul so the installer stays silent if no process exists.
  nsExec::Exec 'cmd /C taskkill /F /T /IM goupix-vinted-worker.exe >nul 2>&1'
  Pop $0
  Sleep 500
!macroend
