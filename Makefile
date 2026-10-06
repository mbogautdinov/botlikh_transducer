# Botlikh morphological transducer: lexd + twol + HFST.
#
#   make            the three analyzers (bot_analyzer, bot_noclitics_analyzer, bot_allclitics_analyzer) as .hfstol
#   make test       the tests of the folder tests/
#   make lexicons   the generated lexicons (*_lexicon.lexd) again, from the dictionary and the hand-written tables
#   make clean      remove the compiled files
#
# A module can be built alone, for example: make bot_nouns_analyzer.hfstol

SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -c
.DELETE_ON_ERROR:
.SECONDARY:
.PHONY: all test lexicons clean

all: bot_analyzer.hfstol bot_noclitics_analyzer.hfstol bot_allclitics_analyzer.hfstol

# ---------------------------------------------------------------------------
# General rules
# ---------------------------------------------------------------------------

# the analyzer is the inverted generator
%_analyzer.hfst: %_generator.hfst
	hfst-invert $< -o $@

# optimized lookup format (for hfst-lookup and hfst-proc)
%.hfstol: %.hfst
	hfst-fst2fst -O $< -o $@

# two-level rules of a module
%_twol.hfst: %.twol
	hfst-twolc -q $< -o $@

# the hyphen of the lexical side (reduplication, compounds) is removed from the surface form
remove_hyphen.hfst: remove_hyphen.twol
	hfst-twolc -q $< -o $@

# ---------------------------------------------------------------------------
# Modules. The lexd source of a module is the hand-written patterns (*_formation.lexd)
# followed by the generated lexicon (*_lexicon.lexd).
# ---------------------------------------------------------------------------

bot_numerals_generator.hfst: numerals/numerals_formation.lexd numerals/numerals_lexicon.lexd numerals/numerals_twol.hfst remove_hyphen.hfst
	cat numerals/numerals_formation.lexd numerals/numerals_lexicon.lexd | lexd | hfst-txt2fst \
	| hfst-compose-intersect -1 - -2 numerals/numerals_twol.hfst \
	| hfst-compose-intersect -1 - -2 remove_hyphen.hfst | hfst-minimize -o $@

bot_adjectives_generator.hfst: adjectives/adjectives_formation.lexd adjectives/adjectives_lexicon.lexd adjectives/adjectives_twol.hfst remove_hyphen.hfst
	cat adjectives/adjectives_formation.lexd adjectives/adjectives_lexicon.lexd | lexd | hfst-txt2fst \
	| hfst-compose-intersect -1 - -2 adjectives/adjectives_twol.hfst \
	| hfst-compose-intersect -1 - -2 remove_hyphen.hfst | hfst-minimize -o $@

bot_nouns_generator.hfst: nouns/nouns_formation.lexd nouns/nouns_lexicon.lexd nouns/nouns_twol.hfst remove_hyphen.hfst
	cat nouns/nouns_formation.lexd nouns/nouns_lexicon.lexd | lexd | hfst-txt2fst \
	| hfst-compose-intersect -1 - -2 nouns/nouns_twol.hfst \
	| hfst-compose-intersect -1 - -2 remove_hyphen.hfst | hfst-minimize -o $@

# pronouns: a closed class, the stems are written in the same file as the patterns
bot_pronouns_words.hfst: pronouns/pronouns.lexd pronouns/pronouns_twol.hfst remove_hyphen.hfst
	lexd pronouns/pronouns.lexd | hfst-txt2fst \
	| hfst-compose-intersect -1 - -2 pronouns/pronouns_twol.hfst \
	| hfst-compose-intersect -1 - -2 remove_hyphen.hfst | hfst-minimize -o $@

# bare pronoun stems that occur only with a clitic (эн-кIвала)
bot_pronouns_bare_lex.hfst: pronouns/pronouns_bare.lexd
	lexd $< | hfst-txt2fst -o $@

# invariable words (adverbs, postpositions, particles, conjunctions, interjections, onomatopoeia), without the two-level rules
bot_invariables_lex.hfst: invariables/invariables_formation.lexd invariables/invariables_lexicon.lexd
	cat $^ | lexd | hfst-txt2fst | hfst-minimize -o $@

bot_invariables_words.hfst: bot_invariables_lex.hfst invariables/invariables_twol.hfst
	hfst-compose-intersect $^ | hfst-minimize -o $@

# ---------------------------------------------------------------------------
# Clitics. One clitic is an entry of the lexicon Clitic (=<tag>:form); the spelling rules of
# invariables/invariables.twol (palochka, nasal vowel) are applied to the chains of clitics.
#   bot_clitics_generator      0-3 clitics (after a word)
#   bot_clitics1_generator     1-3 clitics (after a bare pronoun stem)
#   bot_clitics01_generator    0-1 clitic  (after the copula)
#   bot_clitics_isolated       one clitic written as a separate word: the analysis has no stem (=<quot>)
# ---------------------------------------------------------------------------

bot_clitics.hfst: invariables/clitics_formation.lexd invariables/clitics_lexicon.lexd
	cat $^ | lexd | hfst-txt2fst | hfst-minimize -o $@

bot_clitics_generator.hfst: bot_clitics.hfst invariables/invariables_twol.hfst
	hfst-repeat -f 0 -t 3 $< | hfst-compose-intersect -1 - -2 invariables/invariables_twol.hfst | hfst-minimize -o $@

bot_clitics1_generator.hfst: bot_clitics.hfst invariables/invariables_twol.hfst
	hfst-repeat -f 1 -t 3 $< | hfst-compose-intersect -1 - -2 invariables/invariables_twol.hfst | hfst-minimize -o $@

bot_clitics01_generator.hfst: bot_clitics.hfst invariables/invariables_twol.hfst
	hfst-repeat -f 0 -t 1 $< | hfst-compose-intersect -1 - -2 invariables/invariables_twol.hfst | hfst-minimize -o $@

bot_clitics_isolated.hfst: bot_clitics.hfst invariables/invariables_twol.hfst
	hfst-compose-intersect $^ | hfst-minimize -o $@

# the two-level rules are applied to the invariable word together with its clitics
bot_invariables_generator.hfst: bot_invariables_lex.hfst bot_clitics.hfst invariables/invariables_twol.hfst
	hfst-repeat -f 0 -t 3 bot_clitics.hfst | hfst-concatenate -1 bot_invariables_lex.hfst -2 - \
	| hfst-compose-intersect -1 - -2 invariables/invariables_twol.hfst | hfst-minimize -o $@

bot_pronouns_generator.hfst: bot_pronouns_words.hfst bot_clitics_generator.hfst bot_pronouns_bare_lex.hfst bot_clitics1_generator.hfst
	hfst-concatenate bot_pronouns_words.hfst bot_clitics_generator.hfst -o bot_pronouns_a.tmp
	hfst-concatenate bot_pronouns_bare_lex.hfst bot_clitics1_generator.hfst -o bot_pronouns_b.tmp
	hfst-union bot_pronouns_a.tmp bot_pronouns_b.tmp | hfst-minimize -o $@
	rm -f bot_pronouns_a.tmp bot_pronouns_b.tmp

# ---------------------------------------------------------------------------
# The enclitic copula (invariables/copula_ida.lexd, copula_da.lexd). X_cop.hfst is the words of X.hfst
# with the copula, chosen by the end of the surface form of the word:
#   after a vowel or й      + да
#   after a consonant       + ида
#   final а of the word is dropped + ида
# One more clitic may follow the copula.
# ---------------------------------------------------------------------------
VOWEL_OR_J = а|е|и|о|у|э|ы|ю|я|й

cop_ends_v.hfst:
	echo '?* [$(VOWEL_OR_J)]' | hfst-regexp2fst -o $@

cop_ends_c.hfst:
	echo '?* \[$(VOWEL_OR_J)]' | hfst-regexp2fst -o $@

cop_drop_a.hfst:
	echo '?* а:0' | hfst-regexp2fst -o $@

bot_cop_ida.hfst: invariables/copula_ida.lexd
	lexd $< | hfst-txt2fst -o $@

bot_cop_da.hfst: invariables/copula_da.lexd
	lexd $< | hfst-txt2fst -o $@

%_cop.hfst: %.hfst cop_ends_v.hfst cop_ends_c.hfst cop_drop_a.hfst bot_cop_ida.hfst bot_cop_da.hfst bot_clitics01_generator.hfst
	hfst-compose -1 $< -2 cop_ends_v.hfst | hfst-concatenate -1 - -2 bot_cop_da.hfst -o $*_cop1.tmp
	hfst-compose -1 $< -2 cop_ends_c.hfst | hfst-concatenate -1 - -2 bot_cop_ida.hfst -o $*_cop2.tmp
	hfst-compose -1 $< -2 cop_drop_a.hfst | hfst-concatenate -1 - -2 bot_cop_ida.hfst -o $*_cop3.tmp
	hfst-union $*_cop1.tmp $*_cop2.tmp | hfst-union -1 - -2 $*_cop3.tmp | hfst-concatenate -1 - -2 bot_clitics01_generator.hfst | hfst-minimize -o $@
	rm -f $*_cop1.tmp $*_cop2.tmp $*_cop3.tmp

# ---------------------------------------------------------------------------
# The three versions of the transducer
#   bot_noclitics    the words of all modules, no clitics attached
#   bot_allclitics   0-3 clitics after a word of any module, then (optionally) the copula
#   bot              clitics and the copula after the invariable words and the pronouns only
# All versions analyse a clitic that is written as a separate word.
# ---------------------------------------------------------------------------

bot_words.hfst: bot_numerals_generator.hfst bot_invariables_words.hfst bot_adjectives_generator.hfst bot_pronouns_words.hfst bot_nouns_generator.hfst
	hfst-union bot_numerals_generator.hfst bot_invariables_words.hfst | hfst-union -1 - -2 bot_adjectives_generator.hfst \
	| hfst-union -1 - -2 bot_pronouns_words.hfst | hfst-union -1 - -2 bot_nouns_generator.hfst | hfst-minimize -o $@

bot_noclitics_generator.hfst: bot_words.hfst bot_clitics_isolated.hfst
	hfst-union $^ | hfst-minimize -o $@

bot_allclitics_hosts.hfst: bot_words.hfst bot_clitics_generator.hfst bot_pronouns_bare_lex.hfst bot_clitics1_generator.hfst
	hfst-concatenate bot_words.hfst bot_clitics_generator.hfst -o bot_allclitics_a.tmp
	hfst-concatenate bot_pronouns_bare_lex.hfst bot_clitics1_generator.hfst -o bot_allclitics_b.tmp
	hfst-union bot_allclitics_a.tmp bot_allclitics_b.tmp | hfst-minimize -o $@
	rm -f bot_allclitics_a.tmp bot_allclitics_b.tmp

bot_allclitics_generator.hfst: bot_allclitics_hosts.hfst bot_allclitics_hosts_cop.hfst bot_clitics_isolated.hfst
	hfst-union bot_allclitics_hosts.hfst bot_allclitics_hosts_cop.hfst | hfst-union -1 - -2 bot_clitics_isolated.hfst | hfst-minimize -o $@

bot_hosts.hfst: bot_invariables_generator.hfst bot_pronouns_generator.hfst
	hfst-union $^ | hfst-minimize -o $@

bot_generator.hfst: bot_numerals_generator.hfst bot_adjectives_generator.hfst bot_nouns_generator.hfst bot_hosts.hfst bot_hosts_cop.hfst bot_clitics_isolated.hfst
	hfst-union bot_numerals_generator.hfst bot_adjectives_generator.hfst | hfst-union -1 - -2 bot_nouns_generator.hfst \
	| hfst-union -1 - -2 bot_hosts.hfst | hfst-union -1 - -2 bot_hosts_cop.hfst | hfst-union -1 - -2 bot_clitics_isolated.hfst | hfst-minimize -o $@

# ---------------------------------------------------------------------------
# Generated lexicons. They are kept in the repository, so `make` needs only lexd and HFST;
# `make lexicons` (Python, pandas, openpyxl) writes them again.
# ---------------------------------------------------------------------------
lexicons:
	python3 scripts/split_by_pos.py
	python3 scripts/parse_invariables.py
	python3 scripts/parse_adjectives.py
	python3 scripts/build_numerals.py
	python3 scripts/build_invariables.py
	python3 scripts/build_adjectives.py
	python3 scripts/build_nouns.py

test: bot_allclitics_analyzer.hfstol
	python3 tests/run_tests.py --fst bot_allclitics_analyzer.hfstol

clean:
	rm -f *.hfst *.hfstol *.tmp */*_twol.hfst
