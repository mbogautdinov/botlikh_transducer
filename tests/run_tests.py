"""Run the tests of the transducer.

Usage (from the root of the repository, after `make`):

    python3 tests/run_tests.py                              # all tables of the folder tests/
    python3 tests/run_tests.py tests/nouns.tsv              # one table
    python3 tests/run_tests.py --fst bot_analyzer.hfstol    # another version of the transducer

Every table has four columns: form, analysis, expected, source.
    expected = yes    the analysis must be among the analyses of the form (other analyses may be present)
    expected = no     the analysis must not be among the analyses of the form
The script prints the number of passed tests for every table and the tests that failed; the exit code is 1 if a test failed.
"""
import argparse
import csv
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent


def lookup(fst, forms):
    """form -> set of analyses (hfst-lookup)"""
    forms = sorted(set(forms))
    out = subprocess.run(["hfst-lookup", "-q", str(fst)], input="\n".join(forms) + "\n",
                         capture_output=True, text=True, check=True).stdout
    analyses = defaultdict(set)
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and not parts[1].endswith("+?"):
            analyses[parts[0]].add(parts[1])
    return analyses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tables", nargs="*", help="test tables (default: tests/*.tsv)")
    ap.add_argument("--fst", default=str(ROOT / "bot_allclitics_analyzer.hfstol"))
    a = ap.parse_args()
    if not Path(a.fst).exists():
        sys.exit(f"{a.fst} is not found: run `make` first")

    tables = [Path(t) for t in a.tables] or sorted(TESTS.glob("*.tsv"))
    tests = {}
    for t in tables:
        with open(t, encoding="utf-8", newline="") as f:
            tests[t.name] = list(csv.DictReader(f, delimiter="\t"))
    analyses = lookup(a.fst, [r["form"] for rows in tests.values() for r in rows])

    failed_total = 0
    for name, rows in tests.items():
        failed = [r for r in rows if (r["analysis"] in analyses[r["form"]]) != (r["expected"] == "yes")]
        failed_total += len(failed)
        print(f"{name:20s} {len(rows) - len(failed)}/{len(rows)}")
        for r in failed:
            got = ", ".join(sorted(analyses[r["form"]])) or "no analysis"
            print(f"    FAILED  {r['form']}  expected {r['expected']}: {r['analysis']}  got: {got}")
    sys.exit(1 if failed_total else 0)


if __name__ == "__main__":
    main()
