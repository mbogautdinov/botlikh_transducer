"""Generate the lexicon of the numerals: numerals/numerals_lexicon.lexd, from numerals/numerals_closed.tsv.

Usage (from the root of the repository):  python3 scripts/build_numerals.py

numerals_closed.tsv is the hand-curated closed lexicon (columns: lexicon, upper, lower, tags, status, source, note).
Three lexicons are expanded by formulas from the Unit / Ten / One rows:
  Big       : compound hundreds, thousands and hundreds of thousands (кIебешунуда, кIеазаруда, бикьибешуназаруда)
  DistrStem : reduplicated stems (кIе-кIе, ...), including the attested variant иштуштуда
  DistrOne  : це-це
The expanded lexicon is also written to numerals/numerals_expanded.tsv for inspection.
The comment after a stem is its value (2, 300, 7000). The patterns (numerals_formation.lexd) and the rules (numerals.twol)
are separate files that are written by hand; the Makefile joins the patterns with this lexicon.
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "numerals" / "numerals_closed.tsv"


def read_rows():
    with open(SRC, encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f, delimiter="\t")]


def expand(rows):
    units = [r for r in rows if r["lexicon"] == "Unit"]
    ten = [r for r in rows if r["lexicon"] == "Ten" and r["tags"] != "short"]
    extra = []

    def add(lex, upper, lower, tags, status, source, note="", value=""):
        extra.append(dict(lexicon=lex, upper=upper, lower=lower, tags=tags, status=status, source=source, note=note, value=str(value)))

    def number(r):
        m = re.match(r"\d+", r.get("note") or "")
        return int(m.group(0)) if m else 0

    # Big: hundreds, thousands, hundreds of thousands
    for u in units:
        s = u["lower"]
        add("Big", s + "бешунуда", s + "бешуну", "th_j", "rule", "formula", f"{u['upper']} x 100", number(u) * 100)
        add("Big", s + "азаруда", s + "азару", "th_j", "rule", "formula", f"{u['upper']} x 1000", number(u) * 1000)
        add("Big", s + "бешунуда", s + "-бешуну", "th_j,hyph", "attested", "AA2019 spelling with hyphen (инлIи-бешунуда)", f"{u['upper']} x 100, hyphenated", number(u) * 100)
    # hundreds with the short stem бешун- before -да: гьакьубешунда (SA2012), гьабубешунда, гьачIабешунда (corpus)
    for u in units:
        s = u["lower"]
        st = "attested" if s in ("гьакьу", "гьабу", "гьачIа") else "rule"
        add("Big", s + "бешунуда", s + "бешун", "shorth", st, "SA2012 (гьакьубешунда); lingconlab corpus (гьабубешунда, гьачIабешунда)", f"{u['upper']} x 100, short stem before -да", number(u) * 100)
    # hundred thousand: hundred stem loses -у before азару (бикьибешуназаруда, SA2012)
    for u in [None] + units:
        hs = (u["lower"] if u else "") + "бешуну"
        add("Big", hs[:-1] + "азаруда", hs[:-1] + "азару", "th_j", "rule", "formula", "x 100000", (number(u) if u else 1) * 100000)
    # ordinal-only variant with -да inside (гьакьудазаруйхоб, SA/AA)
    add("Big", "гьакьудазаруда", "гьакьудазару", "th_j,ordonly", "attested", "AA2019 (гьакьудазаруйхоб)", "7000th", 7000)

    # distributive: reduplicated stem
    for u in units + ten:
        s = u["lower"]
        add("DistrStem", u["upper"], f"{s}-{s}", "", "attested" if s in ("кIе", "бугъу", "инлIи", "бикьи", "гьачIа", "гьакьу", "гьацIа", "ишту") else "rule", "SA2012", "reduplication")
    add("DistrStem", "иштуда", "иштушту", "", "attested", "SA2012", "variant иштуштуда")
    add("DistrOne", "цеб", "це-це", "", "attested", "SA2012", "це-церикку, це-цебикку, це-цев")
    return extra


STEMS = ("Unit", "Ten", "Hundred", "Thousand", "One", "OneOrd")


def entry_line(r):
    """-> (entry, comment); the comment is the value of the numeral, only for stems"""
    lower = r["lower"]
    upper = r["upper"]
    tags = f"[{r['tags']}]" if r["tags"] else ""
    value = r.get("value") or ""
    if not value and r["lexicon"] in STEMS:
        m = re.match(r"\d+", r.get("note") or "")
        value = m.group(0) if m else ("1" if r["lexicon"] == "OneOrd" else "")
    if upper == lower and not tags:
        return upper, value
    return f"{upper}:{lower}{tags}", value


def main():
    rows = read_rows()
    allrows = rows + expand(rows)
    order = []
    for r in allrows:
        if r["lexicon"] not in order:
            order.append(r["lexicon"])
    out = []
    seen = set()
    for lex in order:
        out.append(f"LEXICON {lex}")
        out.append("")
        entries = []
        for r in (x for x in allrows if x["lexicon"] == lex):
            key = (lex, r["upper"], r["lower"], r["tags"])
            if key in seen:
                continue
            seen.add(key)
            entries.append(entry_line(r))
        width = max((len(b) for b, n in entries if n), default=0) + 2   # comments in one column
        for body, note in entries:
            out.append(f"{body.ljust(width)}# {note}" if note else body)
        out.append("")
        out.append("")
    (ROOT / "numerals" / "numerals_lexicon.lexd").write_text("\n".join(out), encoding="utf-8")
    with open(ROOT / "numerals" / "numerals_expanded.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(allrows[0].keys()), delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(allrows)
    print(f"{len(seen)} lexicon entries in {len(order)} lexicons -> numerals/numerals_lexicon.lexd")


if __name__ == "__main__":
    sys.exit(main())
