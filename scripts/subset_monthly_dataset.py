#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "cryoswath",
#     "dask",
#     "distributed",
#     "h5netcdf",
#     "pyproj",
#     "rioxarray",
#     "shapely",
#     "xarray",
# ]
# ///

from argparse import ArgumentParser, Namespace
from pathlib import Path
import sys

from cryoswath.misc import load_glacier_outlines, _load_basins
from dask.distributed import Client, LocalCluster
from pyproj import CRS
import shapely

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryoswath_paper_workflow.workflow_support import (
    out_to_snakemake_log_or_fallback_stdout,
)
import xarray as xr


def _parse_period(period: str) -> slice:
    return slice(*period.split("-"))


def _parse_region(region: str, crs: CRS) -> shapely.MultiPolygon:
    try:
        return load_glacier_outlines(region, crs=crs)
    except ValueError as err:
        if "RGI identifiers" in str(err):
            return _load_basins([region]).to_crs(crs).make_valid().union_all("unary")  # pyright: ignore[reportReturnType, reportAttributeAccessIssue]
        raise err


def main(
    ds: xr.Dataset,
    period: slice | None = None,
    polygon: shapely.MultiPolygon | None = None,
) -> xr.Dataset:
    if period is not None:
        ds = ds.sel(time=period)
    if polygon is not None:
        ds = ds.rio.clip([polygon])
    return ds


if __name__ == "__main__":
    with out_to_snakemake_log_or_fallback_stdout(
        globals().get("snakemake"), delete_old=True
    ):
        if "snakemake" in globals():
            args = Namespace(
                input_path=globals()["snakemake"].input[0],
                output_path=globals()["snakemake"].output[0],
                region=globals()["snakemake"].params.glacier_rgi_id,
                period=globals()["snakemake"].wildcards.period,
                workers=globals()["snakemake"].threads,
            )
        else:
            parser = ArgumentParser()
            parser.add_argument("input_path", type=str)
            parser.add_argument("output_path", type=str)
            parser.add_argument("--period", type=str)
            parser.add_argument("--region", type=str)
            parser.add_argument("--workers", type=int, default=1)
            args = parser.parse_args()
        ds = xr.open_dataset(args.input_path, engine="h5netcdf", chunks={})
        period = None if not args.period else _parse_period(args.period)
        polygon = None if not args.region else _parse_region(args.region, ds.rio.crs)
        with (
            LocalCluster(
                n_workers=args.workers,
                threads_per_worker=2,
                dashboard_address=None,  # pyright: ignore[reportArgumentType]
            ) as cluster,
            Client(cluster),
        ):
            main(ds, period=period, polygon=polygon).to_netcdf(
                args.output_path, mode="w", engine="h5netcdf"
            )
