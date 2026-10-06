"""Type the dictionary entries of the adjectives and write (1) the typed table and (2) the lexicon TSV for the lexd builder.

Usage (from the root of the repository):  python3 scripts/parse_adjectives.py [--dicts data/pos_dicts]

Input : data/pos_dicts/adjectives.xlsx
Output: data/pos_dicts/adjectives_typed.xlsx   original columns + adj_type, adj_subtype, adj_lemma, adj_stem, adj_evidence, adj_check, adj_gloss
        adjectives/adjectives_auto.tsv    one row per parsed alternative (consumed by build_adjectives.py)
        adjectives/adjectives_review.tsv  entries that need a human look

TYPES (column adj_type) -- they follow the inflectional behaviour, like the lexicon groups of zilo_transducer:
  no_class              no class marker, one invariable form; subtype plain | lli (relational -лълъи/-лъи)
  class_prefix          class marker at the beginning only:  в/й/б/р + ечIер   (вечIер, йечIер, бечIер, речIер)
  class_suffix          class marker at the end only:        stem + в/й/б/л   (subtype a: -о(в)/-ав, -ай, -аб, -ал;
                                                              xa: derived in -ха- (-хо(в), -хай, -хаб/-хоб, -хал);
                                                              u : derived in -ссу/-ццу (ссу, ссуй, ссуб, ссул))
  class_prefix_suffix   class markers at both ends:          в-ечIуха-в/о, й-ечIуха-й, б-ечIуха-б, р-ечIуха-л
  class_internal        class marker inside the word: цебда (цевда, цейда, цебда, целда); closed list
  cited_only            the paradigm cannot be derived safely, only the cited form is analysed
                        (subtype gen_relational | f_cited | plural_cited | unclear_b | hob_lja | other)
  mwe / redup           multiword entries and hyphenated compounds with several class markers: not compiled

Class markers (SA2012 grammar p.546-548): prefix/infix в I, й II, б III, р plural of humans; suffix в, й, б, л (plural of humans);
plural of non-humans = б (the same as III).  The class marker of the m form of an a-stem is realised as -о(в) (а+в > о).
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_invariables import norm, clean_surface, expand_optional, clean_gloss  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SUFLET = "вйбл"


def read_hint(definition: str):
    """Return (kind, note) from a parenthesis at the very beginning of the definition: '(-ай, -аб, -ал)', '(й-...-ай, б-...-аб, р-...-ал)'."""
    d = norm(definition)
    m = re.match(r"^\s*\(([^)]*)\)", d)
    if not m:
        return "", ""
    h = m.group(1).strip()
    if re.search(r"\bй-\.\.\.-ай|\bб-\.\.\.-аб|р-\.\.\.-ал", h):
        return "prefix_suffix", h
    if re.search(r"-(?:у|уй|ул)\b", h) and not re.search(r"-(?:аб|ай|ал|ав|о)\b", h):
        return "suffix_u", h
    if re.search(r"-(?:аб|ай|ал|ав|о|ов|й|б|л|в)\b", h) or re.search(r"-лъ", h):
        return "suffix", h
    if re.search(r"цевда|цейда", h):
        return "internal_ceb", h
    return "other", h


def analyze_alt(a: str, hint_kind: str):
    """Analyse one alternative of a lemma (already normalised, optional material expanded).
    Return dict(type, subtype, pref, suf, stem, cited, evidence, flags)."""
    r = dict(type="", subtype="", pref="", suf="", stem="", stem2="", cited="", evidence="", flags=[])
    if " " in a.strip():
        r.update(type="mwe", evidence="space")
        return r
    a = a.replace("\\", "")  # 'бидул\ав': the part after the backslash is not kept in inflected forms; keep the whole word
    # --- garbled prefix notation 'би/тI/и', 'б/ечI/ер' (OCR): prefix + stem
    m = re.match(r"^([вйбр])([^/=]{0,2})/([^/]+)/([^/]*)$", a)
    if m:
        a = m.group(1) + "/" + m.group(2) + m.group(3) + m.group(4)
        r["flags"].append("two slashes read as prefix")
    if len(re.findall(r"/", a)) >= 2 and not re.match(r"^[вйбр]/", a):
        r.update(type="cited_only", subtype="other", evidence="notation?", flags=["unparsed class notation (two slashes)"], cited=clean_surface(a))
        return r
    # --- class marker inside the word: 'ссе/битIаб', 'хху́да/вагьихов', 'гьи=в=далIи'
    m = re.match(r"^(.+?)=([вйбр])=(.+)$", a)
    mi = re.match(r"^(.{2,}?)/([вйбр])(.{2,})$", a)
    if m or mi:
        mm = m or mi
        part1, letter, rest = mm.group(1), mm.group(2), mm.group(3)
        if re.search(r"[=/]", part1 + rest):
            r.update(type="cited_only", subtype="other", evidence="notation?", flags=["unparsed class notation"], cited=clean_surface(a))
            return r
        suf, stem2, sk = "", rest, "none"
        if m is None:
            if re.search(r"ов$", rest):
                suf, stem2, sk = "в", rest[:-2] + "а", "o"
            elif re.search(r"аб$", rest):
                suf, stem2 = "б", rest[:-1]
            elif re.search(r"ав$", rest):
                suf, stem2 = "в", rest[:-1]
            elif re.search(r"о$", rest):
                suf, stem2 = "в", rest[:-1] + "а"
        r.update(type="class_infix", subtype="a" if suf else "none", pref=letter, suf=suf, stem=clean_surface(part1), stem2=clean_surface(stem2),
                 evidence="notation", cited=clean_surface(part1 + letter + rest))
        return r
    # --- class prefix
    pref = ""
    parts = re.split(r"-", a)
    pm = [bool(re.match(r"^[вйбр][=/]", p)) for p in parts]
    if sum(pm) > 1:
        r.update(type="redup", evidence="notation", flags=["several class markers"])
        return r
    m = re.match(r"^([вйбр])[=/](.*)$", a)
    if m:
        pref, a = m.group(1), m.group(2)
    elif any(pm):  # prefix in a later hyphen part
        r.update(type="redup", evidence="notation", flags=["class marker inside a hyphenated word"])
        return r
    r["pref"] = pref
    ev = "notation" if pref else ""
    # --- class suffix: explicit notation
    suf, stem, sufkind = "", a, ""
    m = re.match(r"^(.*?)[=/]а([вйблр])$", a)           # гучI/аб, агъаргъ=аб
    mov = re.match(r"^(.*?)[=/]ов$", a)                  # бужих/ов (o < a+в)
    m2 = re.match(r"^(.*?)[=/]о$", a)                    # балугъ=о (o < a+в)
    m3 = re.match(r"^(.*?)[=/]([вйблр])$", a)           # макваса/б, агьиха=б
    m4 = re.match(r"^(.*?)[=/]([вйбл])(.{1,4})$", a)  # …/л…: rare
    if m:
        stem, suf, sufkind = m.group(1) + "а", m.group(2), "notation"
    elif m2 or mov:
        stem, suf, sufkind = (m2 or mov).group(1) + "а", "в", "notation_o"
    elif m3:
        stem, suf, sufkind = m3.group(1), m3.group(2), "notation"
        if suf == "р":
            r["flags"].append("suffix р")
        if stem.endswith("о") and len(stem) > 2:     # зирзахо/б: the m form -хо(в) is a+в > о, the stem is -ха
            stem = stem[:-1] + "а"
            r["flags"].append("o-stem read as a-stem")
    elif re.search(r"[=/]", a):
        r.update(type="cited_only", subtype="other", evidence="notation?", flags=["unparsed class notation"], cited=clean_surface(a))
        return r
    else:
        # --- shape of the cited form
        b = a
        low = b
        if re.search(r"(?:луб|ралуб)$", low) and len(low) > 6:
            suf, stem, sufkind = "", b, "gen_rel"
        elif re.search(r"ссуб$|ццуб$", low):
            stem, suf, sufkind = b[:-1], "б", "shape_u"
        elif re.search(r"ссуй$|ццуй$", low):
            stem, suf, sufkind = b[:-1], "й", "shape_u"
        elif re.search(r"ссул$|ццул$", low):
            stem, suf, sufkind = b[:-1], "л", "shape_u"
        elif re.search(r"(?:ссу|ццу)$", low):
            stem, suf, sufkind = b, "в", "shape_u0"
        elif re.search(r"хоб$", low):
            stem, suf, sufkind = b[:-2] + "а", "б", "shape_xa"
        elif re.search(r"аб$", low):
            stem, suf, sufkind = b[:-1], "б", "shape"
        elif re.search(r"ав$", low):
            stem, suf, sufkind = b[:-1], "в", "shape"
        elif re.search(r"ов$", low):
            stem, suf, sufkind = b[:-2] + "а", "в", "shape_o"
        elif re.search(r"о$", low):
            stem, suf, sufkind = b[:-1] + "а", "в", "shape_o0"
        elif re.search(r"ай$", low):
            stem, suf, sufkind = b[:-1], "й", "shape_f"
        elif re.search(r"ал$", low):
            stem, suf, sufkind = b[:-1], "л", "shape_pl"
        elif re.search(r"(?:уб|иб|об)$", low):
            suf, stem, sufkind = "", b, "shape_b"
        else:
            suf, stem, sufkind = "", b, "none"
    # ---------------- decide the type
    if sufkind == "gen_rel":
        r.update(type="cited_only", subtype="gen_relational", stem=clean_surface(stem), cited=clean_surface(stem), evidence="shape")
        return r
    if sufkind == "shape_b":
        r.update(type="cited_only", subtype="unclear_b", stem=clean_surface(stem), cited=clean_surface(stem), evidence="shape")
        return r
    if sufkind == "shape_f" and not pref and hint_kind not in ("suffix", "prefix_suffix"):
        r.update(type="cited_only", subtype="f_cited", stem=clean_surface(a), cited=clean_surface(a), evidence="shape")
        return r
    if sufkind == "shape_pl" and not pref and hint_kind not in ("suffix", "prefix_suffix"):
        r.update(type="cited_only", subtype="plural_cited", stem=clean_surface(a), cited=clean_surface(a), evidence="shape")
        return r
    if not suf:
        if pref:
            r.update(type="class_prefix", stem=clean_surface(stem), evidence=ev or "notation")
        elif re.search(r"(?:лълъи|лъи)$", stem):
            r.update(type="no_class", subtype="lli", stem=clean_surface(stem), evidence="shape")
        else:
            r.update(type="no_class", subtype="plain", stem=clean_surface(stem), evidence="shape")
            if re.match(r"^б[аеиоу]", clean_surface(stem)):
                r["flags"].append("initial_b (class prefix not excluded)")
        r["cited"] = clean_surface(a if not pref else pref + a)
        return r
    # a class suffix is present
    stem_c = clean_surface(stem)
    cited_letter = suf
    st = "a"
    if sufkind in ("shape_u", "shape_u0"):
        st = "u"
    elif sufkind == "notation" and stem_c.endswith("у"):
        st = "u"
    elif sufkind == "notation" and re.search(r"(?:ссу|ццу)$", stem_c):
        st = "u"
    elif stem_c.endswith("ха") or sufkind == "shape_xa":
        st = "xa"
    elif not stem_c.endswith("а"):
        st = "other"
    t = "class_prefix_suffix" if pref else "class_suffix"
    if sufkind.startswith("notation"):
        ev = "notation"
    elif hint_kind in ("suffix", "suffix_u", "prefix_suffix"):
        ev = "hint"
    else:
        ev = "shape"
    if st == "other":
        r.update(type="cited_only", subtype="other", stem=stem_c, cited=clean_surface(a), evidence=ev, flags=["stem does not end in -а/-у"])
        return r
    r.update(type=t, subtype=st, suf=suf, stem=stem_c, evidence=ev, cited=clean_surface(a))
    if sufkind in ("shape_o0",) and not re.search(r"(?:хо|лъо|чIо|ихо|ссо)$", clean_surface(a)):
        r["flags"].append("guess_o")
    return r


def lemma_upper(r):
    """III-class form, as in SA2012 and zilo_transducer."""
    if r["type"] in ("class_prefix",):
        return "б" + r["stem"]
    if r["type"] == "class_prefix_suffix":
        return "б" + r["stem"] + ("б" if r["subtype"] != "u" else "б")
    if r["type"] == "class_suffix":
        return r["stem"] + "б"
    if r["type"] == "class_infix":
        return r["stem"] + "б" + r["stem2"] + ("б" if r["suf"] else "")
    return r["cited"] or r["stem"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dicts", default=str(ROOT / "data" / "pos_dicts"))
    ap.add_argument("--out", default=str(ROOT / "adjectives"))
    a = ap.parse_args()
    df = pd.read_excel(Path(a.dicts) / "adjectives.xlsx")
    out = Path(a.out)
    out.mkdir(exist_ok=True)

    # sibling evidence: the same remainder with different class letters in the prefix position
    first_pass = {}
    for raw in df["lemma"].astype(str):
        for alt in norm(raw).split("//"):
            alt = alt.strip().replace("=", "").replace("/", "")
            if re.match(r"^[вйбр][аеиоуы]", alt) and " " not in alt:
                first_pass.setdefault(alt[1:].lower(), set()).add(alt[0])

    rows, review, typed = [], [], []
    for _, row in df.iterrows():
        raw = str(row["lemma"])
        definition = str(row["definition"]) if pd.notna(row["definition"]) else ""
        gloss = clean_gloss(row["meaning_ru"]) if pd.notna(row["meaning_ru"]) else ""
        hint_kind, hint = read_hint(definition)
        alts = [x.strip() for x in norm(raw).split("//") if x.strip()]
        first = None
        for ai, alt in enumerate(alts):
            for opt in expand_optional(alt):
                r = analyze_alt(opt, hint_kind)
                r["plain"] = clean_surface(opt.replace("=", "").replace("/", "").replace("\\", ""))
                # prefix evidence without notation: siblings or the AA convention of citing the m form of prefixed participles
                if r["type"] in ("class_suffix", "no_class", "cited_only") and not r["pref"] and r["type"] != "mwe":
                    base = clean_surface(opt.replace("=", "").replace("/", ""))
                    if hint_kind == "prefix_suffix" and re.match(r"^[вйбр]", base):
                        r2 = analyze_alt(base[0] + "=" + opt, hint_kind) if False else None
                    if re.match(r"^[вйбр][аеиоуы]", base) and len(first_pass.get(base[1:], ())) >= 2 and r["type"] == "class_suffix":
                        r["pref"], r["type"] = base[0], "class_prefix_suffix"
                        r["stem"] = r["stem"][1:]
                        r["evidence"] += "+sibling"
                    elif hint_kind == "prefix_suffix" and re.match(r"^[вйбр]", base) and r["type"] == "class_suffix":
                        r["pref"], r["type"] = base[0], "class_prefix_suffix"
                        r["stem"] = r["stem"][1:]
                        r["evidence"] += "+hint"
                    elif r["type"] == "class_suffix" and base.startswith("в") and re.match(r"^в[аеиоу]", base) and r["subtype"] in ("a", "xa") \
                            and re.search(r"(?:о|ов|ав)$", base):
                        r["pref"], r["type"] = "в", "class_prefix_suffix"
                        r["stem"] = r["stem"][1:]
                        r["evidence"] += "+shape_prefix"
                        r["flags"].append("guess_prefix")
                if hint_kind == "internal_ceb" and r["type"] != "mwe":
                    r.update(type="class_internal", subtype="ceb", evidence="hint")
                    if r["plain"] != "цебда":
                        r.update(type="cited_only", subtype="other", flags=r["flags"] + ["цебда-compound: class forms not generated"], stem=r["plain"])
                if r["type"] in ("class_prefix_suffix", "class_suffix", "class_prefix") and hint_kind == "suffix_u" and r["subtype"] == "a":
                    r["flags"].append("hint says -у/-уй/-ул")
                status = "attested" if ai == 0 and opt == expand_optional(alt)[0] else "variant"
                r["status"] = status
                r["lemma"] = lemma_upper(r)
                if first is None:
                    first = r
                if r["type"] in ("mwe", "redup"):
                    rows.append(dict(r, gloss=gloss, source=row["source_dict"], id=row["id"], orig=raw, hint=hint))
                    continue
                rows.append(dict(r, gloss=gloss, source=row["source_dict"], id=row["id"], orig=raw, hint=hint))
                if r["flags"] and any(f in ("unparsed class notation", "suffix р", "several class markers") for f in r["flags"]):
                    review.append((r["type"], raw, row["source_dict"], "; ".join(r["flags"]), definition[:80]))
        if first is None:
            first = dict(type="", subtype="", stem="", lemma="", evidence="", flags=["no form"])
            review.append(("", raw, row["source_dict"], "no form", definition[:80]))
        typed.append(dict(adj_type=first["type"], adj_subtype=first["subtype"], adj_lemma=first["lemma"], adj_stem=first["stem"],
                          adj_evidence=first["evidence"], adj_check="; ".join(first["flags"]), adj_gloss=gloss, adj_hint=hint))

    # ---------------- typed table
    tdf = pd.concat([df.reset_index(drop=True), pd.DataFrame(typed)], axis=1)
    DESC = {
        ("no_class", "plain"): "нет классного показателя, одна неизменяемая форма (ирхха, гьирцIи, ххеххи); косвенные формы только как субстантивированные (-(а)лу-)",
        ("no_class", "lli"): "относительные прилагательные на -лълъи/-лъи (арсилъи 'денежный'); не изменяются по классам",
        ("class_prefix", ""): "классный показатель только в начале: в/й/б/р + основа (вечIер, йечIер, бечIер, речIер)",
        ("class_suffix", "a"): "классный показатель только в конце, основа на -а: -о(в)/-ав, -ай, -аб, -ал (маквасо(в), маквасай, маквасаб, маквасал)",
        ("class_suffix", "xa"): "то же, основа на -ха (причастные -хаб/-хо(в)); у п. рода есть -хаб и -хоб",
        ("class_suffix", "u"): "то же, основа на -у: производные на -ссу/-ццу (ишхъессу, аруссуй, бекьуссуб, -ссул)",
        ("class_prefix_suffix", "a"): "показатели и в начале, и в конце: в-ечIухо(в), й-ечIухай, б-ечIухаб, р-ечIухал",
        ("class_prefix_suffix", "xa"): "то же, основа на -ха",
        ("class_prefix_suffix", "u"): "то же, основа на -ссу/-ццу",
        ("class_infix", "a"): "показатель внутри слова (после первой части) и в конце: ссе-битIаб, хху́да-вагьихов",
        ("class_infix", "none"): "показатель внутри слова, суффикса нет: гьи=в=далIи",
        ("class_internal", "ceb"): "цебда: цевда, цейда, цебда, целда (как числительное цеб)",
        ("cited_only", "gen_relational"): "этнические прилагательные на -алуб (генитив мн. числа): парадигма не выводится, анализируется только цитатная форма",
        ("cited_only", "f_cited"): "цитируется форма II класса на -ай (чаще существительные: гIурусай 'русская')",
        ("cited_only", "plural_cited"): "цитируется форма мн. числа на -ал (чаще существительные: асатинал)",
        ("cited_only", "unclear_b"): "оканчивается на -иб/-уб/-об, тип неясен",
        ("cited_only", "other"): "запись не удалось разобрать (см. adj_check)",
        ("mwe", ""): "словосочетание: не компилируется",
        ("redup", ""): "редупликация/сложное слово с несколькими классными показателями: не компилируется",
    }
    summ = (tdf.groupby(["adj_type", "adj_subtype"]).size().reset_index(name="n_entries"))
    summ["description"] = [DESC.get((t, st), "") for t, st in zip(summ["adj_type"], summ["adj_subtype"])]
    ex = tdf.groupby(["adj_type", "adj_subtype"])["lemma"].apply(lambda x: ", ".join(x.astype(str).head(4))).reset_index(name="examples")
    summ = summ.merge(ex, on=["adj_type", "adj_subtype"])
    with pd.ExcelWriter(Path(a.dicts) / "adjectives_typed.xlsx") as xw:
        tdf.to_excel(xw, sheet_name="adjectives", index=False)
        summ.to_excel(xw, sheet_name="types", index=False)

    cols = ["type", "subtype", "lemma", "stem", "stem2", "plain", "pref", "suf", "cited", "status", "evidence", "flags", "gloss", "source", "id", "orig", "hint"]
    with open(out / "adjectives_auto.tsv", "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            r = dict(r)
            r["flags"] = "; ".join(r["flags"])
            f.write("\t".join(str(r.get(c, "")) for c in cols) + "\n")
    with open(out / "adjectives_review.tsv", "w", encoding="utf-8") as f:
        f.write("type\torig\tsource\treason\tdefinition\n")
        for x in review:
            f.write("\t".join(map(str, x)) + "\n")
    print(len(df), "entries,", len(rows), "alternatives,", len(review), "review items")
    print(tdf.groupby(["adj_type", "adj_subtype"]).size().to_string())


if __name__ == "__main__":
    main()
