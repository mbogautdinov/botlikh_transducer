"""Parse the dictionary entries of the invariable parts of speech into a lexicon TSV.

Input : data/pos_dicts/{adverbs,postpositions,particles,conjunctions,interjections,onomatopoeia}.xlsx
Output: invariables/invariables_auto.tsv   (one row per surface form; consumed by build_invariables.py)
        invariables/invariables_review.tsv (entries whose notation could not be interpreted safely)

Usage (from the root of the repository):  python3 scripts/parse_invariables.py [--dicts data/pos_dicts]

Notation handled:
  stress marks, length colon, macron           removed from the surface form (the original is kept in `orig`)
  X//Y//Z                                      alternative forms (status variant)
  form(да), инку(й)чIада                       optional material: forms with and without it
  б=aкьу, б/акьу                               class prefix (AA '=' / SA '/'): variants with в/й/б/р
  го/б/чIа                                     class infix: variants with в/й/б/л/р
  гьечIиссеасу/б, гучI/аб                      class suffix: variants with в/й/б/л/р
  см. X                                        form is a variant of the lemma X (same part of speech)
  суфф. / суффиксальная частица                bound particle -> goes to the clitic lexicon, not here
"""
import argparse
import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

FILES = {  # file -> (POS tag, default lexd lexicon name)
    "adverbs": "ADV",
    "postpositions": "POSTP",
    "particles": "PTCL",
    "conjunctions": "CONJ",
    "interjections": "INTJ",
    "onomatopoeia": "ONOM",
}
# SA2012 p.539/546: plural of humans = р (л in the suffix position), plural of non-humans = б (the same as III class).
# So: prefix and infix series в й б р, word-final suffix series в й б л.
PREFIX_CLASSES = [("в", "m"), ("й", "f"), ("б", "n"), ("р", "an.pl")]
INFIX_CLASSES = PREFIX_CLASSES
SUFFIX_CLASSES = [("в", "m"), ("й", "f"), ("б", "n"), ("л", "an.pl")]
CLASS_LETTERS = "вйблр"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s))
    for ch in ("́", "̀", "̄", "­"):
        s = s.replace(ch, "")
    s = unicodedata.normalize("NFC", s)
    s = s.translate(str.maketrans("aeopcxyiAEOPCXYTHKMB", "аеорсхуиАЕОРСХУТНКМВ"))  # Latin lookalikes from OCR (capital I is the palochka and stays)
    s = s.replace("Ӏ", "I").replace("ӏ", "I").replace("1", "I") if re.search(r"[а-яА-Я]1[а-яА-Я]", s) else s.replace("Ӏ", "I").replace("ӏ", "I")
    return s.strip()


def clean_surface(s: str) -> str:
    s = s.replace("I", "\ue000").lower().replace("\ue000", "I")  # palochka stays uppercase 'I'
    s = s.replace(":", "").replace("!", "").replace("?", "")
    s = re.sub(r"\s+", " ", s).strip(" -–—,;.")
    return s


def expand_optional(s: str):
    """'гучIа(да)' -> ['гучIа', 'гучIада']; handles several groups."""
    m = re.search(r"\(([^()]*)\)", s)
    if not m:
        return [s]
    pre, opt, post = s[: m.start()], m.group(1), s[m.end():]
    out = []
    for rest in expand_optional(post):
        out.append(pre + rest)
        out.append(pre + opt + rest)
    return out


def class_variants(form: str):
    """Return [(surface, class_tag)] or None when the form has no class notation. Raw (un-cleaned) form expected."""
    # prefix: б=екьару or б/екьару (possibly in several hyphen parts)
    if re.match(r"^[вйбр][=/]", form):
        marker = form[0]
        out = []
        for letter, tag in PREFIX_CLASSES:
            parts = form.split("-")
            res = []
            for i, p in enumerate(parts):
                if re.match(r"^[вйбр][=/]", p):
                    res.append(letter + p[2:])
                elif i > 0 and p.startswith(marker) and len(parts) > 1:
                    res.append(letter + p[1:])
                else:
                    res.append(p)
            out.append(("-".join(res), tag))
        return out
    # infix: го/б/чIа
    m = re.match(r"^(.*)/([вйблр])/(.*)$", form)
    if m:
        return [(m.group(1) + l + m.group(3), t) for l, t in INFIX_CLASSES]
    m = re.match(r"^(.+)/([вйблр])([^/]{2,})$", form)
    if m:
        return [(m.group(1) + l + m.group(3), t) for l, t in INFIX_CLASSES]
    # suffix: ...а/б  or  гучI/аб
    m = re.match(r"^(.*)/(.?)([вйблр])$", form)
    if m and len(m.group(2)) <= 1:
        return [(m.group(1) + m.group(2) + l, t) for l, t in SUFFIX_CLASSES]
    return None


def cited_form(form: str) -> str:
    """The form as cited in the dictionary, with the class notation resolved to the cited letter."""
    if re.match(r"^[вйбр][=/]", form):
        parts = form.split("-")
        return "-".join(p[0] + p[2:] if re.match(r"^[вйбр][=/]", p) else p for p in parts)
    m = re.match(r"^(.*)/([вйблр])/(.*)$", form)
    if m:
        return m.group(1) + m.group(2) + m.group(3)
    m = re.match(r"^(.+)/([вйблр])([^/]{2,})$", form)
    if m:
        return m.group(1) + m.group(2) + m.group(3)
    m = re.match(r"^(.*)/(.?)([вйблр])$", form)
    if m and len(m.group(2)) <= 1:
        return m.group(1) + m.group(2) + m.group(3)
    return form


def parse_entry(raw: str):
    """Yield (form, status, class_tag, flags) for one raw lemma string."""
    raw = norm(raw)
    flags = set()
    results = []
    # 'инла/инлала': a single slash between two long words = alternatives, not class notation
    raw = re.sub(r"(?<=\w)/(?=\w{4,}$)", "//", raw) if re.match(r"^[^/]{4,}/[^/]{4,}$", raw) else raw
    alts = [a for a in raw.split("//") if a.strip()]
    if not alts:
        return results
    for ai, alt in enumerate(alts):
        alt = alt.strip()
        base_status = "attested" if ai == 0 else "variant"
        if ai > 0 and len(re.sub(r"[^\w]", "", alt)) < 3 and len(alts[0]) > 4:
            flags.add("short_alternative")
            continue
        for opt_form in expand_optional(alt):
            status = base_status if opt_form == expand_optional(alt)[0] else "variant"
            cv = class_variants(opt_form)
            if cv:
                for surf, tag in cv:
                    s = clean_surface(surf)
                    if s:
                        results.append((s, "class_var" if status == "attested" else "class_var", tag, flags))
            else:
                s = clean_surface(opt_form)
                if s:
                    results.append((s, status, "", flags))
    return results


def lemma_of(raw):
    """Lemma = cited form of the first alternative, without optional material."""
    raw = norm(raw)
    raw = re.sub(r"(?<=\w)/(?=\w{4,}$)", "//", raw) if re.match(r"^[^/]{4,}/[^/]{4,}$", raw) else raw
    alts = [a.strip() for a in raw.split("//") if a.strip()]
    if not alts:
        return ""
    first = expand_optional(alts[0])[0]
    return clean_surface(cited_form(first))


def clean_gloss(g: str, limit: int = 70) -> str:
    """One-line Russian translation for the comment after '#': no tabs, no '#', no newlines."""
    g = re.sub(r"[\t\r\n#]+", " ", str(g or "")).replace("\u00ad", "")
    g = re.sub(r"\s+", " ", g).strip(" ;,")
    return g if len(g) <= limit else g[:limit].rsplit(" ", 1)[0] + "…"


def gloss_of(meaning_ru, definition: str) -> str:
    """meaning_ru (curated short translation) if present, otherwise the first sense(s) of the dictionary definition."""
    if meaning_ru is not None and str(meaning_ru).strip() not in ("", "nan"):
        return clean_gloss(meaning_ru)
    d = norm(definition or "")
    d = re.sub(r"^\s*\d?\s*//\s*\S+(?:\s*//\s*\S+)*", "", d)
    segs = [x.strip() for x in re.split(r";|\|\|\|", d) if x.strip()]
    keep = [x for i, x in enumerate(segs) if i == 0 or re.match(r"\d[.)]", x)][:3]
    out = []
    for x in keep:
        x = re.sub(r"^(?:\d[.)]\s*)+", "", x)
        x = re.sub(r"^(?:нареч\.?|межд\.?|союз|част(?:ица|\.)?(?:\s+вопросит\.|\s+вопр\.)?|вводн\.(?:\s*сл\.)?|послелог|\d[.)])\s*", "", x)
        if x:
            out.append(x)
    return clean_gloss("; ".join(out))


def def_variants(definition: str):
    """Variant headwords written at the start of the definition: '//ссе́а 1. нареч.', '// ГЬА́НДАРЕ нареч.', '//ччит возглас'."""
    d = norm(definition).replace("\u00ad", "")
    m = re.match(r"^\s*\d?\s*//\s*(.+?)(?=\s+(?:нареч|в знач|возглас|межд|числ|част|союз|мест|послелог|\d[.)]|1\))|$)", d)
    if not m:
        return []
    out = []
    for part in re.split(r"//|,", m.group(1)):
        part = re.sub(r"\([^)]*\)", "", part).strip()
        s = clean_surface(part)
        if s and " " not in s and len(s) > 1:
            out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dicts", default=str(ROOT / "data" / "pos_dicts"))
    ap.add_argument("--out", default=str(ROOT / "invariables"))
    a = ap.parse_args()
    dicts = Path(a.dicts)
    out_rows, review = [], []
    clitic_candidates = []
    glosses = {}
    for fname, pos in FILES.items():
        df = pd.read_excel(dicts / f"{fname}.xlsx")
        entries = []  # (id, raw, source, definition)
        for _, r in df.iterrows():
            entries.append((r["id"], str(r["lemma"]), r["source_dict"], str(r["definition"]) if pd.notna(r["definition"]) else ""))
            glosses[r["id"]] = gloss_of(r["meaning_ru"] if "meaning_ru" in df.columns and pd.notna(r["meaning_ru"]) else None, str(r["definition"]) if pd.notna(r["definition"]) else "")
        # first pass: lemma index for 'см.' redirects
        lemma_index = {}
        for _id, raw, src, de in entries:
            res = parse_entry(raw)
            if res:
                lemma_index.setdefault(lemma_of(raw), lemma_of(raw))
        seen = {}
        for _id, raw, src, de in entries:
            ndef = norm(de)
            low = ndef.replace('I', '\ue000').lower().replace('\ue000', 'I')
            # bound particles are clitics, not words
            if re.match(r"^(суфф\.|суффиксальная|ч?астица\s*-)", low) or raw.strip().startswith("-"):
                clitic_candidates.append((pos, raw, src, de[:80]))
                continue
            res = parse_entry(raw)
            if not res:
                review.append((pos, raw, src, "no surface form", de[:80]))
                continue
            lemma = lemma_of(raw)
            for v in def_variants(de):
                res.append((v, "variant", "", set()))
            if any("short_alternative" in fl for _, _, _, fl in res) or ("//" in raw and any(len(re.sub(r"[^\w]", "", a)) < 3 for a in norm(raw).split("//")[1:])):
                review.append((pos, raw, src, "very short alternative after // (suffix replacement?): only the first form is used", de[:80]))
            m = re.match(r"^(?:[\d.\s]*)?см\.?\s*([^\s,;.|]+(?: [^\s,;.|]+)?)", low)
            redirect = ""
            if m:
                target = clean_surface(norm(m.group(1)).replace("- ", "").replace("«", ""))
                cand = [k for k in lemma_index if k == target or k.replace("-", "") == target.replace("-", "")]
                if not cand:
                    import difflib
                    cand = difflib.get_close_matches(target, list(lemma_index), n=1, cutoff=0.88)
                if cand:
                    redirect = cand[0]
                else:
                    review.append((pos, raw, src, f"'см.' target not found: {target}", de[:80]))
            extra = []
            for surf, status, tag, fl in res:
                if "ᴴ" in surf:  # the sketch and the site write the nasal as н (вангьи) where the dictionaries have ᴴ (ваᴴгьи)
                    extra.append((surf.replace("ᴴ", "н"), "nasal_n", tag, fl))
            for surf, status, tag, fl in res + extra:
                upper = redirect or lemma
                st = "variant" if redirect and status == "attested" else status
                key = (pos, upper, surf, tag)
                if key in seen:
                    seen[key]["source"].add(src)
                    seen[key]["ids"].add(str(_id))
                    continue
                row = dict(pos=pos, upper=upper, lower=surf, class_tag=tag, status=st, source={src}, ids={str(_id)}, orig=raw, note="", gloss=glosses.get(_id, ""))
                seen[key] = row
                out_rows.append(row)
            if re.search(r"[A-HJ-Za-hj-z0-9&]", norm(raw)) or "  " in raw:
                review.append((pos, raw, src, "suspicious characters (OCR?)", de[:80]))
            if " " in lemma and not redirect:
                for r_ in out_rows[-len(res):]:
                    pass
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    cols = ["pos", "upper", "lower", "class_tag", "status", "source", "ids", "orig", "note", "gloss"]
    with open(out / "invariables_auto.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in out_rows:
            r = dict(r)
            r["source"] = "; ".join(sorted(r["source"]))
            r["ids"] = ",".join(sorted(r["ids"]))
            if " " in r["lower"]:
                r["note"] = (r["note"] + " mwe").strip()
            f.write("\t".join(str(r[c]) for c in cols) + "\n")
    with open(out / "invariables_review.tsv", "w", encoding="utf-8") as f:
        f.write("pos\torig\tsource\treason\tdefinition\n")
        for r in review:
            f.write("\t".join(map(str, r)) + "\n")
    with open(out / "clitic_candidates_from_dictionary.tsv", "w", encoding="utf-8") as f:
        f.write("pos_file\torig\tsource\tdefinition\n")
        for r in clitic_candidates:
            f.write("\t".join(map(str, r)) + "\n")
    print(f"{len(out_rows)} forms, {len(review)} review items, {len(clitic_candidates)} clitic candidates")
    by = {}
    for r in out_rows:
        by.setdefault(r["pos"], []).append(r)
    for k, v in by.items():
        print(k, len(v), "forms,", len({x['upper'] for x in v}), "lemmas")


if __name__ == "__main__":
    main()
