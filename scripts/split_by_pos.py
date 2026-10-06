"""Split data/botlikh_dicts.xlsx into one workbook per part of speech (data/pos_dicts/).

Usage (from the root of the repository):
    python3 scripts/split_by_pos.py
    python3 scripts/split_by_pos.py --src data/botlikh_dicts.xlsx --out data/pos_dicts

Every Botlikh row is kept (repeated lexemes with different translations stay as
separate rows). Only columns that are empty or constant for Botlikh are dropped.
One column is added: source_dict (SA2012 or AA2019), derived from `reference`.
"""
import argparse
import re
from pathlib import Path

import pandas as pd
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent

# pos value in the source table -> output file name
POS_FILES = {
    "noun": "nouns",
    "adj": "adjectives",
    "verb": "verbs",
    "adv": "adverbs",
    "pron": "pronouns",
    "num": "numerals",
    "adp": "postpositions",
    "part": "particles",
    "conj": "conjunctions",
    "intj": "interjections",
    "expression": "expressions",
    "onomatope": "onomatopoeia",
}
NO_POS_FILE = "no_pos"

SOURCE_SHORT = {
    "Saidova, Abusov 2012": "SA2012",
    "Alekseev, Azayev 2019": "AA2019",
}

COL_WIDTHS = {"lemma": 30, "definition": 90, "meaning_ru": 28, "meaning_ru_comment": 28, "ipa": 26}

ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean_cell(x):
    return ILLEGAL.sub("", x) if isinstance(x, str) else x


def write_xlsx(df: pd.DataFrame, path: Path) -> None:
    df = df.map(clean_cell)
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="dict")
        ws = xw.sheets["dict"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for i, col in enumerate(df.columns, start=1):
            ws.column_dimensions[get_column_letter(i)].width = COL_WIDTHS.get(col, 14)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "data" / "botlikh_dicts.xlsx"))
    ap.add_argument("--sheet", default="andic_dicts")
    ap.add_argument("--out", default=str(ROOT / "data" / "pos_dicts"))
    args = ap.parse_args()

    df = pd.read_excel(args.src, sheet_name=args.sheet)
    df = df[df["language"] == "Botlikh"].copy()
    total = len(df)
    print(f"Botlikh rows: {total}")

    dropped = [c for c in df.columns
               if df[c].isna().all() or df[c].nunique(dropna=False) == 1]
    df = df.drop(columns=dropped)
    print("dropped empty/constant columns:", dropped)

    df.insert(df.columns.get_loc("lemma") + 1, "source_dict",
              df["reference"].map(SOURCE_SHORT).fillna(df["reference"]))
    df = df.sort_values("id").reset_index(drop=True)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    written = 0
    for pos, name in POS_FILES.items():
        part = df[df["pos"] == pos]
        if part.empty:
            continue
        write_xlsx(part, out / f"{name}.xlsx")
        written += len(part)
        print(f"{name:15s} {len(part):6d} rows, {part['id_word'].nunique():6d} words")

    rest = df[~df["pos"].isin(POS_FILES)]
    if len(rest):
        write_xlsx(rest, out / f"{NO_POS_FILE}.xlsx")
        written += len(rest)
        print(f"{NO_POS_FILE:15s} {len(rest):6d} rows, {rest['id_word'].nunique():6d} words")

    assert written == total, (written, total)
    print("all rows accounted for:", written)


if __name__ == "__main__":
    main()
