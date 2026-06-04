# Changelog

## Unreleased

### Fixed

- Revised Snakemake `ancient()` markers so downloaded trend rasters are
  treated consistently as stable inputs, while coverage analysis becomes
  a normal dependency for the coverage/terrain complexity figure.
- Fixed sign conventions in Tables 2 and 3.
- Fixed treating "Region number" as numeric scale during plotting which
  let to defaulting to a less explicit palette and not mentioning all
  regions in the legend.
- Revise paper template, fixing multiple issues.

## v1 - 2026-06-02

### Added

- Published the first tagged release of the CryoSwath paper reproduction
  workflow.
