"""Start/stop local Amazon HTTP worker from the FastAPI dev process (Windows-friendly)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

logger = logging.getLogger("goupixdex.local_workers")

_amazon_proc: subprocess.Popen[bytes] | None = None


def _api_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def amazon_worker_port() -> int:
    return int(os.environ.get("GOUPIX_AMAZON_LOCAL_PORT", "18768"))


def auto_start_amazon_worker_enabled() -> bool:
    raw = os.environ.get("GOUPIX_AUTO_START_AMAZON_WORKER", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    if os.path.isfile("/.dockerenv"):
        return False
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return False
    # Par défaut : ne pas toucher au worker (Tauri / sidecar). ``run_dev.py`` force ``1``.
    return False


def _amazon_worker_meta_ok(port: int) -> bool:
    url = f"http://127.0.0.1:{port}/amazon/meta"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def kill_processes_listening_on_port(port: int) -> None:
    if port <= 0:
        return
    if sys.platform == "win32":
        script = (
            f"$pids = Get-NetTCPConnection -LocalPort {port} -State Listen "
            f"-ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; "
            f"foreach ($id in $pids) {{ if ($null -ne $id -and $id -gt 0) "
            f"{{ Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }} }}"
        )
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                script,
            ],
            check=False,
            capture_output=True,
        )
        return
    try:
        subprocess.run(
            ["fuser", "-k", f"{port}/tcp"],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        pass


def _tcp_port_open(host: str, port: int) -> bool:
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def start_managed_amazon_worker() -> None:
    global _amazon_proc
    if not auto_start_amazon_worker_enabled():
        return

    script = _api_dir() / "desktop_amazon_server.py"
    if not script.is_file():
        logger.warning("Amazon worker script missing: %s", script)
        return

    port = amazon_worker_port()

    if _amazon_proc is not None and _amazon_proc.poll() is None:
        return

    if _amazon_proc is None and _amazon_worker_meta_ok(port):
        logger.info(
            "Worker Amazon déjà actif sur 127.0.0.1:%s (Tauri/sidecar) — l’API ne le remplace pas.",
            port,
        )
        return

    kill_processes_listening_on_port(port)
    time.sleep(0.35)

    env = os.environ.copy()
    env.setdefault("GOUPIX_AMAZON_LOCAL_PORT", str(port))
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

    _amazon_proc = subprocess.Popen(
        [sys.executable, str(script)],
        cwd=str(_api_dir()),
        env=env,
        creationflags=creationflags,
    )
    logger.info(
        "Amazon worker démarré (pid=%s, port=%s) — arrêt avec l’API (processus enfant uniquement)",
        _amazon_proc.pid,
        port,
    )

    for _ in range(20):
        if _amazon_proc.poll() is not None:
            logger.error("Amazon worker s’est arrêté immédiatement (code=%s)", _amazon_proc.returncode)
            _amazon_proc = None
            return
        if _tcp_port_open("127.0.0.1", port):
            return
        time.sleep(0.15)
    logger.warning("Amazon worker pid=%s mais le port %s ne répond pas encore", _amazon_proc.pid, port)


def stop_managed_amazon_worker() -> None:
    global _amazon_proc
    if not auto_start_amazon_worker_enabled():
        return

    if _amazon_proc is not None:
        proc = _amazon_proc
        _amazon_proc = None
        if proc.poll() is None:
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        check=False,
                        capture_output=True,
                    )
                else:
                    proc.terminate()
                    proc.wait(timeout=10)
            except Exception as exc:
                logger.debug("Amazon worker stop: %s", exc)
                try:
                    proc.kill()
                except Exception:
                    pass
        logger.info("Amazon worker arrêté (pid=%s)", proc.pid)

    # Ne pas tuer le port 18768 : le worker Tauri/sidecar doit survivre au reload de l’API.
