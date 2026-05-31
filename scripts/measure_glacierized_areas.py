"""Script to measure glacierized areas

The output of this script is used to weight subregions in Arctic-wide
aggregation.

Use the prefix `uv run` to synchronize and activate the environment with
the required dependencies.
"""

from cryoswath.misc import rgi_code_translator
import numpy as np
import pandas as pd
from pathlib import Path
import rasterio
from cryoswath_paper_workflow.workflow_support import (
    o1o2reg_tuple_list,
    project_path,
    snakemake_fallback_builder,
    strip_spec_chars,
)

snakemake_fallback = snakemake_fallback_builder(globals())
trend_root = Path(
    snakemake_fallback(
        "params", "trend_root", str(project_path("resources", "trends_dataset"))
    )
)

o2areas = pd.Series(
    index=pd.MultiIndex.from_tuples(
        [(o1, o2) for o1, o2list in o1o2reg_tuple_list for o2 in o2list],
        names=["o1", "o2"],
    ),
    name="area_km2",
)

for o1, o2list in o1o2reg_tuple_list:
    for o2 in o2list:
        o2areas.loc[o1, o2] = (
            np.sum(
                ~np.isnan(
                    rasterio.open(
                        str(
                            trend_root
                            / "__".join(
                                [
                                    "Glacier_surface_elevation_trend_2010-2024",
                                    strip_spec_chars(rgi_code_translator(f"{o1:02d}")),
                                    strip_spec_chars(
                                        rgi_code_translator(f"{o1:02d}-{o2:02d}")
                                    ),
                                    "500x500m.tif",
                                ]
                            )
                        )
                    ).read(1)
                )
            )
            * 0.25
        )

o2areas.sort_index().to_csv(
    snakemake_fallback(
        "output", 0, str(project_path("resources", "o2region__area_km2.csv"))
    )
)
