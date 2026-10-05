"""Encrypt recovery evidence to an X.509 recipient before artifact upload.

Only the holder of the corresponding private key can decrypt the CMS envelope.
The private key is never supplied to the workflow. With no configured public
certificate, the workflow uploads sanitized status only.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import tempfile


def encrypt(db: Path, certificate: Path, out: Path) -> None:
    if not db.is_file():
        raise ValueError("No recovery database exists")
    cert = certificate.read_text()
    if "PRIVATE KEY" in cert or "BEGIN CERTIFICATE" not in cert:
        raise ValueError("Configure a public X.509 certificate, never a private key")
    if out.resolve() in {db.resolve(), certificate.resolve()}:
        raise ValueError("Encrypted output must not replace the evidence or certificate")
    out.parent.mkdir(parents=True, exist_ok=True)
    # Create the encrypted artifact atomically; failed encryption leaves no
    # partially written file for the artifact uploader to mistake for success.
    with tempfile.TemporaryDirectory(dir=out.parent) as directory:
        temporary = Path(directory) / "recovery.p7m"
        subprocess.run(["openssl", "cms", "-encrypt", "-aes256", "-binary", "-in", str(db),
                        "-out", str(temporary), "-outform", "DER", str(certificate)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        temporary.replace(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--certificate", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    encrypt(args.db, args.certificate, args.out)
    print("Encrypted recovery artifact prepared; no raw database is uploaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
