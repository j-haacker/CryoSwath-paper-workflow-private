#!/usr/bin/env python3
import argparse
from pathlib import Path
import requests
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryoswath_paper_workflow.workflow_support import (
    download_file,
    out_to_snakemake_log_or_fallback_stdout,
)
import urllib.parse
from xml.etree import ElementTree as ET


def config_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def iter_urlpaths_from_catalog_xml(xml_text: str):
    root = ET.fromstring(xml_text)
    for elem in root.iter():
        if elem.tag.split("}")[-1] == "dataset":
            urlpath = elem.attrib.get("urlPath")
            if urlpath:
                yield urlpath


def main(
    filename: str,
    dest_dir: Path,
    verify_tls: bool = True,
):
    xml = requests.get(
        "https://opendap.4tu.nl/thredds/catalog/data2/djht/955d7f5a-0e3f-4166-a411-f0dcc4557cb2/2/catalog.xml",
        timeout=60,
        verify=verify_tls,
    ).text
    if filename == "all":
        urlpaths = sorted(set(iter_urlpaths_from_catalog_xml(xml)))
    else:
        urlpaths = sorted(
            set(
                nc
                for nc in iter_urlpaths_from_catalog_xml(xml)
                if nc.endswith(filename)
            )
        )

    # Build HTTP file download URLs (THREDDS fileServer)
    base = "https://opendap.4tu.nl/thredds/fileServer/"
    urls = [urllib.parse.urljoin(base, p) for p in urlpaths]

    print(f"Found {len(urls)} files. Downloading to: {str(dest_dir)}")
    for u in urls:
        target = dest_dir / Path(urllib.parse.urlparse(u).path).name
        if target.exists():
            print(f"⏭️ {target.stem} skipping existing file")
            continue
        download_file(u, target, verify=verify_tls)


if __name__ == "__main__":
    if "snakemake" in globals():
        with out_to_snakemake_log_or_fallback_stdout(globals().get("snakemake"), delete_old=True):
            destpath = Path(globals()["snakemake"].output[0])
            verify_tls = config_bool(
                globals()["snakemake"].config.get("download_verify_tls", True)
            )
            main(destpath.name, destpath.parent, verify_tls=verify_tls)
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("dest_dir", type=str)
        parser.add_argument("--file", type=str, default="all")
        parser.add_argument("--no-verify-tls", action="store_true")
        args = parser.parse_args()
        main(args.file, Path(args.dest_dir), verify_tls=not args.no_verify_tls)
