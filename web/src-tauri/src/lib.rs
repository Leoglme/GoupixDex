use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

/// Processus Python ``desktop_vinted_server.py`` (nodriver en local).
struct VintedLocalChild(Mutex<Option<Child>>);

fn repo_api_dir() -> Result<std::path::PathBuf, std::io::Error> {
  let manifest = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
  let repo_root = manifest
    .parent()
    .and_then(|p| p.parent())
    .ok_or_else(|| std::io::Error::new(std::io::ErrorKind::NotFound, "répertoire dépôt"))?;
  let api = repo_root.join("api");
  if api.join("desktop_vinted_server.py").is_file() {
    Ok(api)
  } else {
    Err(std::io::Error::new(
      std::io::ErrorKind::NotFound,
      "api/desktop_vinted_server.py introuvable (lancez depuis le clone du dépôt ou définissez GOUPIX_PYTHON / PYTHONPATH).",
    ))
  }
}

fn spawn_vinted_local_worker() -> Result<Child, std::io::Error> {
  let api_dir = repo_api_dir()?;
  let bin = std::env::var("GOUPIX_PYTHON").unwrap_or_else(|_| "python".to_string());
  Command::new(&bin)
    .current_dir(&api_dir)
    .arg("desktop_vinted_server.py")
    .spawn()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_updater::Builder::new().build())
    .manage(VintedLocalChild(Mutex::new(None)))
    .setup(|app| {
      match spawn_vinted_local_worker() {
        Ok(child) => {
          *app
            .state::<VintedLocalChild>()
            .0
            .lock()
            .expect("vinted child mutex") = Some(child);
        }
        Err(e) => {
          eprintln!(
            "[GoupixDex] Worker Vinted local indisponible : {e}\n\
             → Depuis le dossier « api » du projet : python desktop_vinted_server.py\n\
             → Ou : définir GOUPIX_PYTHON vers votre exécutable Python."
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
          if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
          }
        }
      }
    });
}
