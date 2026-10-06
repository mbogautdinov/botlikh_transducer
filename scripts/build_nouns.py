"""Build the noun lexicon from data/botlikh_dicts.xlsx (sheet andic_dicts, language Botlikh, pos noun; SA2012 + AA2019).

Usage (from the root of the repository):  python3 scripts/build_nouns.py [--xlsx PATH]

Input : data/botlikh_dicts.xlsx      the dictionary table
        nouns/nouns_manual.tsv       hand-written: lemmas that are not in the dictionaries (names, toponyms, words of the corpus)
                                     and plural suffixes attested in the corpus for lemmas of the dictionaries
Output: nouns/nouns_auto.tsv         one row per lemma: plain lemma, gloss, sources, original headword, hints from the definition
                                     (plural 'мн.', genitive 'рп.')
        nouns/nouns_lexicon.lexd     LEXICON NounH (the plural suffix is known from the hint: one tag per suffix) and
                                     LEXICON NounU (no hint: no plural forms);  lemma:lemma[tags]  # translation
        nouns/nouns_skipped.tsv      headwords that are not compiled (multiword, unparsed notation)
        nouns/nouns_review.tsv       plural hints that could not be read
The patterns (nouns/nouns_formation.lexd) and the rules (nouns/nouns.twol) are separate files that are written by hand;
the Makefile joins the patterns with this lexicon.

Plural tags (from the hint 'мн. -X' of AA2019): de -де, e -е, balji -балъи, abalji -абалъи, jabalji -йабалъи, ibalji -ибалъи,
vabalji -вабалъи, zabalji -забалъи, malji -малъи, dalji -далъи, dilji -дилъи, bdalji -бдалъи, bdilji -бдилъи, al -ал, l -л, ve -ве.
The hint '-' is not read as 'no plural' (AA2019 gives 'мн. -' for гьуркьа, but its grammar has the plural гьуркье).

Cleaning of the headword: stress marks and the notation signs / \\ = are removed; 'a // b' gives two lemmas; an optional segment
'ади́н(м)чIу' gives both spellings; multiword headwords and headwords with '?' are skipped. Vowel length is not written in the
transducer: the length sign of the dictionaries (ба:бу, кье:) is removed. Glosses: column meaning_ru, at most 3 per lemma.
Palochka (I) and the nasal ᴴ are spelled once; nouns.twol rewrites them.
"""
import argparse
import csv
import re
from collections import OrderedDict, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
NOUNS = ROOT / "nouns"
DEFAULT_XLSX = str(ROOT / "data" / "botlikh_dicts.xlsx")
ACCENT = "́̄"
LENGTH = re.compile(r":(?!\s)")   # the length sign of the dictionaries: a colon that is not followed by a space
SRC = {"Alek": "AA2019", "Said": "SA2012"}


def lemma_variants(raw):
    """-> (list of plain lemmas, reason or None)"""
    s = re.sub("[" + ACCENT + "]", "", str(raw)).strip()
    s = LENGTH.sub("", s)          # vowel length is not written
    if " " in s and "//" not in s:
        return [], "multiword"
    if any(ch in s for ch in ':?"’'):
        return [], "unparsed notation"
    out = []
    for part in s.split("//"):
        part = part.strip()
        if " " in part:
            return [], "multiword"
        part = re.sub(r"[/\\=]", "", part)
        m = re.search(r"\(([^()]*)\)", part)
        if m:
            if not re.fullmatch(r"[а-яА-ЯI]+", m.group(1)):
                return [], "unparsed notation"
            out += [part[:m.start()] + m.group(1) + part[m.end():], part[:m.start()] + part[m.end():]]
        else:
            out.append(part)
    out = [x for x in dict.fromkeys(out) if x and re.fullmatch(r"[а-яёА-ЯЁIᴴ-]+", x)]
    return (out, None) if out else ([], "unparsed notation")


def hints(defn):
    d = re.sub("[" + ACCENT + "]", "", str(defn))
    m = re.search(r"мн\.\s*([^,;]*?)\s*,\s*рп\.\s*([^\s;]+)", d)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.search(r"рп\.\s*([^\s;]+)", d)
    if m:
        return "", m.group(1).strip()
    m = re.search(r"мн\.\s*([^\s,;]+)", d)
    return (m.group(1).strip(), "") if m else ("", "")


def more_plural_hints(defn, first):
    """Plural hints of the other senses of an entry (хъуча: '1. мн. -е ... 2. мн. -ибалъи'): every 'мн. -X' after the first one."""
    d = re.sub("[" + ACCENT + "]", "", str(defn))
    found = [x.strip() for x in re.findall(r"мн\.\s*(-[^\s,;()]+)", d)]
    return [x for x in dict.fromkeys(found) if x != first and x in PL_TAGS]


PL_TAGS = {"-де": "de", "-е": "e", "-балъи": "balji", "-абалъи": "abalji", "-йабалъи": "jabalji", "-ибалъи": "ibalji",
           "-вабалъи": "vabalji", "-забалъи": "zabalji", "-малъи": "malji", "-далъи": "dalji", "-дилъи": "dilji", "-бдалъи": "bdalji", "-бдилъи": "bdilji", "-ал": "al", "-л": "l", "-ве": "ve"}
PL_SPECIAL = {"-де(е)": ["-де", "-е"], "-е(е)": ["-е"], "-(де)": ["-де"], "-де(де)": ["-де"], "-(а)балъи": ["-абалъи", "-балъи"],
              "-де(абалъи)": ["-де", "-абалъи"], "-де(-абалъи)": ["-де", "-абалъи"], "-абалъи(-ве)": ["-абалъи", "-ве"], "-е(ибалъи)": ["-е", "-ибалъи"],
              "-а(а)балъи": ["-абалъи"], "-и(и)балъи": ["-ибалъи"], "-абалъи(де)": ["-абалъи", "-де"]}


SHU_ONLY = {"ваша", "вацци"}   # sons / brothers: -щу-; daughters / sisters: -лълъи-
LLI_ONLY = {"йеши", "йацци"}
L_EXTRA = {"вацци", "йацци", "ваша", "йеши", "макIи"}


def plural_tags(pl_hint):
    """-> (sorted tags, unread tokens) from the plural hint(s) of a lemma"""
    tags, bad = [], []
    for part in pl_hint.split(" | "):
        for tok in part.split("/"):
            t = re.sub(r"\s+", "", tok.replace("–", "-"))
            if t in ("", "-"):
                continue
            alt = re.fullmatch(r"(-[а-яI]+)\(-?([а-яI]+)\)", t)   # 'X (Y)', 'X(-Y)': two plural suffixes
            if t not in PL_SPECIAL and alt and alt.group(1) in PL_TAGS and "-" + alt.group(2) in PL_TAGS:
                parts = [alt.group(1), "-" + alt.group(2)]
            else:
                parts = PL_SPECIAL.get(t, [t])
            for x in parts:
                if x in PL_TAGS:
                    if PL_TAGS[x] not in tags:
                        tags.append(PL_TAGS[x])
                else:
                    bad.append(tok.strip())
    return tags, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=DEFAULT_XLSX)
    a = ap.parse_args()
    df = pd.read_excel(a.xlsx, sheet_name="andic_dicts")
    n = df[(df.language == "Botlikh") & (df.pos == "noun")].copy()
    n["src"] = n.reference.str[:4].map(SRC)
    n = n.drop_duplicates(["src", "id_word", "id_meaning"])

    lemmas = OrderedDict()
    skipped = []
    for _, r in n.iterrows():
        vs, why = lemma_variants(r.lemma)
        gl = str(r.meaning_ru).strip() if pd.notna(r.meaning_ru) else ""
        if why:
            skipped.append((why, r.lemma, r.src, gl))
            continue
        pl, gen = hints(r.definition)
        pl = " | ".join([pl] + more_plural_hints(r.definition, pl)) if pl else pl
        for v in vs:
            e = lemmas.setdefault(v, dict(glosses=[], sources=[], orig=[], pl=[], gen=[]))
            if gl and gl not in e["glosses"]:
                e["glosses"].append(gl)
            if r.src not in e["sources"]:
                e["sources"].append(r.src)
            if str(r.lemma) not in e["orig"]:
                e["orig"].append(str(r.lemma))
            for key, val in (("pl", pl), ("gen", gen)):
                if val and val not in e[key]:
                    e[key].append(val)

    # hand-written additions (nouns/nouns_manual.tsv): action add = a new lemma (names, toponyms, words of the corpus that are not
    # in the dictionaries; tags = its plural suffixes, empty = no plural); action tag = more plural suffixes for a lemma of the dictionaries
    manual = NOUNS / "nouns_manual.tsv"
    n_add = n_tag = 0
    if manual.exists():
        with open(manual, encoding="utf-8", newline="") as f:
            for m in csv.DictReader(f, delimiter="\t"):
                lem, extra = m["lemma"].strip(), [t for t in m["tags"].replace(" ", "").split(",") if t]
                assert all(t in PL_TAGS.values() for t in extra), f"unknown plural tag in nouns_manual.tsv: {m}"
                if m["action"] == "add":
                    assert lem not in lemmas, f"nouns_manual.tsv: {lem} is already in the dictionaries (use the action tag)"
                    assert re.fullmatch(r"[а-яёIᴴ-]+", lem), f"nouns_manual.tsv: bad lemma {lem!r}"
                    lemmas[lem] = dict(glosses=[m["gloss"].strip()], sources=[m["source"].strip() or "manual"], orig=[lem], pl=[], gen=[], manual=extra)
                    n_add += 1
                elif m["action"] == "tag":
                    assert lem in lemmas, f"nouns_manual.tsv: {lem} is not in the dictionaries (use the action add)"
                    lemmas[lem].setdefault("manual", []).extend(extra)
                    n_tag += 1
                else:
                    raise ValueError(f"nouns_manual.tsv: unknown action {m['action']!r}")

    def gloss_of(e):
        g = [x for x in e["glosses"] if not x.startswith("см.")] or e["glosses"]
        return " | ".join(g[:3])

    NOUNS.mkdir(exist_ok=True)
    with open(NOUNS / "nouns_auto.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["lemma", "gloss", "sources", "orig", "pl_hint", "gen_hint"])
        for lem, e in lemmas.items():
            w.writerow([lem, gloss_of(e), "+".join(sorted(e["sources"])), " | ".join(e["orig"]), " | ".join(e["pl"]), " | ".join(e["gen"])])
    with open(NOUNS / "nouns_skipped.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["reason", "headword", "source", "gloss"])
        for row in sorted(set(skipped)):
            w.writerow(row)

    lex = OrderedDict((k, []) for k in ("NounH", "NounU"))
    review = []
    for lem, e in lemmas.items():
        tags, bad = plural_tags(" | ".join(e["pl"]))
        tags += [t for t in e.get("manual", []) if t not in tags]
        if lem.endswith("ав") and "al" in tags:
            tags = ["l" if t == "al" else t for t in tags]  # abazinav-type words: plural in -л (чачанав - чачанал)
        if lem.endswith("ав") and not tags:
            tags = ["l"]  # ethnonyms and the like in -ав without a (readable) hint: plural -л (чачанав - чачанал)
        if lem in L_EXTRA and "l" not in tags:
            tags.append("l")  # AA2019: вацци-л, йацци-л, ваша-л, йеши-л, макIи-л
        tags = list(dict.fromkeys(tags))
        if "l" in tags:  # the -л group: oblique stem in -щу- or -лълъи-
            tags += ["shu"] if lem in SHU_ONLY else ["lli"] if lem in LLI_ONLY else ["shu", "lli"]
        elif tags:  # the other nouns: thematic -а, -и or -у (unknown for the single noun)
            tags.append("th")
        if bad:
            review.append((lem, " | ".join(e["pl"]), " | ".join(bad)))
        if tags:
            lex["NounH"].append((f"{lem}:{lem}[{','.join(tags)}]", gloss_of(e)))
        else:
            lex["NounU"].append((f"{lem}:{lem}", gloss_of(e)))
    with open(NOUNS / "nouns_review.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["lemma", "plural_hint", "unread"])
        w.writerows(review)
    out = []
    for name, ents in lex.items():
        width = max(len(x) for x, _ in ents) + 2
        out += [f"LEXICON {name}", ""]
        out += [f"{x.ljust(width)}# {c}" if c else x for x, c in ents]
        out += ["", ""]
    lexicon = "\n".join(out)
    (NOUNS / "nouns_lexicon.lexd").write_text(lexicon, encoding="utf-8")
    ents = lex["NounH"] + lex["NounU"]
    cnt = defaultdict(int)
    for s in skipped:
        cnt[s[0]] += 1
    print(f"nouns_manual.tsv: {n_add} lemmas added, {n_tag} lemmas with more plural suffixes")
    print(f"{len(ents)} noun lemmas ({len(lex['NounH'])} with a plural hint, {len(lex['NounU'])} without); skipped headwords: {dict(cnt)}; unread hints: {len(review)}")


if __name__ == "__main__":
    main()
