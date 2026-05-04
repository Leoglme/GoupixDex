use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::Duration;
#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;
use tauri::Manager;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Local Python workers (`desktop_vinted_server.py`, `desktop_amazon_server.py`).
///
/// In `release`: embedded binaries via `bundle.externalBin` (PyInstaller).
/// In `debug`  : `python` from PATH (or `GOUPIX_PYTHON`) running scripts in `api/`.
struct DesktopWorkers(Mutex<DesktopWorkersInner>);

struct DesktopWorkersInner {
    vinted: Option<CommandChild>,
    amazon: Option<CommandChild>,
}

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

/// Look for a browser executable on the system (Chrome or Edge) and return
/// its absolute path if found.
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

/// Kill a local worker and its whole child process tree (Chromium spawned by
/// nodriver in particular). Required before overwriting sidecar binaries on disk.
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

/// Ports workers locaux : alignés sur `spawn_*` / `.env` (valeurs par défaut dev Tauri).
fn vinted_local_port() -> u16 {
    std::env::var("GOUPIX_VINTED_LOCAL_PORT")
        .ok()
        .and_then(|s| s.trim().parse().ok())
        .unwrap_or(18767)
}

fn amazon_local_port() -> u16 {
    std::env::var("GOUPIX_AMAZON_LOCAL_PORT")
        .ok()
        .and_then(|s| s.trim().parse().ok())
        .unwrap_or(18768)
}

/// Tue tout processus qui **écoute** déjà sur ces ports (instance Python orpheline, ancien worker).
/// Sans ça, `restart_local_workers` ne fait que tuer les `CommandChild` suivis — insuffisant si le
/// port est tenu par un autre PID (ex. script lancé à la main).
#[cfg(target_os = "windows")]
fn kill_processes_listening_on_ports(ports: &[u16]) {
    if ports.is_empty() {
        return;
    }
    let list = ports
        .iter()
        .map(|p| p.to_string())
        .collect::<Vec<_>>()
        .join(",");
    let script = format!(
        r#"$ports = @({list}); foreach ($port in $ports) {{
  $pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($id in $pids) {{
    if ($null -ne $id -and $id -gt 0) {{ Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }}
  }}
}}"#
    );
    let _ = std::process::Command::new("powershell.exe")
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle",
            "Hidden",
            "-Command",
            &script,
        ])
        .creation_flags(CREATE_NO_WINDOW)
        .status();
}

#[cfg(not(target_os = "windows"))]
fn kill_processes_listening_on_ports(_ports: &[u16]) {}

/// Attend que les deux workers acceptent une connexion TCP (bind réussi).
fn verify_local_workers_accept_tcp(vinted_port: u16, amazon_port: u16) -> Result<(), String> {
    let attempts: u32 = 14;
    let pause = Duration::from_millis(200);
    let timeout = Duration::from_millis(900);
    let addr_v: SocketAddr = format!("127.0.0.1:{vinted_port}")
        .parse()
        .map_err(|_| "adresse Vinted invalide".to_string())?;
    let addr_a: SocketAddr = format!("127.0.0.1:{amazon_port}")
        .parse()
        .map_err(|_| "adresse Amazon invalide".to_string())?;

    for i in 0..attempts {
        let v_ok = std::net::TcpStream::connect_timeout(&addr_v, timeout).is_ok();
        let a_ok = std::net::TcpStream::connect_timeout(&addr_a, timeout).is_ok();
        if v_ok && a_ok {
            return Ok(());
        }
        if i + 1 < attempts {
            std::thread::sleep(pause);
        }
    }
    Err(format!(
        "Les ports {vinted_port} et {amazon_port} ne répondent pas après redémarrage (voir la console : souvent « port déjà utilisé » ou erreur Python)."
    ))
}

/// Stop local workers (Vinted + Amazon) before a Tauri app update.
#[tauri::command]
fn stop_local_worker(state: tauri::State<'_, DesktopWorkers>) -> Result<(), String> {
    let mut inner = match state.0.lock() {
        Ok(g) => g,
        Err(_) => return Ok(()),
    };
    if let Some(child) = inner.vinted.take() {
        kill_worker_tree(child);
    }
    if let Some(child) = inner.amazon.take() {
        kill_worker_tree(child);
    }
    Ok(())
}

/// Arrête puis relance les deux workers (utile en `tauri dev` après changement de code Python ou port bloqué).
#[tauri::command]
fn restart_local_workers(
    app: tauri::AppHandle,
    state: tauri::State<'_, DesktopWorkers>,
) -> Result<(), String> {
    let vinted_port = vinted_local_port();
    let amazon_port = amazon_local_port();

    {
        let mut inner = state
            .0
            .lock()
            .map_err(|_| "mutex desktop workers".to_string())?;
        if let Some(child) = inner.vinted.take() {
            kill_worker_tree(child);
        }
        if let Some(child) = inner.amazon.take() {
            kill_worker_tree(child);
        }
    }

    kill_processes_listening_on_ports(&[vinted_port, amazon_port]);
    std::thread::sleep(Duration::from_millis(500));

    let mut errs: Vec<String> = Vec::new();

    match spawn_vinted_worker(&app) {
        Ok(child) => {
            app.state::<DesktopWorkers>()
                .0
                .lock()
                .expect("desktop workers mutex")
                .vinted = Some(child);
        }
        Err(e) => errs.push(format!("Vinted: {e}")),
    }
    match spawn_amazon_worker(&app) {
        Ok(child) => {
            app.state::<DesktopWorkers>()
                .0
                .lock()
                .expect("desktop workers mutex")
                .amazon = Some(child);
        }
        Err(e) => errs.push(format!("Amazon: {e}")),
    }

    if !errs.is_empty() {
        let mut inner = state
            .0
            .lock()
            .map_err(|_| "mutex desktop workers".to_string())?;
        if let Some(child) = inner.vinted.take() {
            kill_worker_tree(child);
        }
        if let Some(child) = inner.amazon.take() {
            kill_worker_tree(child);
        }
        return Err(errs.join(" ; "));
    }

    match verify_local_workers_accept_tcp(vinted_port, amazon_port) {
        Ok(()) => {
            eprintln!("[GoupixDex] Workers locaux redémarrés (Vinted + Amazon).");
            Ok(())
        }
        Err(msg) => {
            let mut inner = state
                .0
                .lock()
                .map_err(|_| "mutex desktop workers".to_string())?;
            if let Some(child) = inner.vinted.take() {
                kill_worker_tree(child);
            }
            if let Some(child) = inner.amazon.take() {
                kill_worker_tree(child);
            }
            Err(msg)
        }
    }
}

#[cfg(debug_assertions)]
fn dev_repo_api_dir_with(script: &str) -> Option<PathBuf> {
    if let Ok(override_dir) = std::env::var("GOUPIX_API_DIR") {
        let trimmed = override_dir.trim();
        if !trimmed.is_empty() {
            let api = PathBuf::from(trimmed);
            if api.join(script).is_file() {
                return Some(api);
            }
        }
    }
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let api = manifest.parent()?.parent()?.join("api");
    if api.join(script).is_file() {
        Some(api)
    } else {
        None
    }
}

/// Compat: legacy name for detecting the `api/` folder (Vinted worker).
#[cfg(debug_assertions)]
fn dev_repo_api_dir() -> Option<PathBuf> {
    dev_repo_api_dir_with("desktop_vinted_server.py")
}

/// Nodriver Chromium profile directory for `tauri dev`: under the OS user data folder.
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
fn build_vinted_worker_command(
    app: &tauri::AppHandle,
) -> Result<tauri_plugin_shell::process::Command, String> {
    let info = detect_browsers();
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

fn build_amazon_worker_command(
    app: &tauri::AppHandle,
) -> Result<tauri_plugin_shell::process::Command, String> {
    #[cfg(debug_assertions)]
    {
        if let Some(api_dir) = dev_repo_api_dir_with("desktop_amazon_server.py") {
            let bin = std::env::var("GOUPIX_PYTHON").unwrap_or_else(|_| "python".to_string());
            eprintln!(
                "[GoupixDex] Worker Amazon : exécutable `{} desktop_amazon_server.py` (cwd={})",
                bin,
                api_dir.display()
            );
            let cmd = app
                .shell()
                .command(bin)
                .args(["desktop_amazon_server.py"])
                .current_dir(api_dir);
            return Ok(cmd);
        }
        eprintln!(
            "[GoupixDex] Worker Amazon : aucun dossier `api/` trouvé pour ce script — utilisation du sidecar.\n\
             Astuces : définir `GOUPIX_API_DIR` vers votre dossier `api`, ou `npm run amazon-worker:sync-dist` après PyInstaller."
        );
    }

    app.shell()
        .sidecar("goupix-amazon-worker")
        .map_err(|e| format!("sidecar `goupix-amazon-worker` introuvable: {e}"))
}

fn spawn_vinted_worker(app: &tauri::AppHandle) -> Result<CommandChild, String> {
    let cmd = build_vinted_worker_command(app)?;
    let (mut rx, child) = cmd
        .spawn()
        .map_err(|e| format!("Impossible de lancer le worker Vinted local: {e}"))?;

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

fn spawn_amazon_worker(app: &tauri::AppHandle) -> Result<CommandChild, String> {
    let cmd = build_amazon_worker_command(app)?;
    let (mut rx, child) = cmd
        .spawn()
        .map_err(|e| format!("Impossible de lancer le worker Amazon local: {e}"))?;

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    eprintln!(
                        "[goupix-amazon-worker:out] {}",
                        String::from_utf8_lossy(&line).trim_end()
                    );
                }
                CommandEvent::Stderr(line) => {
                    eprintln!(
                        "[goupix-amazon-worker:err] {}",
                        String::from_utf8_lossy(&line).trim_end()
                    );
                }
                CommandEvent::Terminated(payload) => {
                    eprintln!(
                        "[goupix-amazon-worker] terminé (code={:?}, signal={:?})",
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
        .manage(DesktopWorkers(Mutex::new(DesktopWorkersInner {
            vinted: None,
            amazon: None,
        })))
        .invoke_handler(tauri::generate_handler![
            check_browser_availability,
            stop_local_worker,
            restart_local_workers
        ])
        .setup(|app| {
            let handle = app.handle().clone();

            match spawn_vinted_worker(&handle) {
                Ok(child) => {
                    app.state::<DesktopWorkers>()
                        .0
                        .lock()
                        .expect("desktop workers mutex")
                        .vinted = Some(child);
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

            match spawn_amazon_worker(&handle) {
                Ok(child) => {
                    app.state::<DesktopWorkers>()
                        .0
                        .lock()
                        .expect("desktop workers mutex")
                        .amazon = Some(child);
                }
                Err(e) => {
                    eprintln!(
                        "[GoupixDex] Worker Amazon local indisponible : {e}\n\
                         → En dev : depuis le dossier « api » lancer `python desktop_amazon_server.py`,\n\
                           ou définir GOUPIX_PYTHON.\n\
                         → En prod : le sidecar `goupix-amazon-worker` doit être inclus dans le bundle\n\
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
                if let Ok(mut guard) = app.state::<DesktopWorkers>().0.lock() {
                    if let Some(child) = guard.vinted.take() {
                        kill_worker_tree(child);
                    }
                    if let Some(child) = guard.amazon.take() {
                        kill_worker_tree(child);
                    }
                }
            }
        });
}
