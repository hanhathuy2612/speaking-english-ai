"""Run the app with the server settings from .env (SERVER_HOST, SERVER_PORT, SSL_*).

    python -m app          (from backend/, venv active)
    run                    (run.cmd at the project root: no cd, no venv activation)

See docs/dev-environment.md. Agents' test servers still use `uvicorn app.main:app --port 8001`.
"""

from __future__ import annotations

import socket

import uvicorn

from app.core import config


def lan_ip() -> str | None:
    """This machine's address on the LAN (a UDP connect sends no packet)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.0.1", 9))
            return s.getsockname()[0]
    except OSError:
        return None


def main() -> None:
    ssl: dict[str, str] = {}
    if config.SSL_CERTFILE or config.SSL_KEYFILE:
        cert, key = config.ROOT_DIR / config.SSL_CERTFILE, config.ROOT_DIR / config.SSL_KEYFILE
        if not (config.SSL_CERTFILE and cert.is_file() and config.SSL_KEYFILE and key.is_file()):
            raise SystemExit(
                f"SSL_CERTFILE / SSL_KEYFILE not found ({cert}, {key}).\n"
                "Create them with: python -m scripts.make_cert <LAN IP>, or leave both empty for HTTP."
            )
        ssl = {"ssl_certfile": str(cert), "ssl_keyfile": str(key)}
    scheme = "https" if ssl else "http"
    print(f"Open {scheme}://localhost:{config.SERVER_PORT}")
    if config.SERVER_HOST in ("0.0.0.0", "::") and (ip := lan_ip()):
        print(f"Other devices on the LAN: {scheme}://{ip}:{config.SERVER_PORT}")
        if not ssl:
            print("!! Without HTTPS the microphone only works on this machine (see SSL_CERTFILE in .env).")
    uvicorn.run("app.main:app", host=config.SERVER_HOST, port=config.SERVER_PORT, **ssl)


if __name__ == "__main__":
    main()
