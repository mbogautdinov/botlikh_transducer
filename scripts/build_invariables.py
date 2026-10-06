"""Generate the lexicons of the invariable words and of the clitics: invariables/invariables_lexicon.lexd, clitics_lexicon.lexd.

Usage (from the root of the repository):  python scripts/build_invariables.py [--no-palochka] [--drop STATUS ...]

Inputs : invariables/invariables_auto.tsv      (made by scripts/parse_invariables.py)
         invariables/invariables_manual.tsv    (optional hand corrections: columns action(add|drop), pos, upper, lower, class_tag, note)
         invariables/clitics_closed.tsv        (hand-curated clitics)
Outputs: invariables/invariables_lexicon.lexd, invariables/clitics_lexicon.lexd
         invariables/invariables_expanded.tsv  (everything that went into the lexicon, incl. palochka variants)
         invariables/invariables_mwe.tsv       (multiword entries: not compiled, spaces cannot be written in lexd entries)

Orthographic variation is NOT written into the lexicon: the lexicon has one entry per word (palochka as Latin I, the nasal
vowel of the dictionary as ᴴ) and invariables/invariables.twol rewrites it on the surface:  I -> I, Ӏ, ӏ, 1   and   ᴴ -> ᴴ, н.
invariables_expanded.tsv still lists every surface variant (it is the input of the tests); --no-palochka leaves them out.
Lexicon files carry no bracket tags; the comment (the translation) stands in one column.
The patterns (invariables_formation.lexd, clitics_formation.lexd) and the rules (invariables.twol) are separate files that are
written by hand; the Makefile joins the patterns with these lexicons.
"""
import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "invariables"
LEXNAME = {"ADV": "Adv", "POSTP": "Postp", "PTCL": "Ptcl", "CONJ": "Conj", "INTJ": "Intj", "ONOM": "Onom"}
PAL = ["Ӏ", "ӏ", "1"]


def read_tsv(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def lexd_safe(s):
    for ch in ":[]<>()|?+*%{}\\":
        assert ch not in s, f"special character {ch!r} in {s!r}"
    return s


def aligned(entries):
    """entries: (body, comment); the comments start in one column."""
    width = max((len(b) for b, c in entries if c), default=0) + 2
    return [f"{b.ljust(width)}# {c}" if c else b for b, c in entries]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-gloss", action="store_true", help="do not write the translation comments after #")
    ap.add_argument("--no-palochka", action="store_true")
    ap.add_argument("--drop", nargs="*", default=[], help="statuses to leave out (e.g. class_var variant)")
    a = ap.parse_args()

    rows = read_tsv(INV / "invariables_auto.tsv")
    manual = INV / "invariables_manual.tsv"
    drops, adds = set(), []
    if manual.exists():
        for m in read_tsv(manual):
            if m["action"] == "drop":
                drops.add((m["pos"], m["upper"], m["lower"], m.get("class_tag", "")))
            elif m["action"] == "add":
                adds.append(dict(pos=m["pos"], upper=m["upper"], lower=m["lower"], class_tag=m.get("class_tag", ""),
                                 status="manual", source="manual", ids="", orig="", note=m.get("note", ""), gloss=m.get("gloss", "")))
    rows = [r for r in rows if (r["pos"], r["upper"], r["lower"], r["class_tag"]) not in drops] + adds
    rows = [r for r in rows if r["status"] not in a.drop]
    # the н-spellings of ᴴ-words are produced by invariables.twol, not listed
    rows = [r for r in rows if r["status"] != "nasal_n"]

    mwe = [r for r in rows if " " in r["lower"]]
    rows = [r for r in rows if " " not in r["lower"]]
    with open(INV / "invariables_mwe.tsv", "w", encoding="utf-8") as f:
        f.write("pos\tupper\tlower\tsource\n")
        for r in mwe:
            f.write(f"{r['pos']}\t{r['upper']}\t{r['lower']}\t{r['source']}\n")

    by = {k: [] for k in LEXNAME}
    seen = set()
    expanded = []
    for r in rows:
        key = (r["pos"], r["upper"], r["lower"], r["class_tag"])
        if key in seen:
            continue
        seen.add(key)
        tags = r["upper"] + "<" + r["pos"] + ">" + (f"<{r['class_tag']}>" if r["class_tag"] else "")
        lexd_safe(r["upper"]); lexd_safe(r["lower"])
        gl = (r.get("gloss") or "").replace("#", " ").strip()
        by[r["pos"]].append((f"{tags}:{r['lower']}", "" if a.no_gloss else gl))
        # surface variants for the tests (made by the twol rules)
        variants = [(r["lower"], r["status"])]
        if not a.no_palochka:
            for low, st in list(variants):
                if "I" in low:
                    variants += [(low.replace("I", p), r["status"] + ",palochka") for p in PAL]
            for low, st in list(variants):
                if "ᴴ" in low:
                    variants.append((low.replace("ᴴ", "н"), "nasal_n" + (",palochka" if "palochka" in st else "")))
        for low, st in variants:
            expanded.append((r["pos"], r["upper"], low, r["class_tag"], st, r["source"]))

    out = []
    for pos, name in LEXNAME.items():
        out.append(f"LEXICON {name}")
        out.append("")
        out.extend(aligned(by[pos]))
        out.append("")
        out.append("")
    (INV / "invariables_lexicon.lexd").write_text("\n".join(out), encoding="utf-8")
    with open(INV / "invariables_expanded.tsv", "w", encoding="utf-8") as f:
        f.write("pos\tupper\tlower\tclass_tag\tstatus\tsource\n")
        for e in expanded:
            f.write("\t".join(e) + "\n")

    cl = read_tsv(INV / "clitics_closed.tsv")
    cout = ["LEXICON Clitic", ""]
    cseen = set()
    centries = []
    for c in cl:
        cls = (c.get("class") or "").strip()   # class marker of a clitic that agrees in class: =<restr>><n>
        key = (c["form"], c["tag"], cls)
        if key in cseen:
            continue
        cseen.add(key)
        lexd_safe(c["form"])
        gl = c.get("gloss", "").replace("#", " ").strip()
        tag = "<" + c["tag"] + ">" + (f"><{cls}>" if cls else "")
        centries.append((f"={tag}:{c['form']}", "" if a.no_gloss else gl))
    cout.extend(aligned(centries))
    (INV / "clitics_lexicon.lexd").write_text("\n".join(cout) + "\n", encoding="utf-8")
    n = sum(len(v) for v in by.values())
    print(f"{n} lexicon entries ({len(mwe)} multiword entries left out), {len(cseen)} clitic entries")


if __name__ == "__main__":
    main()
