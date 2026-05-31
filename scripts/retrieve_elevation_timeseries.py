"""Script to calculate subregion-wide elevation time series

The output of this script is used to derive values reported in the
associated paper and to produce the Arctic-wide time series figure.

Use the prefix `uv run` to synchronize and activate the environment with
the required dependencies.
"""

from cryoswath.misc import rgi_code_translator
import pandas as pd
from pathlib import Path
from cryoswath_paper_workflow.workflow_support import (
    download_file,
    strip_spec_chars,
    snakemake_fallback_builder,
    out_to_snakemake_log_or_fallback_stdout,
    o1o2reg_tuple_list,
    calculate_mean_elevation_and_uncertainty,
    get_interp_unc,
    get_interp_unc_corr,
    project_path,
)
import xarray as xr

snakemake_fallback = snakemake_fallback_builder(globals())

data_repo = (
    "https://opendap.4tu.nl/thredds/fileServer/data2/djht/"
    "955d7f5a-0e3f-4166-a411-f0dcc4557cb2/2/"
)
AVERAGE_ELEVATION_FILENAME = (
    "Arctic_monthly_avg_glacier_surface_elevation_wrt_2010_per_RGI_o2region__meter.csv"
)


def config_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def download_verify_tls() -> bool:
    if "snakemake" in globals():
        return config_bool(globals()["snakemake"].config.get("download_verify_tls", True))
    return True


def monthly_inputs_by_name() -> dict[str, Path]:
    if "snakemake" not in globals():
        return {}
    snakemake_input = globals()["snakemake"].input
    try:
        monthly_inputs = snakemake_input.monthly
    except AttributeError:
        try:
            monthly_inputs = snakemake_input["monthly"]
        except (KeyError, TypeError):
            monthly_inputs = []
    if isinstance(monthly_inputs, (str, Path)):
        monthly_inputs = [monthly_inputs]
    return {Path(path).name: Path(path) for path in monthly_inputs}


def monthly_filename(region_name: str, subregion_name: str) -> str:
    return "__".join(
        [
            "Glacier_surface_elevation",
            strip_spec_chars(region_name),
            strip_spec_chars(subregion_name),
            "monthly_500x500m.nc",
        ]
    )


def main():
    ## preallocate results dataframe
    results = pd.DataFrame(columns=pd.MultiIndex.from_product([[], [], []]))
    monthly_inputs = monthly_inputs_by_name()

    for o1, o2_list in o1o2reg_tuple_list:
        for o2 in o2_list:
            region_name = rgi_code_translator(f"{o1:02d}")
            subregion_name = rgi_code_translator(f"{o1:02d}-{o2:02d}")
            if o1 in results.columns.get_level_values(0) and o2 in results.loc[
                :, (o1,)
            ].columns.get_level_values(0):  # type: ignore
                print("skipping", region_name, subregion_name, "because values known")
                continue
            filename = monthly_filename(region_name, subregion_name)
            path = monthly_inputs.get(
                filename,
                project_path("resources", "monthly_dataset", filename),
            )
            if not path.is_file():
                if filename in monthly_inputs:
                    raise FileNotFoundError(path)
                download_file(data_repo + filename, path, verify=download_verify_tls())
            print("processing", region_name, subregion_name)
            with xr.open_dataset(path) as ds:
                for da in calculate_mean_elevation_and_uncertainty(
                    ds,
                    get_interp_unc(
                        snakemake_fallback(
                            "input",
                            "unc_tbl",
                            str(
                                project_path(
                                    "results",
                                    "uncertainty_by_interp__uncertainty.csv",
                                )
                            ),
                        )
                    ),
                    get_interp_unc_corr(
                        snakemake_fallback(
                            "input",
                            "corr_tbl",
                            str(
                                project_path(
                                    "results",
                                    "uncertainty_by_interp__correlations.csv",
                                )
                            ),
                        )
                    ),
                ).data_vars.values():
                    results.loc[:, (o1, o2, da.name)] = da.to_series()
            results.sort_index(axis=1, inplace=True)

    results.to_csv(
        snakemake_fallback(
            "output",
            0,
            str(
                project_path(
                    "resources",
                    AVERAGE_ELEVATION_FILENAME,
                )
            ),
        )
    )


if __name__ == "__main__":
    with out_to_snakemake_log_or_fallback_stdout(
        globals().get("snakemake"), delete_old=True
    ):
        main()
