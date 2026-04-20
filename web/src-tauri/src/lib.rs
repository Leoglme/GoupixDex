use std::path::PathBuf;
use std::sync::Mutex;
#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;
use tauri::Manager;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Worker Python local (`desktop_vinted_server.py`).
///
/// En `release` : binaire embarqué via `bundle.externalBin` (PyInstaller).
/// En `debug`   : `python` du PATH (ou `GOUPIX_PYTHON`) sur `api/desktop_vinted_server.py`.
struct VintedLocalChild(Mutex<Option<CommandChild>>);

#[derive(Clone, Debug, serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct BrowserInfo {
    chrome_available: bool,
    edge_available: bool,
    chrome_path: Option<String>,
    edge_path: Option<String>,
    chrome_install_url: String,
}

const CHROME_INSTALL_URL: &str = "https://www.google.com/intl/fr_fr/chrome/";

#[cfg(target_os = "windows")]
fn windows_program_files_candidates() -> Vec<String> {
    let mut roots: Vec<String> = Vec::new();
    for var in ["ProgramFiles", "ProgramFiles(x86)", "LocalAppData"] {
        if let Ok(val) = std::env::var(var) {
            if !val.is_empty() {
                roots.push(val);
            }
        }
    }
    roots
}

/// Cherche un exécutable navigateur sur le système (Chrome ou Edge) et renvoie
/// son chemin absolu si trouvé.
fn find_browser(kind: &str) -> Option<PathBuf> {
    #[cfg(target_os = "windows")]
    {
        let suffixes: &[&str] = match kind {
            "chrome" => &[
                r"Google\Chrome\Application\chrome.exe",
                r"Google\Chrome Beta\Application\chrome.exe",
                r"Google\Chrome Dev\Application\chrome.exe",
            ],
            "edge" => &[
                r"Microsoft\Edge\Application\msedge.exe",
                r"Microsoft\Edge Beta\Application\msedge.exe",
            ],
            _ => return None,
        };
        for root in windows_program_files_candidates() {
            for suf in suffixes {
                let p = PathBuf::from(&root).join(suf);
                if p.is_file() {
                    return Some(p);
                }
            }
        }
        return None;
    }
    #[cfg(target_os = "macos")]
    {
        let candidates: &[&str] = match kind {
            "chrome" => &[
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
            ],
            "edge" => &[
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            ],
            _ => return None,
        };
        for c in candidates {
            let p = PathBuf::from(c);
            if p.is_file() {
                return Some(p);
            }
        }
        return None;
    }
    #[cfg(all(not(target_os = "windows"), not(target_os = "macos")))]
    {
        let candidates: &[&str] = match kind {
            "chrome" => &[
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/snap/bin/chromium",
            ],
            "edge" => &["/usr/bin/microsoft-edge", "/usr/bin/microsoft-edge-stable"],
            _ => return None,
        };
        for c in candidates {
            let p = PathBuf::from(c);
            if p.is_file() {
                return Some(p);
            }
        }
        return None;
    }
}

fn detect_browsers() -> BrowserInfo {
    let chrome = find_browser("chrome");
    let edge = find_browser("edge");
    BrowserInfo {
        chrome_available: chrome.is_some(),
        edge_available: edge.is_some(),
        chrome_path: chrome.as_ref().map(|p| p.to_string_lossy().to_string()),
        edge_path: edge.as_ref().map(|p| p.to_string_lossy().to_string()),
        chrome_install_url: CHROME_INSTALL_URL.to_string(),
    }
}

#[tauri::command]
fn check_browser_availability() -> BrowserInfo {
    detect_browsers()
}

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// Tue le worker local et toute son arborescence de sous-processus (Chromium
/// lancés par nodriver notamment). Indispensable avant un remplacement sur
/// disque de `goupix-vinted-worker.exe` (mise à jour NSIS) pour ne pas se
/// retrouver avec un fichier verrouillé.
fn kill_worker_tree(child: CommandChild) {
    #[cfg(target_os = "windows")]
    {
        let pid = child.pid();
        let _ = std::process::Command::new("taskkill")
            .args(["/F", "/T", "/PID", &pid.to_string()])
            .creation_flags(CREATE_NO_WINDOW)
            .status();
    }
    let _ = child.kill();
}

/// Commande exposée au front-end pour fermer proprement le worker avant une
/// mise à jour Tauri (voir `DesktopUpdaterPanel.vue`).
#[tauri::command]
fn stop_local_worker(state: tauri::State<'_, VintedLocalChild>) -> Result<(), String> {
    let child_opt = match state.0.lock() {
        Ok(mut guard) => guard.take(),
        Err(_) => None,
    };
    if let Some(child) = child_opt {
        kill_worker_tree(child);
    }
    Ok(())
}

#[cfg(debug_assertions)]
fn dev_repo_api_dir() -> Option<PathBuf> {
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let api = manifest.parent()?.parent()?.join("api");
    if api.join("desktop_vinted_server.py").is_file() {
        Some(api)
    } else {
        None
    }
}

/// Nodriver Chromium profile directory for `tauri dev`: under the OS user data folder,
/// not inside the repo `api/` tree (avoids creating `vinted-nodriver-profile-dev/` there).
fn dev_vinted_nodriver_user_data_dir() -> Option<String> {
    #[cfg(target_os = "windows")]
    {
        let local = std::env::var("LOCALAPPDATA").ok()?;
        if local.is_empty() {
            return None;
        }
        Some(
            PathBuf::from(local)
                .join("GoupixDex")
                .join("vinted-nodriver-profile-dev")
                .to_string_lossy()
                .into_owned(),
        )
    }
    #[cfg(target_os = "macos")]
    {
        let home = std::env::var("HOME").ok()?;
        if home.is_empty() {
            return None;
        }
        Some(
            PathBuf::from(home)
                .join("Library")
                .join("Application Support")
                .join("GoupixDex")
                .join("vinted-nodriver-profile-dev")
                .to_string_lossy()
                .into_owned(),
        )
    }
    #[cfg(all(not(target_os = "windows"), not(target_os = "macos")))]
    {
        let home = std::env::var("HOME").ok()?;
        if home.is_empty() {
            return None;
        }
        Some(
            PathBuf::from(home)
                .join(".local")
                .join("share")
                .join("GoupixDex")
                .join("vinted-nodriver-profile-dev")
                .to_string_lossy()
                .into_owned(),
        )
    }
}

/// Builds the shell command for the Vinted worker, injecting `VINTED_CHROME_EXECUTABLE`
/// when Chrome or Edge is found.
fn build_worker_command(
    app: &tauri::AppHandle,
) -> Result<tauri_plugin_shell::process::Command, String> {
    let info = detect_browsers();
    // Prefer Chrome, then Edge; otherwise nodriver may auto-detect.
    let chrome_path = info.chrome_path.clone().or(info.edge_path.clone());

    #[cfg(debug_assertions)]
    {
        if let Some(api_dir) = dev_repo_api_dir() {
            let bin = std::env::var("GOUPIX_PYTHON").unwrap_or_else(|_| "python".to_string());
            let mut cmd = app
                .shell()
                .command(bin)
                .args(["desktop_vinted_server.py"])
                .current_dir(api_dir);
            // Local dev should not collide with an installed desktop app:
            // - dedicated worker port (18767)
            // - dedicated nodriver profile folder
            if std::env::var("GOUPIX_VINTED_LOCAL_PORT").is_err() {
                cmd = cmd.env("GOUPIX_VINTED_LOCAL_PORT", "18767");
            }
            if std::env::var("VINTED_USER_DATA_DIR").is_err() {
                if let Some(p) = dev_vinted_nodriver_user_data_dir() {
                    cmd = cmd.env("VINTED_USER_DATA_DIR", p);
                }
            }
            if let Some(p) = chrome_path {
                cmd = cmd.env("VINTED_CHROME_EXECUTABLE", p);
            }
            return Ok(cmd);
        }
        // Pas de dépôt local trouvé en dev → on tente quand même le sidecar (pratique pour
        // tester un build PyInstaller depuis un `tauri dev`).
    }

    let mut sidecar = app
        .shell()
        .sidecar("goupix-vinted-worker")
        .map_err(|e| format!("sidecar `goupix-vinted-worker` introuvable: {e}"))?;
    if let Some(p) = chrome_path {
        sidecar = sidecar.env("VINTED_CHROME_EXECUTABLE", p);
    }
    Ok(sidecar)
}

fn spawn_worker(app: &tauri::AppHandle) -> Result<CommandChild, String> {
    let cmd = build_worker_command(app)?;
    let (mut rx, child) = cmd
        .spawn()
        .map_err(|e| format!("Impossible de lancer le worker Vinted local: {e}"))?;

    // Drain stdout/stderr pour ne pas bloquer le worker (et logger côté Tauri).
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    eprintln!(
                        "[goupix-vinted-worker:out] {}",
                        String::from_utf8_lossy(&line).trim_end()
                    );
                }
                CommandEvent::Stderr(line) => {
                    eprintln!(
                        "[goupix-vinted-worker:err] {}",
                        String::from_utf8_lossy(&line).trim_end()
                    );
                }
                CommandEvent::Terminated(payload) => {
                    eprintln!(
                        "[goupix-vinted-worker] terminé (code={:?}, signal={:?})",
                        payload.code, payload.signal
                    );
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(child)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_shell::init())
        .manage(VintedLocalChild(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            check_browser_availability,
            stop_local_worker
        ])
        .setup(|app| {
            let handle = app.handle().clone();
            match spawn_worker(&handle) {
                Ok(child) => {
                    *app.state::<VintedLocalChild>()
                        .0
                        .lock()
                        .expect("vinted child mutex") = Some(child);
                }
                Err(e) => {
                    eprintln!(
                        "[GoupixDex] Worker Vinted local indisponible : {e}\n\
                         → En dev : depuis le dossier « api » lancer `python desktop_vinted_server.py`,\n\
                           ou définir GOUPIX_PYTHON.\n\
                         → En prod : le sidecar `goupix-vinted-worker` doit être inclus dans le bundle\n\
                           (étape PyInstaller dans la CI desktop)."
                    );
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                if let Ok(mut guard) = app.state::<VintedLocalChild>().0.lock() {
                    if let Some(child) = guard.take() {
                        kill_worker_tree(child);
                    }
                }
            }
        });
}
