//! Prod MariaDB/MySQL → local dev database sync (read-only dump → import). Desktop debug builds only.
//!
//! Uses host `mysqldump` / `mysql` when available, otherwise **`docker run mariadb:11`**
//! (`mariadb-dump` / `mariadb` in the image) when `GOUPIX_SYNC_USE_DOCKER=auto` and no local clients.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

fn command_hidden(bin: impl AsRef<std::ffi::OsStr>) -> Command {
    let mut c = Command::new(bin);
    #[cfg(target_os = "windows")]
    c.creation_flags(CREATE_NO_WINDOW);
    c
}

pub fn load_env_sync_files() {
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let web_root = match manifest.parent() {
        Some(p) => p,
        None => return,
    };
    let repo_root = match web_root.parent() {
        Some(p) => p,
        None => return,
    };
    let paths = [
        repo_root.join("api").join(".env.sync"),
        web_root.join(".env.sync"),
    ];
    for p in paths {
        if p.is_file() {
            if let Err(e) = dotenvy::from_path(&p) {
                eprintln!("[GoupixDex] Failed to load .env.sync {:?}: {}", p, e);
            }
        }
    }
}

fn req_env(key: &str) -> Result<String, String> {
    std::env::var(key)
        .map_err(|_| format!("Missing env var: {key} (see web/.env.sync.example)"))
        .and_then(|v| {
            let t = v.trim().to_string();
            if t.is_empty() {
                Err(format!("Empty env var: {key}"))
            } else {
                Ok(t)
            }
        })
}

fn env_or(key: &str, default: &str) -> String {
    std::env::var(key)
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| default.to_string())
}

fn env_u16(key: &str, default: u16) -> u16 {
    std::env::var(key)
        .ok()
        .and_then(|s| s.trim().parse().ok())
        .unwrap_or(default)
}

/** Allow only [a-zA-Z0-9_] in database names to avoid injection in `-e` SQL. */
fn sanitize_db_name(name: &str, key: &str) -> Result<String, String> {
    if name.is_empty() {
        return Err(format!("{key} is empty"));
    }
    if !name
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '_')
    {
        return Err(format!(
            "{key}: invalid database name (use letters, digits, underscore only)"
        ));
    }
    Ok(name.to_string())
}

fn write_client_cnf(
    path: &Path,
    host: &str,
    port: u16,
    user: &str,
    password: &str,
) -> Result<(), String> {
    // Note: `#` in the password truncates the line in .cnf files — see .env.sync.example.
    let body = format!(
        "[client]\nhost={host}\nport={port}\nuser={user}\npassword={password}\n"
    );
    fs::write(path, body.as_bytes()).map_err(|e| format!("write {:?}: {e}", path))
}

fn resolve_client_bin(env_key: &str, default: &str) -> String {
    std::env::var(env_key)
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| default.to_string())
}

fn client_version_ok(bin: &str) -> bool {
    command_hidden(bin)
        .arg("--version")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn docker_daemon_ok(docker: &str) -> bool {
    command_hidden(docker)
        .args(["info"])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

/// Host path for `docker run -v SRC:DST:ro`. On Windows, `canonicalize` yields a verbatim path
/// (`\\?\C:\...`) which Docker parses incorrectly ("invalid spec", "too many colons"). Strip the
/// prefix and use forward slashes so the bind mount is valid for Docker Desktop.
fn docker_bind_mount_source(host_file: &Path) -> Result<String, String> {
    let abs = fs::canonicalize(host_file)
        .map_err(|e| format!("absolute path required for Docker -v {:?}: {e}", host_file))?;
    let raw = abs.to_string_lossy();
    let mut s = raw.into_owned();
    if let Some(rest) = s.strip_prefix(r"\\?\") {
        s = rest.to_string();
    } else if let Some(rest) = s.strip_prefix("//?/") {
        s = rest.to_string();
    }
    Ok(s.replace('\\', "/"))
}

fn docker_volume_mount(host_file: &Path, container_path: &str) -> Result<String, String> {
    let src = docker_bind_mount_source(host_file)?;
    Ok(format!("{src}:{container_path}:ro"))
}

enum SyncBackend {
    Host {
        mysqldump: String,
        mysql: String,
    },
    Docker {
        docker: String,
        image: String,
    },
}

fn resolve_sync_backend(
    mode: &str,
    mysqldump_bin: &str,
    mysql_bin: &str,
    docker_bin: &str,
    docker_image: &str,
) -> Result<SyncBackend, String> {
    match mode {
        "always" => {
            if !docker_daemon_ok(docker_bin) {
                return Err(format!(
                    "Docker unavailable (`{docker_bin} info` failed). Start Docker Desktop."
                ));
            }
            Ok(SyncBackend::Docker {
                docker: docker_bin.to_string(),
                image: docker_image.to_string(),
            })
        }
        "never" => {
            if !client_version_ok(mysqldump_bin) {
                return Err(format!(
                    "`{mysqldump_bin}` not found (GOUPIX_SYNC_USE_DOCKER=never)."
                ));
            }
            if !client_version_ok(mysql_bin) {
                return Err(format!(
                    "`{mysql_bin}` not found (GOUPIX_SYNC_USE_DOCKER=never)."
                ));
            }
            Ok(SyncBackend::Host {
                mysqldump: mysqldump_bin.to_string(),
                mysql: mysql_bin.to_string(),
            })
        }
        "auto" | _ => {
            if client_version_ok(mysqldump_bin) && client_version_ok(mysql_bin) {
                return Ok(SyncBackend::Host {
                    mysqldump: mysqldump_bin.to_string(),
                    mysql: mysql_bin.to_string(),
                });
            }
            if docker_daemon_ok(docker_bin) {
                return Ok(SyncBackend::Docker {
                    docker: docker_bin.to_string(),
                    image: docker_image.to_string(),
                });
            }
            Err(
                "Neither MariaDB/MySQL clients (mysqldump / mysql) nor Docker is usable. \
                 Install Docker Desktop (https://www.docker.com/products/docker-desktop/) \
                 or MariaDB client binaries on PATH."
                    .into(),
            )
        }
    }
}

struct CleanupFiles(Vec<PathBuf>);

impl Drop for CleanupFiles {
    fn drop(&mut self) {
        for p in &self.0 {
            let _ = fs::remove_file(p);
        }
    }
}

fn run_mysqldump(
    backend: &SyncBackend,
    prod_cnf: &Path,
    prod_db: &str,
) -> Result<Vec<u8>, String> {
    match backend {
        SyncBackend::Host { mysqldump, .. } => {
            let prod_extra = format!("--defaults-extra-file={}", prod_cnf.to_string_lossy());
            let dump_out = command_hidden(mysqldump)
                .arg(&prod_extra)
                .args([
                    "--single-transaction",
                    "--skip-lock-tables",
                    "--skip-triggers",
                ])
                .arg(prod_db)
                .stderr(Stdio::piped())
                .stdout(Stdio::piped())
                .output()
                .map_err(|e| {
                    format!(
                        "Could not run `{mysqldump}`: {e}. Use Docker or set GOUPIX_MYSQLDUMP_BIN."
                    )
                })?;
            if !dump_out.status.success() {
                let err = String::from_utf8_lossy(&dump_out.stderr);
                return Err(format!(
                    "mysqldump failed (network, remote MySQL allowlist, SELECT grants):\n{err}"
                ));
            }
            Ok(dump_out.stdout)
        }
        SyncBackend::Docker { docker, image } => {
            let mount = docker_volume_mount(prod_cnf, "/tmp/goupix_sync_prod.cnf")?;
            let dump_out = command_hidden(docker)
                .args([
                    "run",
                    "--rm",
                    "--add-host=host.docker.internal:host-gateway",
                    "-v",
                    mount.as_str(),
                    image.as_str(),
                    "mariadb-dump",
                    "--defaults-extra-file=/tmp/goupix_sync_prod.cnf",
                    "--single-transaction",
                    "--skip-lock-tables",
                    "--skip-triggers",
                    prod_db,
                ])
                .stderr(Stdio::piped())
                .stdout(Stdio::piped())
                .output()
                .map_err(|e| {
                    format!(
                        "`docker run … mariadb-dump` failed: {e}. Check Docker Desktop and image `{image}`."
                    )
                })?;
            if !dump_out.status.success() {
                let err = String::from_utf8_lossy(&dump_out.stderr);
                return Err(format!("mariadb-dump (container) failed:\n{err}"));
            }
            Ok(dump_out.stdout)
        }
    }
}

fn run_mysql_exec(
    backend: &SyncBackend,
    local_cnf: &Path,
    args: &[&str],
) -> Result<(), String> {
    match backend {
        SyncBackend::Host { mysql, .. } => {
            let local_extra = format!("--defaults-extra-file={}", local_cnf.to_string_lossy());
            let mut cmd = command_hidden(mysql);
            cmd.arg(&local_extra);
            for a in args {
                cmd.arg(a);
            }
            let out = cmd.stderr(Stdio::piped()).output().map_err(|e| {
                format!("Could not run `{mysql}`: {e}. Use Docker or set GOUPIX_MYSQL_BIN.")
            })?;
            if !out.status.success() {
                let err = String::from_utf8_lossy(&out.stderr);
                return Err(err.to_string());
            }
            Ok(())
        }
        SyncBackend::Docker { docker, image } => {
            let mount = docker_volume_mount(local_cnf, "/tmp/goupix_sync_local.cnf")?;
            let mut cmd = command_hidden(docker);
            cmd.args([
                "run",
                "--rm",
                "--add-host=host.docker.internal:host-gateway",
                "-v",
                mount.as_str(),
                image.as_str(),
                "mariadb",
                "--defaults-extra-file=/tmp/goupix_sync_local.cnf",
            ]);
            for a in args {
                cmd.arg(a);
            }
            let out = cmd.stderr(Stdio::piped()).output().map_err(|e| {
                format!("`docker run … mariadb`: {e}")
            })?;
            if !out.status.success() {
                let err = String::from_utf8_lossy(&out.stderr);
                return Err(err.to_string());
            }
            Ok(())
        }
    }
}

fn run_mysql_import_stdin(
    backend: &SyncBackend,
    local_cnf: &Path,
    local_db: &str,
    dump_sql: &Path,
) -> Result<(), String> {
    let sql_file = fs::File::open(dump_sql).map_err(|e| format!("open dump file: {e}"))?;
    match backend {
        SyncBackend::Host { mysql, .. } => {
            let local_extra = format!("--defaults-extra-file={}", local_cnf.to_string_lossy());
            let out = command_hidden(mysql)
                .arg(&local_extra)
                .arg(local_db)
                .stdin(sql_file)
                .stderr(Stdio::piped())
                .output()
                .map_err(|e| format!("mysql import: {e}"))?;
            if !out.status.success() {
                return Err(String::from_utf8_lossy(&out.stderr).to_string());
            }
            Ok(())
        }
        SyncBackend::Docker { docker, image } => {
            let mount = docker_volume_mount(local_cnf, "/tmp/goupix_sync_local.cnf")?;
            let out = command_hidden(docker)
                .args([
                    "run",
                    "--rm",
                    "-i",
                    "--add-host=host.docker.internal:host-gateway",
                    "-v",
                    mount.as_str(),
                    image.as_str(),
                    "mariadb",
                    "--defaults-extra-file=/tmp/goupix_sync_local.cnf",
                    local_db,
                ])
                .stdin(sql_file)
                .stderr(Stdio::piped())
                .output()
                .map_err(|e| format!("docker import: {e}"))?;
            if !out.status.success() {
                return Err(String::from_utf8_lossy(&out.stderr).to_string());
            }
            Ok(())
        }
    }
}

/// Dump prod to SQL, then import into the local database (DROP TABLE from dump replaces existing tables).
pub fn sync_dev_database_from_prod_impl() -> Result<String, String> {
    load_env_sync_files();

    let prod_host = req_env("GOUPIX_SYNC_PROD_HOST")?;
    let prod_port = env_u16("GOUPIX_SYNC_PROD_PORT", 3306);
    let prod_user = req_env("GOUPIX_SYNC_PROD_USER")?;
    let prod_pass = req_env("GOUPIX_SYNC_PROD_PASSWORD")?;
    let prod_db = sanitize_db_name(&req_env("GOUPIX_SYNC_PROD_DATABASE")?, "GOUPIX_SYNC_PROD_DATABASE")?;

    let local_host = env_or("GOUPIX_SYNC_LOCAL_HOST", "127.0.0.1");
    let local_port = env_u16("GOUPIX_SYNC_LOCAL_PORT", 3306);
    let local_user = env_or("GOUPIX_SYNC_LOCAL_USER", "goupix");
    let local_pass = env_or("GOUPIX_SYNC_LOCAL_PASSWORD", "goupix");
    let local_db = sanitize_db_name(
        &env_or("GOUPIX_SYNC_LOCAL_DATABASE", "goupixdex"),
        "GOUPIX_SYNC_LOCAL_DATABASE",
    )?;

    let sync_mode = env_or("GOUPIX_SYNC_USE_DOCKER", "auto").to_lowercase();
    let mysqldump_bin = resolve_client_bin("GOUPIX_MYSQLDUMP_BIN", "mysqldump");
    let mysql_bin = resolve_client_bin("GOUPIX_MYSQL_BIN", "mysql");
    let docker_bin = resolve_client_bin("GOUPIX_DOCKER_BIN", "docker");
    let docker_image = env_or("GOUPIX_SYNC_DOCKER_IMAGE", "mariadb:11");

    let backend = resolve_sync_backend(
        sync_mode.as_str(),
        &mysqldump_bin,
        &mysql_bin,
        &docker_bin,
        &docker_image,
    )?;

    let local_connect_host = match &backend {
        SyncBackend::Host { .. } => local_host.clone(),
        SyncBackend::Docker { .. } => env_or("GOUPIX_SYNC_LOCAL_DOCKER_HOST", "host.docker.internal"),
    };

    let tmp = std::env::temp_dir();
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let prod_cnf = tmp.join(format!("goupixdex_sync_prod_{stamp}.cnf"));
    let local_cnf = tmp.join(format!("goupixdex_sync_local_{stamp}.cnf"));
    let dump_sql = tmp.join(format!("goupixdex_sync_dump_{stamp}.sql"));

    write_client_cnf(&prod_cnf, &prod_host, prod_port, &prod_user, &prod_pass)?;
    write_client_cnf(
        &local_cnf,
        &local_connect_host,
        local_port,
        &local_user,
        &local_pass,
    )?;

    let _cleanup = CleanupFiles(vec![
        prod_cnf.clone(),
        local_cnf.clone(),
        dump_sql.clone(),
    ]);

    let stdout = run_mysqldump(&backend, &prod_cnf, &prod_db)?;

    if stdout.is_empty() {
        return Err("Dump is empty (empty prod database or silent failure?)".into());
    }

    fs::write(&dump_sql, &stdout).map_err(|e| format!("write dump file: {e}"))?;
    let bytes = stdout.len();

    let create_sql = format!(
        "CREATE DATABASE IF NOT EXISTS `{local_db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    );
    run_mysql_exec(&backend, &local_cnf, &["-e", &create_sql]).map_err(|err| {
        format!(
            "Failed to create local database:\n{err}\nTip: run `docker compose stop api` in api/."
        )
    })?;

    run_mysql_import_stdin(&backend, &local_cnf, &local_db, &dump_sql).map_err(|err| {
        format!(
            "Import into `{local_db}` failed:\n{err}\nTip: stop the `api` container to free connections."
        )
    })?;

    let via = match &backend {
        SyncBackend::Host { .. } => "local clients",
        SyncBackend::Docker { .. } => "Docker (mariadb:11)",
    };

    Ok(format!(
        "Sync complete ({via}): {prod_db} → {local_db} ({bytes} bytes). Restart the local API if needed."
    ))
}
