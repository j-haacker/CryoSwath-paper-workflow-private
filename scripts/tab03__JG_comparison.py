import numpy as np
import pandas as pd
from textwrap import dedent
from cryoswath_paper_workflow.workflow_support import (
    out_to_snakemake_log_or_fallback_stdout,
    precision,
)
from typing import Protocol, runtime_checkable


@runtime_checkable
class snakemake_mock(Protocol):
    input: dict[int, str]
    output: dict[str, str]


snakemake = globals().get("snakemake", snakemake_mock)

ref_JG = pd.DataFrame.from_dict(
    {
        "Alaska": [83.1, 7.6],
        "Arctic Canada North": [23.2, 1.9],
        "Arctic Canada South": [23.4, 2.0],
        "Greenland Periphery": [23.8, 2.0],
        "Iceland": [3.5, 0.3],
        "Svalbard and Jan Mayen": [18.4, 1.6],
        "Russian Arctic": [18.4, 1.0],
    },
    orient="index",
    columns=["ref", "ref_err"],
)

def main():
    o1_trend_df = pd.read_csv(snakemake.input[0], index_col=0, header=[0, 1])
    print(o1_trend_df)
    with open(snakemake.output[0], "w") as f:
        print(
            dedent(
                r"""
                \begin{tabular}{l*{2}{@{\;\;}>{$}r<{$}@{ $\pm$ }>{$}l<{$}}}
                \tophline
                Region & \multicolumn{2}{l}{CryoSwath} & \multicolumn{2}{l}{JG23} \\
                \middlehline"""
            ).strip(),
            file=f,
        )
        for l, row in (
            o1_trend_df.loc(1)["10_20", ["mass", "m_err"]]
            .droplevel(0, axis=1)
            .join(ref_JG, how="inner")
            .iterrows()
        ):
            row.loc[["mass", "m_err"]] = list(
                map(lambda x: np.round(x, precision(row.m_err)), row.loc[["mass", "m_err"]])
            )
            print(l, *row.values, sep=" & ", end=" \\\\\n", file=f)
        print("\\bottomhline\n\\end{tabular}", end="", file=f)

if __name__ == "__main__":
    with out_to_snakemake_log_or_fallback_stdout(globals().get("snakemake"), delete_old=True):
        main()
