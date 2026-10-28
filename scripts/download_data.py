"""Download CUAD v1 into data/raw.

I fetch two official archives from The Atticus Project:
- data.zip from the CUAD GitHub repo, which holds the SQuAD-style annotations and the
  official train/test split (train_separate_questions.json and test.json).
- CUAD_v1.zip from the Zenodo record linked on the Atticus Project site, which holds the
  510 contracts as PDFs and plain text plus master_clauses.csv.

CUAD is licensed CC BY 4.0. See docs/DATA.md for the citation.
"""

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

import httpx

GITHUB_DATA_URL = "https://github.com/TheAtticusProject/cuad/raw/main/data.zip"
ZENODO_URL = "https://zenodo.org/records/4595826/files/CUAD_v1.zip?download=1"
# I check the Zenodo archive against the md5 the record publishes.
ZENODO_MD5 = "c38f490a984420b8a62600db401fafd5"


def download(url: str, dest: Path, attempts: int = 8) -> None:
    # I stream to a temporary file first so a half-finished download never looks complete.
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, attempts + 1):
        # Zenodo sometimes drops long downloads, so I resume from where the last try stopped.
        done = tmp.stat().st_size if tmp.exists() else 0
        headers = {"Range": f"bytes={done}-"} if done else {}
        try:
            with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=120) as r:
                if r.status_code == 416:
                    break  # the server says there is nothing left to send
                r.raise_for_status()
                if done and r.status_code != 206:
                    done = 0  # the server ignored the range, so I start over
                total = done + int(r.headers.get("content-length", 0))
                with open(tmp, "ab" if done else "wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
                        done += len(chunk)
                        print(f"\r  {dest.name}: {done / max(total, 1):6.1%}", end="", flush=True)
            break
        except httpx.TransportError as err:
            print(f"\n  attempt {attempt} failed ({err}), retrying")
    else:
        raise RuntimeError(f"Could not download {url}")
    print()
    tmp.replace(dest)


def md5sum(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def safe_extract(zip_path: Path, out_dir: Path) -> None:
    # I refuse any member that would land outside out_dir, since this is downloaded data.
    out_dir = out_dir.resolve()
    with zipfile.ZipFile(zip_path) as z:
        for member in z.infolist():
            target = (out_dir / member.filename).resolve()
            if not target.is_relative_to(out_dir):
                raise RuntimeError(f"Unsafe path in archive: {member.filename}")
        z.extractall(out_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("data/raw"))
    parser.add_argument("--skip-pdfs", action="store_true", help="Only fetch the JSON annotations.")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    # The annotations and the official split come from the GitHub repo.
    data_zip = args.out / "data.zip"
    if not data_zip.exists():
        print("Downloading annotations from GitHub")
        download(GITHUB_DATA_URL, data_zip)
    safe_extract(data_zip, args.out / "cuad_json")

    # The PDFs and texts come from the Zenodo record.
    if not args.skip_pdfs:
        full_zip = args.out / "CUAD_v1.zip"
        if not full_zip.exists():
            print("Downloading contracts from Zenodo")
            download(ZENODO_URL, full_zip)
        if md5sum(full_zip) != ZENODO_MD5:
            print("Checksum mismatch for CUAD_v1.zip, delete it and try again", file=sys.stderr)
            return 1
        safe_extract(full_zip, args.out)

    print(f"Done. Files are in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
