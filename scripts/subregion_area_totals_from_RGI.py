from cryoswath.misc import load_glacier_outlines, rgi_path
import pandas as pd
from pathlib import Path
import pickle
from cryoswath_paper_workflow.workflow_support import (
    out_to_snakemake_log_or_fallback_stdout,
    project_path,
    snakemake_fallback_builder,
)

snakemake_fallback = snakemake_fallback_builder(globals())


def main():
    o1_tbl = pd.read_csv(
        snakemake_fallback(
            "input", 0, Path(rgi_path, "RGI2000-v7.0-G-global-attributes.csv")
        ),
        index_col="rgi_id",
    )
    for i in range(1, 6):
        o1_tbl.loc[
            load_glacier_outlines(f"05-1{i}", "basins", False).rgi_id, "o2region"
        ] = f"05-1{i}"
    o2_areas_rgi = o1_tbl.groupby("o2region").area_km2.sum()
    o2_areas_rgi.index = pd.MultiIndex.from_tuples(
        [[int(o2code[:2]), int(o2code[-2:])] for o2code in o2_areas_rgi.index],
    )
    with open(
        snakemake_fallback(
            "output",
            0,
            str(project_path("resources", "subregion_area_totals_from_RGI.pkl")),
        ),
        "wb",
    ) as f:
        pickle.dump(o2_areas_rgi, f)


if __name__ == "__main__":
    with out_to_snakemake_log_or_fallback_stdout(globals().get("snakemake"), delete_old=True):
        main()
