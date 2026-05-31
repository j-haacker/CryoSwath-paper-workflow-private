from argparse import ArgumentParser
from cryoswath.misc import (
    rgi_code_translator,
    dem_path,
)
from dask.distributed import Client, LocalCluster, Lock
import geopandas as gpd
from pathlib import Path
from pystac_client import Client as pyst_cl
from tempfile import NamedTemporaryFile
from cryoswath_paper_workflow.workflow_support import (
    out_to_snakemake_log_or_fallback_stdout,
    project_path,
    snakemake_fallback_builder,
)
import xarray as xr

snakemake_fallback = snakemake_fallback_builder(globals())


catalog = pyst_cl.open("https://stac.pgc.umn.edu/api/v1")
query = dict(
    collections=["arcticdem-strips-s2s041-2m"],
    datetime="2010-08-01/2024-11-30",
)


def download_arcticdem_strip(item_id):
    out_dir = Path(dem_path, "strips")
    out_dir.mkdir(exist_ok=True)
    dst = out_dir / (item_id + "__32m_mean.tif")
    if dst.exists():
        return
    item = next(catalog.search(ids=[item_id]).items())
    coarsen = 32
    chunk = 128
    da = (
        xr.open_dataarray(item.assets["dem"].href)
        .chunk(coarsen * chunk)
        .where(xr.open_dataarray(item.assets["mask"].href).chunk(coarsen * chunk) == 0)
    )
    da = da.coarsen(x=coarsen, y=coarsen, boundary="trim").mean()
    with NamedTemporaryFile(suffix=".tif", dir=dst.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with (
            LocalCluster(
                n_workers=(4 if "snakemake" not in globals() else snakemake.threads),
                dashboard_address=None,  # pyright: ignore[reportArgumentType]
            ) as cluster,
            Client(cluster),
        ):
            da.rio.to_raster(tmp_path, tiled=True, lock=Lock("rio"))
        tmp_path.replace(dst)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def main(o1: int):
    refdata_lockfile = Path(
        snakemake_fallback(
            "input",
            0,
            Path(
                "resources",
                "calval__select_arcticdem_strips__"
                + rgi_code_translator(f"{o1:02d}", out_type="long_code"),
            ).with_suffix(".lock.feather"),
        )
    )
    refdata_ids = gpd.read_feather(refdata_lockfile)
    for item_list in refdata_ids.strip_ids:
        for item_id in item_list:
            download_arcticdem_strip(item_id)
    if "snakemake" in globals():
        Path(globals()["snakemake"].output[0]).touch()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--o1", type=str, default="")
    with out_to_snakemake_log_or_fallback_stdout(
        globals().get("snakemake"), delete_old=True
    ):
        main(int(snakemake_fallback("wildcards", "token", parser.parse_args().o1)[:2]))
