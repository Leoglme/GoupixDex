; Hooks NSIS personnalisés pour le bundle Tauri Windows.
;
; Contexte : GoupixDex embarque un sidecar PyInstaller `goupix-vinted-worker.exe`
; qui lance lui-même Chromium via nodriver. Pendant une mise à jour, NSIS doit
; réécrire ce .exe ; s'il est encore en mémoire (ou si un des Chromium enfants
; garde un handle), l'install échoue avec :
;   « Error opening file for writing: ...\goupix-vinted-worker.exe »
;
; Côté app Tauri on appelle déjà la commande `stop_local_worker` avant
; `downloadAndInstall`, mais ce hook joue le rôle de filet de sécurité
; (install manuel depuis GitHub Releases, app crashée, anciens orphelins...).

!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Arrêt du worker GoupixDex s'il est en cours d'exécution..."
  ; /F = force, /T = tue aussi l'arborescence (Chromium lancés par nodriver).
  ; On redirige la sortie vers nul pour rester silencieux si aucun process n'est trouvé.
  nsExec::Exec 'cmd /C taskkill /F /T /IM goupix-vinted-worker.exe >nul 2>&1'
  Pop $0
  Sleep 500
!macroend
