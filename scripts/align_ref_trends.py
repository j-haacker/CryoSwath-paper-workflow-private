from pathlib import Path
from rasterio.warp import Resampling
from rioxarray import open_rasterio
from rioxarray.merge import merge_arrays
from cryoswath_paper_workflow.workflow_support import (
    out_to_snakemake_log_or_fallback_stdout,
)
from typing import Protocol, runtime_checkable


@runtime_checkable
class snakemake_mock(Protocol):
    input: dict[str, str]
    output: dict[int, str]


snakemake = globals().get("snakemake", snakemake_mock)

with out_to_snakemake_log_or_fallback_stdout(
    None if isinstance(snakemake, snakemake_mock) else snakemake, delete_old=True
):
    ds = open_rasterio(snakemake.input["own"], band_as_variable=True, chunks={})
    merge_arrays(
        [
            open_rasterio(x, mask_and_scale=True)
            for x in Path(snakemake.input["ref_sentinel"]).parent.glob("*.tif")
        ]  # pyright: ignore[reportArgumentType]
    ).squeeze().rio.reproject_match(ds, resampling=Resampling.average).rio.to_raster(
        snakemake.output[0]
    )
