#!/usr/bin/env python3
from pathlib import Path
import requests
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryoswath_paper_workflow.workflow_support import (
    download_file,
    out_to_snakemake_log_or_fallback_stdout,
    project_path,
    snakemake_fallback_builder,
)

snakemake_fallback = snakemake_fallback_builder(globals())

base_url = "https://api.sedoo.fr/sedoo-glaciers-rest/data/v1_0"


def request_archive_id(session: requests.Session) -> str:
    req = session.get(
        f"{base_url}/prepare/06_rgi60/2010-01-01_2020-01-01",
        timeout=60,
    )
    req.raise_for_status()
    request_id = req.text.strip().strip('"')
    if not request_id:
        raise RuntimeError("SEDOO prepare endpoint returned an empty request id")
    return request_id


def wait_until_archive_is_ready(
    session: requests.Session,
    request_id: str,
    max_checks: int = 240,
    delay_s: float = 1.0,
) -> None:
    for i in range(max_checks):
        status = (
            session.get(
                f"{base_url}/check",
                params={"requestid": request_id},
                timeout=60,
            )
            .text.strip()
            .strip('"')
        )
        print(f"check {i + 1}/{max_checks}: {status}")
        if status == "DONE":
            return
        if status in {"ERROR", "FAILED", "ABORTED"} or status.startswith("ERROR"):
            raise RuntimeError(f"SEDOO archive generation failed: {status}")
        time.sleep(delay_s)

    raise TimeoutError(
        f"SEDOO archive generation timed out after {max_checks} checks "
        f"(request id: {request_id})"
    )


def main():
    sentinel = Path(
        snakemake_fallback(
            "output",
            "sentinel",
            str(
                project_path(
                    "resources", "dhdt", "N64W018_2010-01-01_2020-01-01_dhdt.tif"
                )
            ),
        )
    )
    dest_root = sentinel.parents[1]
    if sentinel.exists():
        print(f"skip existing file: {sentinel}")
        return

    with requests.Session() as session:
        request_id = request_archive_id(session)
        print(f"SEDOO request id: {request_id}")
        wait_until_archive_is_ready(session, request_id)

    tmp_tar = (
        dest_root
        / f"cache_iceland_ref__{int(time.time())}.tar"
    )
    try:
        download_file(
            f"{base_url}/download/{request_id}",
            tmp_tar,
        )
        with tarfile.open(tmp_tar, mode="r:*") as archive:
            archive.extractall(dest_root)
    finally:
        tmp_tar.unlink(missing_ok=True)

    if not sentinel.exists():
        raise FileNotFoundError(
            "Archive extraction finished but expected sentinel TIFF was not found: "
            f"{sentinel}"
        )

    print(f"extracted to {dest_root}")


if __name__ == "__main__":
    with out_to_snakemake_log_or_fallback_stdout(globals().get("snakemake"), delete_old=True):
        main()
