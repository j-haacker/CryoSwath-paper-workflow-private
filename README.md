# CryoSwath paper workflow

This repository contains the Snakemake workflow that builds the figures,
tables, and manuscript for the article.

## Requirements

Use a 64-bit Linux machine for this workflow and install `pixi`.

```bash
curl -fsSL https://pixi.sh/install.sh | sh
```

or, from an existing conda installation:

```bash
conda install conda-forge::pixi
```

See the Pixi installation docs at <https://pixi.prefix.dev/latest/installation/>
and the conda-forge package at <https://anaconda.org/conda-forge/pixi>.

While pixi is recommended, you can attempt to use the explicit conda
environment at `envs/default.linux-64.pin.txt` instead.

Likely you could run the workflow from UNIX machines or Windows through
`wsl`. If you do, expect that results can differ on insignificant
digits. Consider using provided lock files of randomly sampled points
(`resources/calval/select_arcticdem_strips__*.lock.feather`).

## Credentials

The workflow downloads some protected input data. Configure the relevant
credentials before running targets that need those downloads. The
registration at the concerned services is free; however, you can skip
the processing steps that involve the credentials by selecting
`downloaded` (as opposed to `produced`) for the concerned processing
steps.

### NSIDC/RGI Earthdata

RGI shapefile downloads use NASA Earthdata credentials. The workflow resolves
them in this order:

1. `earthdata_username` and `earthdata_password` in `config/snakemake.yaml`
2. `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD`
3. `$HOME/.netrc`
4. `./.netrc`
5. `./.nsidc_cookies`

The config-file fields are present but empty by default:

```yaml
earthdata_username: ""
earthdata_password: ""
```

### ESA CryoSat-2 L1b

ESA CryoSat-2 L1b downloads, including
`fig02__coherence_waveform_examples`, use ESA EOIAM credentials. Environment
variables are the recommended setup:

```bash
export EOIAM_USER="your-esa-username"
export EOIAM_PASSWORD="your-esa-password"
```

The ESA lookup order is `EOIAM_USER`/`EOIAM_PASSWORD`, keyring,
`$HOME/.netrc` with `machine science-pds.cryosat.esa.int`, and legacy
`config.ini` `[user]` `name`/`password`.

If the needed CryoSat-2 L1b files are already present in
`resources/l1b_cache/`, ESA credentials are not checked. If they are
missing, absent ESA credentials can make downloads fail or appear to
hang while the data access layer retries.

## Configuration

Edit `config/snakemake.yaml` to set configuration parameters, or pass
them on the command line with `--config key=value`. Here, you can opt-in
to (re)produce all intermediate results. The default is to download
those. Use `--config publication_artifact_source=produced` only when you
want the PDF workflow to regenerate artifact-only manuscript inputs and
figures from their upstream dependencies. That path can require
credentials and large downloads.

Further, you can opt-out of checking the server certificates
while downloading. This makes you vulnerable to "man-in-the-middle"
attacks and should be avoided; however, in the past it was necessary due
to expired certificates.

## Running the workflow

Snakemake keeps track of the produced and downloaded files and decides
based on their provenance and your configuration what to do. Generally,
`snakemake target` will attempt to produce the file `target`. `target`
can also be rules with only inputs which then are the produced files.
To run the entire workflow on one CPU core, use the following.

```shell
pixi run snakemake publication_reproduction --cores 1
```

Use `pixi run` so Snakemake can import the workflow dependencies while
parsing the Snakefile. Increase `--cores` to allow Snakemake to run
independent jobs in parallel (specifying the number of cores is
necessary).

The target `publication_reproduction` builds the rerunnable figures and
tables from downloaded derived CSV/YAML/TEX inputs, downloads archived
final figure artifacts for figures that depend on protected or
heavyweight inputs, and materializes `paper/manuscript.tex`. It does not
require ESA or Earthdata credentials.

## Render the manuscript PDF

Unfortunately, the TeX file cannot be compiled with the current portable
setup because all available engines fail for external reasons. That
means that you will need to make `pdflatex` available on your path with
the macros allowed for copernicus manuscripts to enable the last
workflow task. `tectonic` crashes when the Copernicus class loads
FontAwesome fonts, Pixi’s `texlive-core` is missing or cannot find
required TeX helper files, and Apptainer cannot run containers on hosts
without system-level namespace configuration. However, even if you do
not have a full texlive installation but access to `docker`, use the
following to render the manuscript.

```shell
docker run --rm \
    -v paper:/work \
    -w /work \
    -u "$(id -u):$(id -g) \
    texlive/texlive:latest \
    sh -c 'pdflatex manuscript.tex && pdflatex manuscript.tex'
```

## Source Controls

Use one explicit source selector for each analysis that can use either
downloaded outputs or locally produced outputs:

| Config key | Values | What it controls |
| --- | --- | --- |
| `calval_source` | `downloaded`, `produced` | Downloaded `resources/calval/compare_arcticdem_strips__*.csv` files vs rebuilding them |
| `coverage_analysis_source` | `downloaded`, `produced` | Downloaded `coverage_analysis.csv` vs rebuilding it |
| `glacierized_area_source` | `downloaded`, `produced` | Downloaded `resources/o2region__area_km2.csv` vs deriving it from the published trend rasters |
| `elevation_timeseries_source` | `downloaded`, `produced` | Downloaded `resources/Arctic_monthly_avg_glacier_surface_elevation_wrt_2010_per_RGI_o2region__meter.csv` vs deriving it from monthly datasets and cal/val summaries |
| `publication_artifact_source` | `downloaded`, `produced` | Archived manuscript inputs/final figures vs rebuilding protected/heavy artifact branches |

The published 2010-2024 trend rasters are always downloaded by this workflow to
`resources/trends_dataset/`. The area and elevation time-series tables are
active workflow outputs in `resources/` and can be downloaded or reproduced via
their own source selectors.

Downloaded publication inputs are read from `publication_data_url` by default.
`downloaded_analysis_data_url` and `publication_artifact_data_url` are optional
specialized overrides; leave them empty for a single 4TU publication-data
archive.

The 2010-2024 trend rasters can be reproduced using the separate 4TU trend
workflow at
`https://data.4tu.nl/v3/datasets/f8c6e417-7893-4c26-a532-296f59712089.git`.

If the 4TU monthly-data server has a broken TLS certificate, use
`--config download_verify_tls=false` to skip certificate verification.

## Build One Target From Inputs

Choose the target you want and override only the relevant source controls for
that run. Snakemake still builds only the dependency closure of the requested
target; setting `calval_source` or `coverage_analysis_source` to `produced`
does not make it build the whole workflow.

Rebuild the one-year cal/val summary from inputs:

```bash
pixi run snakemake results/one_year_error_correlation.txt --cores 1 --config calval_source=produced
```

Rebuild the Arctic-wide time-series figure using rebuilt cal/val summaries and
locally reproduced elevation time-series table:

```bash
pixi run snakemake paper/figures/fig04__arctic-wide_time_series.pdf --cores 1 --config elevation_timeseries_source=produced calval_source=produced
```

Rebuild the glacierized-area table from the published trend rasters:

```bash
pixi run snakemake resources/o2region__area_km2.csv --cores 1 --config glacierized_area_source=produced
```

Rebuild the coverage-analysis figure using published trend rasters:

```bash
pixi run snakemake paper/figures/fig16__coverage_terraincomplexity_correlation.pdf --cores 1 --config coverage_analysis_source=produced
```

## Common Target Hints

| Target family | Source controls that usually matter |
| --- | --- |
| `results/one_year_error_correlation.txt`, `paper/figures/figA1__*.pdf`, `paper/figures/figA2__*.pdf` | `calval_source` |
| `paper/figures/fig04__*.pdf`, `paper/figures/fig05__*.pdf` | `glacierized_area_source`, `elevation_timeseries_source`; `elevation_timeseries_source=produced` also follows `calval_source` |
| `results/tabA2__subregion_overview.tex` | Published trend rasters are always downloaded |
| `paper/figures/fig16__*.pdf`, `results/coverage_analysis.csv` | `coverage_analysis_source`; published trend rasters are always downloaded |
| `publication_reproduction` | Default downloaded source controls plus `publication_artifact_source`; no credentials when the publication archive is configured |
| `paper/manuscript.pdf` | `calval_source`, `coverage_analysis_source`, `glacierized_area_source`, `elevation_timeseries_source`, `publication_artifact_source`; published trend rasters are always downloaded |

## Resource Usage

Benchmark files are operational diagnostics written under `logs/` and are
ignored by Git. The numbers below are approximate, machine-dependent ranges
from local benchmark runs; use them to choose targets and `--cores`, not as
strict performance guarantees.

| Rule family | Expected resource profile |
| --- | --- |
| Downloaded-source publication path | Mostly light once downloaded inputs are present. The public `publication_reproduction` target reruns tabular-derived figures and materializes `paper/manuscript.tex`; protected/heavy manuscript artifacts are downloaded as final files. |
| Produced-source manuscript path | Summary notebooks generally run in seconds to a few minutes; `result__value_collection` is the main memory-sensitive step and has reached about 25 GB peak RAM locally. |
| Produced cal/val path | Strip selection is moderate, about 0.5-1.5 minutes and under 1 GB RAM per region. Strip comparison is the heavy step, about 2-8 minutes per region and potentially very memory-heavy; local runs have reached about 90 GB RAM. |
| Closeup icecap notebooks | About 0.5-4 minutes per target. These are memory-sensitive, with local runs around 15-50 GB RAM depending on the region. |
| Coverage analysis path | `coverage_analysis` is the critical step, about 1-2 minutes and around 10 GB RAM in local runs with 24 threads. The downstream coverage figure is light. |
| Iceland/reference trend path | Subset, trend, and comparison steps are typically about 0.5-4 minutes and mostly 1-3 GB RAM in this workflow. Full trend-raster production in the separate 4TU workflow is much heavier. |
| Large downloads | ArcticDEM mosaic and remote archives are disk- and network-bound. Benchmark memory usage is not representative of the download size or required free disk space. |
