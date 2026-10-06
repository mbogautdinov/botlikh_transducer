"""Collect the four Botlikh stories of the site "буйхалъи ххабарде" into one table: evaluation/texts/botlikh_khabar.tsv.

Source: https://sverhees.github.io/botlikh_khabar/ (compiled by G. Moroz, C. Naccarato and S. Verhees, 2020),
repository https://github.com/sverhees/botlikh_khabar. The files are taken at a fixed commit, so the result
is always the same. The stories were recorded by T. Gudava and Kh. Azaev in the 1950s-1970s.

Usage (from the root of the repository):  python3 scripts/make_khabar_texts.py [--local PATH_TO_A_CLONE]

Output columns: text_id, title, title_ru, recorded_by, sentence_nr, botlikh, russian
The texts are not changed in any way (no normalisation); the preprocessing for the evaluation is done in the notebook.
"""
import argparse
import io
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
COMMIT = "da6915e335b6d03ea3125dfe01b0fe8eab99d60b"   # 2023-06-18, the last commit of the repository
RAW = "https://raw.githubusercontent.com/sverhees/botlikh_khabar/" + COMMIT + "/texts/"

TEXTS = [  # file, id, title on the site, Russian title, who recorded the text (as stated on the site)
    ("azaev_text1.xlsx", "happiness", "Регьинлъи талихI", "Семейное счастье", "Azaev"),
    ("azaev_text2.xlsx", "khan", "Ханилъила гьабуда вашащуб хIахъалдала муха", "Сказка о хане и трех его сыновьях", "Azaev"),
    ("lamb.xlsx", "lamb", "Денла диб кьетIирла", "Я и мой ягненок", "Gudava"),
    ("brick.xlsx", "brick", "Керпеч инлала игье", "Как сделать кирпич", "Gudava"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="folder 'texts' of a local clone of the repository (instead of downloading)")
    a = ap.parse_args()
    parts = []
    for fname, tid, title, title_ru, who in TEXTS:
        if a.local:
            df = pd.read_excel(Path(a.local) / fname)
        else:
            with urllib.request.urlopen(RAW + fname) as r:
                df = pd.read_excel(io.BytesIO(r.read()))
        df = df[df["botlikh"].notna()].copy()
        out = pd.DataFrame({
            "text_id": tid, "title": title, "title_ru": title_ru, "recorded_by": who,
            "sentence_nr": df["nr"].astype(int),
            "botlikh": df["botlikh"].astype(str).str.strip(),
            "russian": df["russian"].fillna("").astype(str).str.strip(),
        })
        parts.append(out)
        print(f"{tid:10s} {len(out):4d} rows")
    res = pd.concat(parts, ignore_index=True)
    for c in ("botlikh", "russian"):
        res[c] = res[c].str.replace(r"[\t\r\n]+", " ", regex=True)
    dest = ROOT / "evaluation" / "texts" / "botlikh_khabar.tsv"
    dest.parent.mkdir(exist_ok=True)
    res.to_csv(dest, sep="\t", index=False, lineterminator="\n")
    print(len(res), "rows ->", dest)


if __name__ == "__main__":
    main()
