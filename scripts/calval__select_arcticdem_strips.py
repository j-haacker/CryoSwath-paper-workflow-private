from argparse import ArgumentParser
from cryoswath.misc import (
    load_glacier_outlines,
    rgi_code_translator,
)
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
from pathlib import Path
from pystac_client import Client as pyst_cl
from cryoswath_paper_workflow.workflow_support import (
    out_to_snakemake_log_or_fallback_stdout,
    project_path,
    rgi_names,
    snakemake_fallback_builder,
)

snakemake_fallback = snakemake_fallback_builder(globals())

catalog = pyst_cl.open("https://stac.pgc.umn.edu/api/v1")
query = dict(
    collections=["arcticdem-strips-s2s041-2m"],
    datetime="2010-08-01/2024-11-30",
)


def select_strips(points, rng):
    collection = gpd.GeoDataFrame(
        geometry=[p for p in points.iloc[0].geoms], crs=points.crs
    )
    collection = collection.assign(
        strip_ids=[
            "",
        ]
        * len(collection)
    )
    for idx, row in collection.to_crs(4326).iterrows():
        search = catalog.search(
            intersects={"type": "Point", "coordinates": row.geometry.coords[0]},
            **query,
        )
        collection.at[idx, "strip_ids"] = sorted([item.id for item in search.items()])
    collection.sort_values("strip_ids", key=lambda x: x.apply(len), inplace=True)
    for i in range(len(collection)):
        current = collection.strip_ids.iloc[i]
        previous = [x for lst in collection.strip_ids.iloc[:i] for x in lst]
        cleaned = [x for x in current if x not in previous]
        collection.iat[i, collection.columns.get_loc("strip_ids")] = (
            rng.choice(cleaned, 10, replace=False) if len(cleaned) > 10 else cleaned
        )
    return collection


def strip_filter(arr, axis=None):
    abs_max = np.nanmax(np.abs(arr), axis=axis)
    spread = np.nanmax(arr, axis=axis) - np.nanmin(arr, axis=axis)
    return (abs_max < 150) & (spread < 150)


def main(o1: int):
    gdf = load_glacier_outlines(f"{o1:02d}", "glaciers", union=False)
    gdf = gdf.loc[
        gdf["o2region"].isin(
            [
                f"{o1:02d}-{(o2 if o1 != 5 else 1):02d}"
                for o2 in rgi_names[o1].keys()
                if isinstance(o2, int)
            ]
        )
    ]

    if gdf.total_bounds[1] < 65:
        if gdf.total_bounds[3] > 85:
            raise Exception(f"Region {o1} covers 65-85 more than fully.")
        gdf = gdf.to_crs(gdf.estimate_utm_crs())
    else:
        gdf = gdf.to_crs(3413)
    # simplified union
    union = gpd.GeoSeries(
        gdf.simplify(500).make_valid().union_all("unary"), crs=gdf.crs
    )
    refdata_lockfile = Path(
        snakemake_fallback(
            "output",
            0,
            Path(
                "resources",
                "calval__select_arcticdem_strips__"
                + rgi_code_translator(f"{o1:02d}", out_type="long_code"),
            ).with_suffix(".lock.feather"),
        )
    )
    refdata_lockfile.parent.mkdir(parents=True, exist_ok=True)
    sample_points = union.sample_points(10, rng=np.random.default_rng(seed=o1))
    refdata_ids = select_strips(sample_points, rng=np.random.default_rng(seed=o1 + 10))
    refdata_ids.to_feather(refdata_lockfile)
    union.boundary.plot(zorder=1)
    gray_to_orange = LinearSegmentedColormap.from_list(
        "gray_to_orange", ["#9e9e9e", "#ff7700"]
    )
    refdata_ids["strip_count"] = refdata_ids.strip_ids.apply(len)
    refdata_ids.plot(
        ax=plt.gca(),
        column="strip_count",
        cmap=gray_to_orange,
        vmin=0,
        vmax=10,
        legend=True,
        legend_kwds={"label": "List length (0-10)"},
        zorder=10,
    )
    plt.title(rgi_code_translator(f"{o1:02d}") + f"  ({union.crs})")
    plt.savefig(
        snakemake_fallback(
            "output",
            1,
                str(
                    project_path(
                        "resources",
                        f"calval__select_arcticdem_strips__{rgi_code_translator(f'{o1:02d}', out_type='long_code')}.png",
                    )
                ),
        )
    )


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--o1", type=str, default="")
    with out_to_snakemake_log_or_fallback_stdout(
        globals().get("snakemake"), delete_old=True
    ):
        main(int(snakemake_fallback("wildcards", "token", parser.parse_args().o1)[:2]))
