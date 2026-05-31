from cryoswath.misc import load_glacier_outlines
import matplotlib as mpl
import matplotlib.pyplot as plt
import seaborn as sns
from cryoswath_paper_workflow.workflow_support import (
    out_to_snakemake_log_or_fallback_stdout,
    project_path,
    snakemake_fallback_builder,
)
import xarray as xr

mpl.rcParams["svg.fonttype"] = "none"
sns.set_theme()
sns.set_context("paper")

snakemake_fallback = snakemake_fallback_builder(globals())


def main():
    trend_path = snakemake_fallback(
        "input",
        "trend",
        str(
            project_path(
                "data",
                "L4",
                "Glacier_surface_elevation_trend_2010-2024__Russian_Arctic__Severnaya_Zemlya__500x500m.tif",
            )
        ),
    )
    monthly_path = snakemake_fallback(
        "input",
        "monthly_ds",
        str(
            project_path(
                "data",
                "L3",
                "Glacier_surface_elevation__Russian_Arctic__Severnaya_Zemlya__monthly_500x500m.nc",
            )
        ),
    )

    with xr.open_dataset(monthly_path) as ds:
        data_crs = ds.rio.crs
        if data_crs is None:
            raise ValueError(f"Monthly dataset has no CRS: {monthly_path}")
        vavilov_outline = load_glacier_outlines(
            ["RGI2000-v7.0-C-09-00305"], crs=data_crs
        )
        elevs = ds.rio.clip([vavilov_outline])

    with xr.open_dataarray(trend_path) as ds:
        if ds.rio.crs is None:
            ds = ds.rio.write_crs(data_crs)
        trends = ds.rio.clip([vavilov_outline])

    mask = (
        (trends.isel(band=0) > 1)  # select the feature by surface trend
        & (elevs.elev_diff_interp_flag == 0)  # only use observed elevations
        & (elevs.x >= 728_000)  # limit the considered extent to exclude grid cells
        & (elevs.x <= 737_000)  #   that are not close to the feature
        & (elevs.y >= 889_000)
        & (elevs.y <= 896_000)
    )

    fig, ax = plt.subplots(2, figsize=(12 / 2.54, 15 / 2.54), height_ratios=[2, 3])
    trends.isel(band=0).plot(
        ax=ax[0], cmap="RdYlBu", cbar_kwargs={"label": "Surface elevation trend, m/yr"}
    )
    mask.any("time").plot.contour(
        ax=ax[0], levels=[-1, 0.5], colors=["k"], linewidths=0.67
    )
    ax[0].set_title("")
    ax[0].set_aspect("equal")
    unc2sig = (
        2
        * (
            elevs.elev_diff_error.where(mask).coarsen(x=4, y=4, boundary="pad").sum()
            ** 2
        ).sum(["x", "y"])
        ** 0.5
        / mask.sum(["x", "y"])
    )
    ax[1].errorbar(
        elevs.get_index("time"),
        elevs.elev_diff.where(mask).mean(["x", "y"]),
        unc2sig,
        ecolor="r",
        capsize=2,
        label="Avg. elevation",
    )
    ax[1].set_ylabel("Avg. elevation difference to ArcticDEM, m")
    ax[1].legend()
    for label, ax in zip(["a", "b"], ax):
        ax.annotate(
            label,
            xy=(0, 1),
            xycoords="axes fraction",
            xytext=(+0.5, -0.5),
            textcoords="offset fontsize",
            fontsize="medium",
            verticalalignment="top",
            fontfamily="serif",
            fontweight="bold",
            bbox=dict(facecolor=(1, 1, 1, 0.4), edgecolor="k", pad=3.0),
        )
    fig.tight_layout()
    fig.savefig(
        snakemake_fallback(
            "output", 0, str(project_path("figures", "figA3__vavilov_feature.pdf"))
        )
    )


if __name__ == "__main__":
    with out_to_snakemake_log_or_fallback_stdout(
        globals().get("snakemake"), delete_old=True
    ):
        main()
