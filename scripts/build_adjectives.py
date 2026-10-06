"""Generate the lexicon of the adjectives: adjectives/adjectives_lexicon.lexd.

Usage (from the root of the repository):  python scripts/build_adjectives.py [--no-gloss] [--drop-guess]

Input : adjectives/adjectives_auto.tsv       (scripts/parse_adjectives.py)
        adjectives/adjectives_manual.tsv     (optional: action add|drop, see the file)
Output: adjectives/adjectives_lexicon.lexd   stems with the translation after '#', comments aligned in one column
        adjectives/adjectives_skipped.tsv    entries that are not compiled (see below)
The patterns (adjectives/adjectives_formation.lexd) and the rules (adjectives/adjectives.twol) are separate files that are
written by hand; the Makefile joins the patterns with this lexicon.

The lexicon is split by where the class marker stands (SA2012 p.546-548, AA2019); there are no other types:
  AdjNo      no class marker                           ирхха, гьацIахха
  AdjPre     class prefix only                         в-/й-/б-/р-ечIер
  AdjSuf     class suffix only                         маквас-о(в)/-ай/-аб/-ал, ссу
  AdjPreSuf  class prefix and class suffix together    в-ечIух-о(в), й-ечIух-ай, б-ечIух-аб, р-ечIух-ал
A stem that ends in -а is written with {A} (-а > -о before the masculine/neuter archiphonemes), a stem in -у is written as it is.
No tags are written: statuses stay in adjectives_auto.tsv, the stem type is read from the stem itself by the twol rules.

Not compiled (adjectives_skipped.tsv): class marker inside the word (ссебитIаб, гьивдалIи, цебда), multiword entries
(spaces cannot be written in lexd), cited-only entries (ethnic -алуб, noun forms in -ай / -ал, unclear -иб/-уб):
the last group belongs to the noun module.
"""
import argparse
import csv
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADJ = ROOT / "adjectives"
TYPES = {"no_class": "AdjNo", "class_prefix": "AdjPre", "class_suffix": "AdjSuf", "class_prefix_suffix": "AdjPreSuf"}


def read_tsv(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def lexd_safe(s):
    for ch in ":[]<>()|?+*%{}\\#":
        if ch in s.replace("{A}", ""):
            raise AssertionError(f"special character {ch!r} in {s!r}")
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-gloss", action="store_true")
    ap.add_argument("--drop-guess", action="store_true", help="leave out entries whose type rests on a guess (guess_o, guess_prefix)")
    a = ap.parse_args()

    rows = read_tsv(ADJ / "adjectives_auto.tsv")
    manual = ADJ / "adjectives_manual.tsv"
    if manual.exists():
        for m in read_tsv(manual):
            if m["action"] == "drop":
                rows = [r for r in rows if not (r["lemma"] == m["lemma"] and (not m.get("type") or r["type"] == m["type"]))]
            elif m["action"] == "add":
                rows.append(dict(type=m["type"], subtype=m.get("subtype", ""), lemma=m["lemma"], stem=m["stem"], stem2=m.get("stem2", ""),
                                 pref=m.get("pref", ""), suf=m.get("suf", ""), cited=m.get("cited", m["lemma"]), plain=m.get("plain", m["lemma"]),
                                 status="manual", evidence="manual", flags="", gloss=m.get("gloss", ""), source="manual", id="", orig="", hint=""))
    if a.drop_guess:
        rows = [r for r in rows if "guess" not in r["flags"]]

    skipped = [r for r in rows if r["type"] not in TYPES]
    rows = [r for r in rows if r["type"] in TYPES]
    with open(ADJ / "adjectives_skipped.tsv", "w", encoding="utf-8") as f:
        f.write("type\tsubtype\torig\tsource\tgloss\n")
        for r in skipped:
            f.write(f"{r['type']}\t{r['subtype']}\t{r['orig']}\t{r['source']}\t{r['gloss']}\n")

    lex = OrderedDict((name, OrderedDict()) for name in TYPES.values())
    for r in rows:
        name = TYPES[r["type"]]
        lemma, stem = r["lemma"], r["stem"]
        if name in ("AdjSuf", "AdjPreSuf") and stem.endswith("а"):
            stem = stem[:-1] + "{A}"
        d = lex[name]
        key = (lexd_safe(lemma), lexd_safe(stem))
        d.setdefault(key, [])
        g = "" if a.no_gloss else r["gloss"]
        if g and g not in d[key] and len(d[key]) < 3:
            d[key].append(g)

    out = []
    n = 0
    for name, d in lex.items():
        out += [f"LEXICON {name}", ""]
        ents = [(f"{up}:{low}", " | ".join(gl)) for (up, low), gl in d.items()]
        n += len(ents)
        w = max((len(e) for e, _ in ents), default=0) + 2
        out += [f"{e.ljust(w)}# {c}" if c else e for e, c in ents]
        out += ["", ""]
    lexicon = "\n".join(out)
    (ADJ / "adjectives_lexicon.lexd").write_text(lexicon, encoding="utf-8")
    print(f"{n} lexicon entries; {len(skipped)} entries not compiled (adjectives_skipped.tsv)")


if __name__ == "__main__":
    main()
