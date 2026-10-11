"""Create a self-signed HTTPS certificate so phones on the same LAN can use the microphone.

Browsers only allow microphone access on https:// or localhost, so http://192.168.x.x opens the
app but recording fails. Uses the openssl CLI (bundled with Git for Windows); no Python dependency.
See docs/dev-environment.md ("Dùng từ thiết bị khác trong mạng LAN").

Usage (from backend/):
    python -m scripts.make_cert 192.168.0.2 [more IPs or host names ...]
Writes certs/lan-key.pem and certs/lan-cert.pem at the project root (git-ignored).
"""

from __future__ import annotations

import argparse
import ipaddress
import shutil
import subprocess

from app.core.config import ROOT_DIR

CERT_DIR = ROOT_DIR / "certs"
DAYS = 825  # longest validity iOS accepts for a server certificate


def san_entry(name: str) -> str:
    try:
        ipaddress.ip_address(name)
        return f"IP:{name}"
    except ValueError:
        return f"DNS:{name}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("hosts", nargs="+", help="LAN IP addresses or host names of this machine")
    args = parser.parse_args()
    openssl = shutil.which("openssl")
    if not openssl:
        raise SystemExit("openssl not found: run this from Git Bash, or install OpenSSL")

    names = [*args.hosts, "localhost", "127.0.0.1"]
    san = ",".join(dict.fromkeys(san_entry(n) for n in names))
    CERT_DIR.mkdir(exist_ok=True)
    key, cert = CERT_DIR / "lan-key.pem", CERT_DIR / "lan-cert.pem"
    subprocess.run(
        [
            openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256",
            "-days", str(DAYS), "-keyout", str(key), "-out", str(cert),
            "-subj", "/CN=Speaking practice (local)", "-addext", f"subjectAltName={san}",
        ],
        check=True,
    )  # fmt: skip
    print(f"Wrote {cert} and {key} for {san}")
    print("Run the server (from backend/):")
    print("  uvicorn app.main:app --host 0.0.0.0 --port 8000 --ssl-keyfile ../certs/lan-key.pem --ssl-certfile ../certs/lan-cert.pem")
    print(f"Then open https://{args.hosts[0]}:8000 on the other device and accept the certificate warning.")


if __name__ == "__main__":
    main()
