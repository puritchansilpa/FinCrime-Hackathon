# Open-source tools and libraries for a Python sanctions/PEP hit adjudication system (as of Nov 2026)

Notes on sourcing: PyPI versions, release dates and licences below were checked live against the PyPI JSON API (`https://pypi.org/pypi/<pkg>/json`) on 2026-11-21. Items marked **[docs-knowledge]** describe well-known public APIs of a library that I did not re-fetch in this session. They are cited to the project's repo/PyPI page and should be checked before they are relied on.

## 1. OpenSanctions ecosystem (yente, nomenklatura, followthemoney, rigour, fingerprints): how scoring works, licences

### Takeaway
OpenSanctions publishes an MIT-licensed stack that already implements most of a sanctions-hit scorer. `followthemoney` is the entity model, `rigour` does name, country and identifier normalisation, `nomenklatura` does entity resolution and contains the matchers, and `yente` serves them as a `/match` API on Elasticsearch/OpenSearch. Its matchers are transparent and feature-weighted. In `logic-v2` (the default "best" since 2025-12-01), the name score is the base, strong identifier matches add evidence, and differing country, DOB and gender subtract fixed penalties. A team can reuse these feature definitions and weights directly. The OpenSanctions *data* is free only for non-commercial use, while the code is MIT.

### Cited Findings
**Packages, versions, licences (PyPI, checked 2026-11-21)**
- yente 5.5.1 (2026-10-30, MIT); nomenklatura 4.18.0 (2026-11-16, MIT); followthemoney 4.11.3 (2026-11-07, MIT); rigour 2.6.2 (2026-11-07, MIT); fingerprints 1.3.1 (2025-08-01, MIT). All are actively released. — [PyPI yente](https://pypi.org/project/yente/), [PyPI nomenklatura](https://pypi.org/project/nomenklatura/), [PyPI followthemoney](https://pypi.org/project/followthemoney/), [PyPI rigour](https://pypi.org/project/rigour/), [PyPI fingerprints](https://pypi.org/project/fingerprints/)
- yente is an "open source data match-making API" for searching, retrieving and matching FollowTheMoney entities (sanctioned people, companies, vessels). It can also index custom watchlists or company registries, and it can run on-premises as a KYC appliance. It is async FastAPI Python, needs `YENTE_INDEX_URL` pointing at Elasticsearch or OpenSearch, and ships a Dockerfile, docker-compose files (including an OpenSearch one) and a Kubernetes example. The code is MIT. The README says commercial use "may require a data license for OpenSanctions data". — [GitHub yente](https://github.com/opensanctions/yente)
- nomenklatura is a framework and CLI for de-duplicating and linking FtM entities. Its core is a `Resolver`, a graph of judgements (same / different / undecided) between entity IDs, which uses connected components to choose a canonical ID and can infer transitive judgements. The workflow is `xref` (candidate generation via an in-memory blocking `Index`), then `dedupe` (interactive console UI for human judgements), then `apply` (writes merged output). State is kept in SQLite (`NOMENKLATURA_DB_URL`). The Python API exposes `Dataset`, `Store`, `blocker.Index` and `Resolver`. Licence MIT; about 2,148 commits and 273 stars. — [GitHub nomenklatura](https://github.com/opensanctions/nomenklatura)
- rigour consolidates the older OCCRP/Aleph libraries `languagecodes`, `pantomime` and `fingerprints` into data cleaning and validation for names, languages, territories/country codes, corporate and tax identifiers, addresses, text, URLs and dates. Licence MIT. — [GitHub rigour](https://github.com/opensanctions/rigour); [rigour docs](https://rigour.followthemoney.tech/)
- The rigour docs are organised into Identifiers, Names, Territories, Addresses, Languages, Text and Dates/time sections. The landing page does not list function names. — [rigour docs](https://rigour.followthemoney.tech/)

**Matching algorithms available in yente `/match` (from the OpenSanctions scoring docs)**
- `best` is an alias for the top algorithm, which has been `logic-v2` since 2025-12-01. `logic-v2` is deterministic: "fuzzy and culturally aware dictionary-based name matching", identifier rules (IMO, ISIN, LEI, OGRN, INN), and penalties for divergent country, DOB, gender or address. It is calibrated for threshold 0.7. `ofac` (added 2026-06-26) emulates OFAC Sanctions List Search: it takes the best Jaro-Winkler score across all query/candidate name pairs (whole names and tokens), then applies optional penalties. `logic-v1` is not recommended. `name-based` and `name-qualified` are deprecated and retire on 2027-01-18, after which they redirect to `ofac`. `regression-v1` is a logistic regression over many features. `regression-v2` produces much lower scores and uses a threshold of about 0.5. — [OpenSanctions scoring docs](https://www.opensanctions.org/docs/api/scoring/)
- `threshold` defaults to 0.7. The docs suggest 0.8–0.85 when tolerance for false positives is low. `limit` defaults to 5. A per-request `weights` object (0.0–1.0) overrides feature weights, and zero-weight features are not computed. `/match/sanctions` is for sanctions only, `/match/default` includes PEPs, and `?topics=` filters by risk tag. An `/algorithms` endpoint returns algorithm metadata. — [OpenSanctions scoring docs](https://www.opensanctions.org/docs/api/scoring/); [Tuning docs](https://www.opensanctions.org/docs/api/tuning/)

**logic-v2 feature weights (default)**
- Positive features: `name_match` 1.00; `address_entity_match` 0.98; `crypto_wallet_address` 0.98; `isin_security_match` 0.98; `lei_code_match`, `ogrn_code_match`, `vessel_imo_mmsi_match`, `inn_code_match`, `bic_code_match`, `uei_code_match`, `npi_code_match` 0.95 each; `identifier_match` (tax/registration ID) 0.85; `weak_alias_match` 0.80; `address_prop_match` 0.20; `address_match` 0.00 (off by default). — [OpenSanctions matcher docs](https://www.opensanctions.org/matcher/)
- Penalties: `country_mismatch` −0.20; `dob_year_disjoint` −0.15; `dob_day_disjoint` −0.25; `gender_mismatch` −0.20. — [OpenSanctions matcher docs](https://www.opensanctions.org/matcher/)
- Name-matcher config: `nm_number_mismatch` 0.3 (penalty when numbers in names differ); `nm_extra_query_name` 0.8 (weight of query name parts with no counterpart in the result); `nm_extra_result_name` 0.2 (weight of result name parts with no counterpart in the query); `nm_family_name_weight` 1.3 (family-name multiplier for persons); `nm_fuzzy_cutoff_factor` 1; `nm_name_property` null. — [OpenSanctions matcher docs](https://www.opensanctions.org/matcher/)

**ofac, logic-v1 and regression-v1 feature weights**
- `ofac`: `ofac_name_score` 1.00; `country_mismatch` −0.10; `dob_year_disjoint` −0.10; `dob_day_disjoint` −0.15; `gender_mismatch` −0.10; `orgid_disjoint` −0.10. `name-qualified` uses the same penalties with `jaro_name_parts` 0.5 and `soundex_name_parts` 0.5. `name-based` uses only the two name features. — [OpenSanctions matcher docs](https://www.opensanctions.org/matcher/)
- `logic-v1`: `name_literal_match` 1.00; `person_name_jaro_winkler` 0.80; `person_name_phonetic_match` 0.90; `name_fingerprint_levenshtein` 0.90 (non-person names after fingerprinting, e.g. "Limited" becomes "Ltd", then Damerau-Levenshtein); `name_metaphone_match` and `name_soundex_match` 0.00; identifier features as in logic-v2; `weak_alias_match` 0.80; `country_mismatch` −0.20; `last_name_mismatch` −0.20; `dob_year_disjoint` −0.15; `dob_day_disjoint` −0.20; `gender_mismatch` −0.20; `orgid_disjoint` −0.20; `numbers_mismatch` −0.10. — [OpenSanctions matcher docs](https://www.opensanctions.org/matcher/)
- `regression-v1` learned coefficients: `name_match` 0.91; `name_token_overlap` 0.75; `name_numbers` −0.14; `name_levenshtein` −0.11; `phone_match` 0.02; `email_match` 0.01; `identifier_match` 0.08; `dob_matches` 0.88; `dob_year_matches` 0.35; `dob_year_disjoint` −0.52; `first_name_match` −0.11; `family_name_match` 0.03; `birth_place` −0.07; `gender_mismatch` −0.17; `country_mismatch` −0.23; `org_identifier_match` 0.35; `address_match` 0.45; `address_numbers` 0.38. — [OpenSanctions matcher docs](https://www.opensanctions.org/matcher/)

**How logic-v2 matches names (blog)**
- Tokens are tagged with "symbols" from curated reference data: org types (e.g. "Stripe [ORGTYPE:LLC]", so "Stripe LLC" matches "Stripe, Limited Liability Corporation"), generic business words, given and family names, and countries. Tagged filler words become "soft stop words" with lower weight, and fuzzy matching is applied only to the distinctive core. In the post's example, full-string Levenshtein scores "Sparkles Business Corporation" vs "Sporks Business Corporation" at 89%, but the cores "Sparkles" vs "Sporks" score 50%. For persons, first names are compared only with first names and family names with family names, and middle initials can match middle names. Transliteration is applied only for language pairs where romanisation is reliable, and other scripts rely on symbols. Name reference data was mined from Wikidata (over 161,000 items, 1.16 million spellings) and is shipped in rigour. Results include narrative explanations (e.g. "First names match, last names are a fuzzy 0.67 match") meant to feed generative AI case management. — [OpenSanctions blog: Rosetta, not Roulette (logic-v2)](https://www.opensanctions.org/articles/2025-09-11-logic-v2)

**How the `ofac` matcher was reverse-engineered (blog)**
- OFAC's tool appears to use SimMetrics.NET. Its Jaro-Winkler always applies the prefix bonus, whereas the original paper and modern libraries such as rapidfuzz and jellyfish apply it only when Jaro > 0.7. An implementation that always applies the bonus reached about 96% score parity, against about 90% for an LLM-agent attempt. — [OpenSanctions blog: reverse-engineering OFAC](https://www.opensanctions.org/articles/2026-07-01-ofac-matcher/)

**Known matcher limitations and recommended inputs**
- Accuracy drops for non-Western scripts, and phonetic matching does not support non-alphabetic scripts. Misspelled legal forms ("Lymited") hurt matching. Nickname equivalents such as Alexander/Sasha are not in the built-in dictionaries. For better precision: set `schema` to Person or Organization, pass `firstName`/`lastName`, pass `birthDate` ("even a year or year/month substantially reduces false positives"), pass `registrationNumber`/`taxNumber` and `country`. — [Tuning docs](https://www.opensanctions.org/docs/api/tuning/)
- Third-party reuse: Marble built "Motiva", a Rust reimplementation of yente's matching. — [OpenSanctions blog: Marble](https://www.opensanctions.org/articles/2026-07-21-marble/)
- Other background posts: [logic-v1 announcement (2023)](https://www.opensanctions.org/articles/2023-09-18-scoring-rules), [new scoring modes (2023)](https://www.opensanctions.org/articles/2023-05-08-improved-scoring), [name matching in sanctions screening (2025)](https://www.opensanctions.org/articles/2025-06-24-name-matching), [deduplication approach (2021)](https://www.opensanctions.org/articles/2021-11-11-deduplication)

### Inferences
- The fastest credible hackathon path is to run yente locally (docker-compose plus OpenSearch) with a custom FtM watchlist, or to import the nomenklatura/yente matcher code in-process. Its per-feature output then serves as both score and explanation, and the logic-v2 weights are a defensible, citable starting point for a hand-built scorer.
- The weights encode a practical adjudication policy. A day-level DOB conflict (−0.25) counts against a match more than a year-level one (−0.15). A country conflict is −0.20. Strong unique identifiers (LEI, IMO, INN) count almost as much as a name match. Missing data is not penalised: the features fire only on *disjoint* values.
- Exact module paths inside nomenklatura (e.g. `nomenklatura.matching.logic_v2`) were not confirmed in this session. Check the repo tree before writing imports.

### Gaps
- I could not confirm the exact rigour function names (e.g. `rigour.names.tag_person_name`, `remove_org_types`, `rigour.text.ascii_text`, `rigour.territories`). The docs landing page does not list them, so check the Names and Text pages.
- The exact DOB logic (year vs day disjointness for partial dates or ranges) and the country-matching logic beyond the feature names were not documented on the pages fetched.
- I did not verify whether fingerprints (last release 2025-08) is now just a shim over rigour. The rigour README says it absorbed fingerprints.

## 2. Record linkage libraries (Splink, dedupe, Python Record Linkage Toolkit, Zingg, JedAI)

### Takeaway
Splink (MIT, v5.0.0 released 2026-09-28) is the strongest choice for linking a customer across several tables. It does unsupervised Fellegi-Sunter linkage on DuckDB, Spark or Postgres, links about 1M records in roughly a minute on a laptop, and is used by UK ONS and MoJ. dedupe is MIT but its last PyPI release was in 2024. recordlinkage is BSD but stale (2023). Zingg is AGPL and needs Spark. pyJedAI is Apache-2.0 and research-oriented.

### Cited Findings
- Splink does probabilistic record linkage based on Fellegi-Sunter "with customizations". Training is unsupervised (no labels needed), it supports term-frequency adjustments and user-defined fuzzy comparisons, and it runs on DuckDB, Spark or PostgreSQL. It links about 1M records on a laptop in around a minute and over 100M with big-data backends. Users include UK ONS, MoJ, MoD, UKHSA, NHS England, the Australian Bureau of Statistics, Destatis and UNHCR. It works best with multiple, weakly correlated, standardised columns and poorly with a single bag-of-words column. Splink 5 is released and Splink 4 docs are kept as legacy. — [Splink docs](https://moj-analytical-services.github.io/splink/index.html)
- PyPI: splink 5.0.0, uploaded 2026-09-28, MIT, Python ≥3.10. — [PyPI splink](https://pypi.org/project/splink/)
- Splink 5 migration notes (third-party gist, unverified): inputs must be registered via a database API instead of passing pandas DataFrames directly, pandas is optional, the output API changed (e.g. a DuckDB relation), and blocking analysis is faster, with comparison counts estimated from a sample by default. — [Gist: Splink 5 migration notes](https://gist.github.com/RobinL/c6d56a27d8f83c40b6b09643c0fa5d14)
- Splink 4-era API **[docs-knowledge]**: `SettingsCreator(link_type="link_only"|"dedupe_only"|"link_and_dedupe", comparisons=[...], blocking_rules_to_generate_predictions=[block_on("dob"), ...])`, `Linker(dfs, settings, db_api=DuckDBAPI())`, `linker.training.estimate_u_using_random_sampling()`, `linker.training.estimate_parameters_using_expectation_maximisation(...)`, `linker.inference.predict()`, `linker.clustering.cluster_pairwise_predictions_at_threshold()`. Comparison library includes `cl.NameComparison`, `cl.DateOfBirthComparison`, `cl.ExactMatch`, `cl.JaroWinklerAtThresholds`, `cl.LevenshteinAtThresholds`, `cl.PostcodeComparison`, `cl.EmailComparison`. These names may have changed in v5. — [Splink docs](https://moj-analytical-services.github.io/splink/index.html)
- dedupe: MIT, latest PyPI 3.0.3 (2024-08-15). The hosted Dedupe.io service shut down on 31 Jan 2023. The GitHub repo (about 4.5k stars) showed updates in July 2025, Snyk rates maintenance "Inactive", and there is an unofficial fork `dedupe-fork-eccovia` (Nov 2025). Its method is active learning of a classifier plus learned blocking predicates **[docs-knowledge]** (`dedupe.Dedupe(fields)`, `dedupe.Gazetteer` for matching messy records against a canonical list, `console_label`, `train`, `partition`). — [PyPI dedupe](https://pypi.org/project/dedupe/); [dedupeio GitHub org](https://github.com/orgs/dedupeio/repositories); [Dedupe.io](https://dedupe.io/); [Snyk advisor](https://snyk.io/advisor/python/dedupe)
- Python Record Linkage Toolkit (`recordlinkage`): latest 0.16 (2023-07-20), BSD-3-Clause from 0.12 onward (GPL-3 before that). **[docs-knowledge]** API: `recordlinkage.Index().block()/.sortedneighbourhood()`, `recordlinkage.Compare().string(method="jarowinkler", threshold=...)/.exact()/.date()`, and classifiers `ECMClassifier` (Fellegi-Sunter/EM), `LogisticRegressionClassifier`, `NaiveBayesClassifier`, `KMeansClassifier`, plus FEBRL toy datasets via `recordlinkage.datasets.load_febrl1..4`. — [PyPI recordlinkage](https://pypi.org/project/recordlinkage/); [Snyk recordlinkage](https://security.snyk.io/package/pip/recordlinkage)
- Zingg: AGPL-3.0, PyPI 0.7.0 (2026-08-10). It is Spark-based ML entity resolution with active-learning labelling and is described as "for humans and agents". AGPL can block use inside shipped commercial products. — [PyPI zingg](https://pypi.org/project/zingg/); [GitHub zingg](https://github.com/zinggAI/zingg); [Zingg LICENSE](https://github.com/zinggAI/zingg/blob/main/LICENSE)
- pyJedAI: Apache-2.0, PyPI 0.3.6 (2025-11-03). — [PyPI pyjedai](https://pypi.org/project/pyjedai/)

### Inferences
- For "resolve the customer across several tables", use Splink with `link_type="link_and_dedupe"` across the customer tables, blocking on DOB or name tokens. Its match weights (per-comparison log Bayes factors) are themselves an explanation.
- For "is the watchlist hit the customer", the dedupe Gazetteer pattern or an OpenSanctions-style rule scorer fits better than Splink, because the watchlist side has sparse, alias-heavy records.
- Splink 5 is recent (Sept 2026), so tutorials and LLM-generated code will often target v4. Pin `splink<5` or follow the v5 docs consistently.

### Gaps
- No primary source was fetched for pyJedAI internals or JedAI (Java) status.
- No official Splink 5 changelog was found. Only the PyPI release and a third-party gist.

## 3. Name/string and normalisation libraries

### Takeaway
Use rapidfuzz (MIT, fast C++) for edit distance and token-set scoring and jellyfish (MIT) for phonetic codes. For transliteration, prefer anyascii (ISC) over unidecode (GPL-2+). Use nameparser (LGPL) or probablepeople (MIT) to split names, cleanco (MIT) or rigour/fingerprints for legal-form stripping, pycountry (LGPL) for ISO country codes, dateparser (BSD) for free-text dates, and libpostal via `postal` (MIT, heavy native dependency) for addresses. abydos is GPL-3 and has not been released since 2020.

### Cited Findings
- Versions and licences (PyPI, checked 2026-11-21): rapidfuzz 3.14.6 (2026-08-30, MIT); jellyfish 1.3.0 (2026-10-16, MIT); unidecode 1.4.0 (2025-04-24, GPL-2.0+); anyascii 0.3.3 (2025-06-29, ISC); PyICU 2.17 (2026-10-23, MIT-style; needs the ICU C++ library); nameparser 3.1.0 (2026-11-17, LGPL-2.1+); probablepeople 0.5.6 (2024-10-29, MIT); cleanco 2.3 (2024-05-15, MIT); abydos 0.5.0 (2020-01-11, GPL-3+, unmaintained); postal (libpostal bindings) 1.1.11 (2025-10-29, MIT); pycountry 26.2.16 (2026-02-17, LGPL-2.1); dateparser 1.5.1 (2026-11-17, BSD-3). — [PyPI rapidfuzz](https://pypi.org/project/rapidfuzz/), [jellyfish](https://pypi.org/project/jellyfish/), [unidecode](https://pypi.org/project/Unidecode/), [anyascii](https://pypi.org/project/anyascii/), [PyICU](https://pypi.org/project/PyICU/), [nameparser](https://pypi.org/project/nameparser/), [probablepeople](https://pypi.org/project/probablepeople/), [cleanco](https://pypi.org/project/cleanco/), [abydos](https://pypi.org/project/abydos/), [postal](https://pypi.org/project/postal/), [pycountry](https://pypi.org/project/pycountry/), [dateparser](https://pypi.org/project/dateparser/)
- Jaro-Winkler subtlety: rapidfuzz and jellyfish apply the Winkler prefix bonus only when the Jaro score exceeds 0.7, as in the original paper. OFAC's tool appears not to. — [OpenSanctions blog: OFAC matcher](https://www.opensanctions.org/articles/2026-07-01-ofac-matcher/)
- Key APIs **[docs-knowledge]**:
  - rapidfuzz: `fuzz.ratio`, `fuzz.partial_ratio`, `fuzz.token_sort_ratio`, `fuzz.token_set_ratio`, `fuzz.WRatio`; `distance.JaroWinkler.normalized_similarity`, `distance.Levenshtein`, `distance.DamerauLevenshtein`; `process.extract` / `process.cdist` for vectorised many-to-many scoring.
  - jellyfish: `jaro_winkler_similarity`, `damerau_levenshtein_distance`, `soundex`, `metaphone`, `nysiis`, `match_rating_codex`.
  - anyascii: `anyascii(str)`. unidecode: `unidecode(str)`. PyICU: `icu.Transliterator.createInstance("Any-Latin; Latin-ASCII")`.
  - nameparser: `HumanName("Dr. Juan Q. Xavier de la Vega III").first/.middle/.last/.suffix/.title`.
  - probablepeople: `probablepeople.tag(str)` returns labelled components and a type of Person/Corporation/Household (CRF-based).
  - cleanco: `basename("Acme Ltd")`, plus legal-form-to-country classification helpers.
  - pycountry: `countries.lookup()`, `countries.search_fuzzy()`.
  - dateparser: `dateparser.parse()`, plus the `search.search_dates()` helper.
  - libpostal: `postal.parser.parse_address()`, `postal.expand.expand_address()`.

  — [rapidfuzz GitHub](https://github.com/rapidfuzz/RapidFuzz); [jellyfish GitHub](https://github.com/jamesturk/jellyfish); [nameparser GitHub](https://github.com/derek73/python-nameparser); [probablepeople GitHub](https://github.com/datamade/probablepeople); [cleanco GitHub](https://github.com/psolin/cleanco); [libpostal GitHub](https://github.com/openvenues/libpostal); [dateparser GitHub](https://github.com/scrapinghub/dateparser)
- Separately, a `phonetics` package (1.0.5) has not been released since 2018. — [PyPI phonetics](https://pypi.org/project/phonetics/)

### Inferences
- Licence hygiene: unidecode (GPL), abydos (GPL) and nameparser/pycountry (LGPL) are fine for a hackathon, but GPL ones should be avoided in a product. anyascii and rigour are permissive alternatives.
- libpostal needs about 2GB of model data and a C build (awkward on Windows). For a hackathon, rigour's address normalisation or simple rapidfuzz token matching on addresses is cheaper.
- rigour already covers much of what nameparser, cleanco, pycountry and unidecode do, using sanctions-specific reference data. Prefer it if the OpenSanctions stack is adopted.

### Gaps
- The rapidfuzz/jellyfish function names above are from documentation knowledge and were not re-fetched.
- I did not verify whether `postal` wheels exist for Windows / Python 3.12+.

## 4. NER/extraction and LLM structured-output frameworks

### Takeaway
spaCy (MIT, 3.8.18) and GLiNER (Apache-2.0, 0.2.30, zero-shot labels such as "person", "date of birth" and "passport number") are actively maintained for pulling entities out of free-text watchlist remarks or adverse media. Flair (MIT) last released in Feb 2025. For LLM adjudication with a typed verdict, Instructor (MIT, 1.17.0), PydanticAI (MIT) and Outlines (Apache-2.0, constrained decoding for local models) are the current options.

### Cited Findings
- spaCy 3.8.18 (2026-10-26, MIT); GLiNER 0.2.30 (2026-10-31, Apache-2.0); Flair 0.15.1 (2025-02-05, MIT; slower release cadence); Instructor 1.17.0 (2026-09-09, MIT); pydantic-ai 2.71.0 (2026-11-19, MIT); Outlines 1.3.3 (2026-08-06, Apache-2.0). — [PyPI spacy](https://pypi.org/project/spacy/), [gliner](https://pypi.org/project/gliner/), [flair](https://pypi.org/project/flair/), [instructor](https://pypi.org/project/instructor/), [pydantic-ai](https://pypi.org/project/pydantic-ai/), [outlines](https://pypi.org/project/outlines/)
- Key APIs **[docs-knowledge]**:
  - GLiNER: `GLiNER.from_pretrained("urchade/gliner_multi-v2.1")` then `model.predict_entities(text, labels=[...], threshold=0.5)`, for arbitrary zero-shot entity types.
  - Instructor: `instructor.from_provider(...)` / `instructor.from_openai(client)` with `response_model=PydanticModel`, with automatic validation retries.
  - PydanticAI: `Agent(model, output_type=Verdict)`.
  - Outlines: grammar/JSON-schema constrained generation for local HF/vLLM models.

  — [GLiNER GitHub](https://github.com/urchade/GLiNER); [Instructor GitHub](https://github.com/instructor-ai/instructor); [PydanticAI docs](https://ai.pydantic.dev/); [Outlines GitHub](https://github.com/dottxt-ai/outlines)
- LLM vs rule matching on sanctions pairs: on OpenSanctions Pairs, the production rule/regression matcher (nomenklatura RegressionV1) scored F1 91.3%, GPT-4o 99.0%, and locally deployable DeepSeek-R1-Distill-Qwen-14B 98.2% (zero/few-shot, with and without MIPROv2 prompt optimisation). Rules tend to over-match, while LLMs struggle with cross-script transliteration. — [arXiv 2603.11051](https://arxiv.org/abs/2603.11051)

### Inferences
- A strong hackathon design is a hybrid. A cheap deterministic scorer (logic-v2-style features) auto-clears clear non-matches and explains itself. An LLM with a Pydantic `Verdict{decision, confidence, evidence_for, evidence_against}` schema then adjudicates the ambiguous band, given the feature breakdown as context. This matches the paper's finding that the two approaches fail in complementary ways.
- Because LLMs are weak on cross-script names, transliterate deterministically first (rigour/anyascii/ICU) and pass both the original and romanised forms to the model.

### Gaps
- No head-to-head benchmark of GLiNER vs spaCy on watchlist remarks text was found.

## 5. Public datasets/benchmarks for name or sanctions matching

### Takeaway
The main public benchmark is OpenSanctions Pairs: about 755k expert-labelled entity pairs from 293 sources, with a 2026 arXiv paper and NeurIPS 2026 poster. It is free for non-commercial use. The FEBRL synthetic sets shipped with `recordlinkage` are a lightweight person-record linkage benchmark.

### Cited Findings
- OpenSanctions matcher training data: about 760,000 manual judgements (Dec 2025) made while de-duplicating the OpenSanctions database. Each row is two entities plus a label (positive / negative / unsure). The grouped file requires a data delivery token, with monthly snapshots. The older flat `pairs.json` is superseded and no longer updated. Matcher-generated judgements are excluded. Free for non-commercial use, and businesses need a data licence. — [OpenSanctions pairs docs](https://www.opensanctions.org/docs/opensource/pairs)
- Paper: "OpenSanctions Pairs: Large-Scale Entity Matching with LLMs" (Smith, Sesodia, Lindenberg, Schroeder de Witt; v1 Feb 2026, v2 Aug 2026). 755,540 pairs, over 1M entities, 293 source datasets, Latin, Cyrillic and Arabic scripts. Baseline results are those in section 4. The authors argue pairwise matching is near a practical ceiling and future work should target blocking, clustering and uncertainty-aware review. — [arXiv 2603.11051](https://arxiv.org/abs/2603.11051); [NeurIPS 2026 poster](https://neurips.cc/virtual/2026/poster/139718)
- Conflict: the arXiv abstract says 45 jurisdictions, while one search snippet of the HTML version said 31 countries. Prefer the abstract (45). — [arXiv 2603.11051](https://arxiv.org/abs/2603.11051)
- FEBRL synthetic person datasets ship with recordlinkage (`load_febrl1`–`load_febrl4`) **[docs-knowledge]**. — [PyPI recordlinkage](https://pypi.org/project/recordlinkage/)

### Inferences
- For hackathon evaluation, sample OpenSanctions Pairs Person rows (non-commercial use) to tune thresholds, and complement it with synthetic customer/watchlist pairs perturbed by typo, transliteration, DOB-partial and country-conflict rules.

### Gaps
- Kaggle or other academic sanctions-name datasets were not researched within the tool budget. I found no verified, widely used public sanctions-screening benchmark other than OpenSanctions Pairs.
- The licence and download mechanics for the paper's released split (as distinct from the token-gated grouped file) were not confirmed.
