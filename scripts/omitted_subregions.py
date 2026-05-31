from cryoswath.misc import rgi_code_translator
import pandas as pd
from cryoswath_paper_workflow.workflow_support import (
    o1o2reg_tuple_list,
    out_to_snakemake_log_or_fallback_stdout,
    to_yaml,
)
from typing import Protocol, runtime_checkable


@runtime_checkable
class snakemake_mock(Protocol):
    input: dict[int, str]
    output: dict[str, str]


snakemake = globals().get("snakemake", snakemake_mock)


def main():
    df = pd.read_csv(snakemake.input[0])
    df = df[
        df.o1region.isin([o1 for o1, _ in o1o2reg_tuple_list if o1 != 5])
    ]  # excluding Greenland Periphery because of custom subregions
    omitted = df[
        ~df.o2region.isin(
            [
                f"{o1:02d}-{o2:02d}"
                for o1, o2_list in o1o2reg_tuple_list
                for o2 in o2_list
            ]
        )
    ]
    omitted = omitted.groupby("o2region").area_km2.sum().to_frame()
    omitted["area_o1share"] = omitted.apply(
        lambda row: (
            row.area_km2 / df.groupby("o1region").area_km2.sum().at[int(row.name[1])]
        ),
        axis=1,
    )
    omitted["subreg"] = rgi_code_translator(omitted.index.values.tolist())
    omitted.sort_index().to_csv(snakemake.output[0])


if __name__ == "__main__":
    with out_to_snakemake_log_or_fallback_stdout(
        globals().get("snakemake"), delete_old=True
    ):
        main()
