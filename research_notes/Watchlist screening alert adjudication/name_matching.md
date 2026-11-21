# Name Matching Techniques for Sanctions/PEP/Watchlist Screening and Person-Name Record Linkage

Research date: 2026-11-21. About 20 tool calls. Primary sources were favoured. The Christen (2006) figures were taken from the full text of the ANU technical report, extracted locally from the PDF. Several vendor and neural-method claims could only be checked at abstract or snippet level; these are flagged.

## Q1. Phonetic algorithms (Soundex, Metaphone/Double Metaphone, NYSIIS, Beider-Morse, Daitch-Mokotoff): strengths and weaknesses, comparative evaluations

### Takeaway
In the main independent comparison (Christen 2006), phonetic encoding followed by an exact code comparison did much worse than string-similarity ("pattern matching") methods. Average F-measures were about 0.28-0.62 for phonetic methods against up to about 0.92 for pattern matching. Christen explicitly recommends not using phonetic codes as the sole matcher; their value is as a cheap blocking or candidate-generation step. Beider-Morse and Daitch-Mokotoff were built to cut false positives on non-Anglo (Slavic, Germanic, Yiddish) surnames. The evidence for them comes mostly from their own authors.

### Cited Findings
- Christen (2006) compared phonetic encodings (Soundex, Phonex, Phonix, NYSIIS, Double Metaphone, Fuzzy Soundex) with pattern-matching methods on four real datasets: Midwives given names (15,233 pairs), Midwives surnames (14,180 pairs), Midwives full names (36,614 pairs), and COMPLETE surnames (8,942 pairs). Each dataset was balanced with random non-match pairs. — [Christen, TR-CS-06-02 / ICDM Workshops 2006](https://users.cecs.anu.edu.au/~Peter.Christen/publications/tr-cs-06-02.pdf)
- Average F-measures (averaged over all thresholds) across the four datasets, from Table 4: Soundex .341-.485; Phonex .369-.579; Phonix .330-.617; NYSIIS .275-.351; Double Metaphone .304-.410; Fuzzy Soundex .311-.396. Pattern matching scored higher: Levenshtein .513-.737; Damerau-Levenshtein .517-.739; Jaro .601-.853; Winkler .588-.891; Smith-Waterman .579-.889; LCS-2 .514-.915. — [Christen 2006](https://users.cecs.anu.edu.au/~Peter.Christen/publications/tr-cs-06-02.pdf)
- Christen states that "Pattern matching clearly outperform phonetic encoding techniques". The simple Phonex did better than the more complex Phonix and Double Metaphone. — [Christen 2006](https://users.cecs.anu.edu.au/~Peter.Christen/publications/tr-cs-06-02.pdf)
- Christen's Recommendation 3: phonetic encoding followed by exact comparison of codes "should not be used". He describes phonetic codes as usable for blocking or filtering before a more expensive pattern matcher. — [Christen 2006](https://users.cecs.anu.edu.au/~Peter.Christen/publications/tr-cs-06-02.pdf)
- Timing (Table 6): phonetic encodings are much faster, because they are O(|s|). Phonix is the slowest phonetic method, about 10x the others. Among pattern matchers, Jaro and Winkler are fast (about 0.07-0.28 ms per pair). Permuted Winkler, Editex and SAPS are slower (up to about 2.8 ms). — [Christen 2006](https://users.cecs.anu.edu.au/~Peter.Christen/publications/tr-cs-06-02.pdf)
- Beider-Morse Phonetic Matching (BMPM) reports false-positive rates for the surname "Washington": over 99% of matches under American Soundex were false, 67% under Daitch-Mokotoff, and 25% under BMPM. This is the authors' own evaluation. — [Beider & Morse, stevemorse.org](https://stevemorse.org/phonetics/bmpm2.pdf); [BMPM paper](https://stevemorse.org/phonetics/bmpm.pdf)
- BMPM's stated aim is "a significantly smaller number of false positives" without a considerable rise in false negatives. Wikipedia describes the trade-off as fewer false positives at the expense of some false negatives compared with Daitch-Mokotoff. — [stevemorse.org BMPM](https://stevemorse.org/phonetics/bmpm.pdf); [Wikipedia: Daitch-Mokotoff Soundex](https://en.wikipedia.org/wiki/Daitch%E2%80%93Mokotoff_Soundex)
- Apache Solr's documentation says Beider-Morse does not produce the large volume of false hits that Soundex does. This is vendor documentation with no test data. — [Apache Solr Phonetic Matching](https://solr.apache.org/guide/8_6/phonetic-matching.html)
- OFAC's own search tool uses Soundex (phonetic) together with Jaro-Winkler on name parts (see Q6). — [OFAC FAQ 249](https://ofac.treasury.gov/faqs/249)

### Inferences
- In a screening engine, phonetic keys suit recall-oriented candidate retrieval (blocking/indexing), not adjudication. Using Soundex on its own as a match decision would generate many false positives (cf. the >99% figure for "Washington").
- English-centric phonetic codes (Soundex, NYSIIS, Metaphone) build in English orthography assumptions. BMPM and Daitch-Mokotoff target Eastern European and Jewish surnames. None of them handles Arabic or Chinese romanisation variation by design.

### Gaps
- I found no independent peer-reviewed head-to-head of BMPM vs Daitch-Mokotoff vs Double Metaphone on a shared multicultural name set. The BMPM figures are self-reported.
- A column-to-dataset mapping problem affected my PDF text extraction of Christen's Table 4. Per-algorithm figures are therefore given as ranges across the four datasets, not per dataset.

## Q2. String similarity (Levenshtein, Damerau, Jaro-Winkler, token-set/sort, Monge-Elkan, TF-IDF n-grams): comparative studies

### Takeaway
No metric wins everywhere (Christen 2006). Jaro and Jaro-Winkler are consistently strong and fast for parsed single name fields. LCS and permutation-aware variants suit unparsed full names with swapped tokens. For multi-token entity names, Cohen, Ravikumar & Fienberg (2003) found that a hybrid of TF-IDF token weighting with Jaro-Winkler inner similarity ("SoftTFIDF") did best on average. Threshold choice matters as much as metric choice.

### Cited Findings
- Christen 2006 found "no single best technique". Jaro (.601-.853) and Winkler (.588-.891) did well across all four datasets. On parsed fields, LCS-2 reached .915 and Smith-Waterman .889. — [Christen 2006](https://users.cecs.anu.edu.au/~Peter.Christen/publications/tr-cs-06-02.pdf)
- Christen's recommendations:
  - (4) For names parsed into separate fields, Jaro and Winkler work well for both given names and surnames, as do uni- and bigrams.
  - (5) Longest common substring suits unparsed names that may contain swapped words.
  - (6) The Overlap coefficient beats Dice, which beats Jaccard.
  - (7) The Winkler prefix boost can be applied to any technique. Table 5 shows it can give "almost 20%" improvement.
  - (8) Small threshold changes can cause "dramatic drops" in quality, and optimal thresholds vary by dataset; without labelled data a good threshold is hard to find.
  - (9) Use linear-time methods (q-grams, Jaro, Winkler) when speed matters, or filter with bag distance first.
  - If DOB or address data is available, use full record-linkage methods rather than name matching alone.
  — [Christen 2006](https://users.cecs.anu.edu.au/~Peter.Christen/publications/tr-cs-06-02.pdf)
- Edit-distance spread among true matches is wide. In one Christen dataset, 43.5% of matched pairs differ by 6-10 edits. This explains why a pure Levenshtein threshold misses many true variants. — [Christen 2006, Table 3](https://users.cecs.anu.edu.au/~Peter.Christen/publications/tr-cs-06-02.pdf)
- Winkler's modification raises the Jaro score for up to four agreeing initial characters. — [Christen 2006](https://users.cecs.anu.edu.au/~Peter.Christen/publications/tr-cs-06-02.pdf); [NIST DADS Jaro-Winkler](https://xlinux.nist.gov/dads/HTML/jaroWinkler.html)
- Cohen, Ravikumar & Fienberg (IJCAI-03 IIWeb workshop, 2003) compared edit-distance metrics (including Monge-Elkan, an affine-gap Smith-Waterman variant), fast heuristic comparators (Jaro, Jaro-Winkler), token-based metrics (TF-IDF, Jaccard) and hybrids. The best performer on average was a hybrid combining TF-IDF weighting with Jaro-Winkler ("SoftTFIDF"). They note that Jaro and Jaro-Winkler seem intended mainly for short strings such as personal surnames. — [Cohen et al. 2003 (PDF)](https://www.cs.utexas.edu/~ai-lab/pubs/kdd03.pdf); [UW mirror](https://courses.cs.washington.edu/courses/cse590q/04au/papers/Cohen03.pdf)
- A 2023 company-name disambiguation paper reports that among non-learning baselines (Jaro, Jaro-Winkler, Levenshtein), Jaro-Winkler gave the best results. — [arXiv 2303.05391](https://arxiv.org/pdf/2303.05391v1)
- OpenSanctions' worked example of whole-string Levenshtein inflating similarity on organisation names: "Sparkles Business Corporation" vs "Sporks Business Corporation" scores 89%. After generic tokens are removed, "Sparkles" vs "Sporks" scores 50%. — [OpenSanctions logic-v2 (2025)](https://www.opensanctions.org/articles/2025-09-11-logic-v2)

### Inferences
- For adjudication, compare tokens or name parts (token-level alignment, Monge-Elkan / SoftTFIDF style) with a Jaro-Winkler inner metric, and weight tokens by rarity (IDF). Whole-string scores over-reward shared common tokens ("Mohammed", "Ali", "Trading", "Ltd").
- Token-set/token-sort ratios (fuzzywuzzy/rapidfuzz style) work in practice for reordering. I found no formal comparative evaluation of them in this pass.

### Gaps
- I did not retrieve Cohen et al.'s per-dataset table, so there are no exact Monge-Elkan vs SoftTFIDF numbers. Christen's 2012 book "Data Matching" was not accessed.

## Q3. Cross-cultural and transliteration issues; transliteration-aware matching (Rosette, IBM GNR, academic)

### Takeaway
Cultural structure (name order, multi-part Arabic names, double Hispanic surnames, logographic Chinese) and inconsistent romanisation are the main sources of both misses and false positives. Commercial engines (Babel Street Rosette, IBM Global Name Recognition) address this with culture classification, per-culture variant generation, name-order permutation and statistical name corpora. The academic evidence is narrower, with some strong results on specific script pairs (e.g. MITRE Roman-Chinese, F about 96%).

### Cited Findings
- Writing systems lose information differently. Abjads (Arabic, Hebrew) often omit vowels. Chinese logographic names (e.g. 杨柳桦樱 → "Liuhuaying Yang") lose information when romanised. One person may appear as "Mohammed Al-Fulan", "Mo Alfolan" and "Mike Fuller" after anglicisation. — [OpenSanctions, "More than a Technical Problem" (2025)](https://www.opensanctions.org/articles/2025-06-24-name-matching)
- OpenSanctions argues against a single canonical name form, since entities have many equally valid names. Screening often has only a name and perhaps a country, so vague names (e.g. "ISIS") produce many false positives. — [OpenSanctions 2025](https://www.opensanctions.org/articles/2025-06-24-name-matching)
- OpenSanctions logic-v2 (2025) applies transliteration only for script pairs where romanisation is reliable, and keeps other scripts native. Cross-script matching relies on "symbols" built from over 161,000 Wikidata given/family-name items with about 1.16 million spellings. First names are compared only to first names and family names only to family names, and middle initials can match middle names. — [OpenSanctions logic-v2](https://www.opensanctions.org/articles/2025-09-11-logic-v2)
- East Asian (also Hungarian, Sri Lankan) names put the surname first. When rendered in English the order is "sometimes (but not always!)" reversed. — [Industry name-matching paper (Microsoft-hosted)](https://query.prod.cms.rt.microsoft.com/cms/api/am/binary/RW10SDG)
- MITRE reports an F-score of 96% for deciding whether a Chinese-script name and a Roman-script name match. — [MITRE, Name Matching Between Roman and Chinese Scripts](https://www.mitre.org/news-insights/publication/name-matching-between-roman-and-chinese-scripts)
- IBM Global Name Recognition parses a full name, identifies possible word-order variations and shortened forms, and recognises name variants from multiple cultures. It uses a statistical corpus to identify "typical" vs "distinctive" name patterns per culture and returns ranked results. IBM documents that variants arise from component order and from transliteration between writing systems. — [IBM Advanced GNR paper](https://public.dhe.ibm.com/software/data/mdm/pdf/advancedgnr.pdf); [IBM docs: Name variants](https://www.ibm.com/docs/SSEV5M_7.0.0/analyzing/topics/name_variants.html)
- Rosette Name Indexer (now Babel Street) uses a patented two-pass process (fast candidate retrieval, then a finer re-scoring) for fuzzy matching of names, addresses and dates across languages. Its methods are described as common key, edit distance, list, and statistical similarity, with support for about 40 languages including Arabic, Chinese, Farsi, Pashto, Urdu, Korean and Japanese. Press coverage (2013) frames the problem as finding "Abdul Rasheed" when searching "Abdul Rashid". — [Babel Street: Understanding Rosette Name Indexer](https://www.babelstreet.com/landing/understanding-rosette-name-indexer); [Route Fifty/GCN 2013](https://www.route-fifty.com/digital-government/2013/09/watch-lists-how-do-you-find-abdul-rasheed-when-youre-looking-for-abdul-rashid/281997)
- Arabic: El-Shishtawy (2013) proposes a hybrid token- and character-level matcher (Levenshtein extended to token level, with token weighting by position and frequency). It targets typos, omitted or inserted middle-name components (common in multi-part Arabic names), omitted non-significant popular components, and writing-style variation. The abstract claims improvement over the best classical baselines on "a large Arabic dataset" but gives no numbers. — [arXiv 1309.5657](https://arxiv.org/abs/1309.5657)
- JRC-Names-Retrieval (Blair & Bar, LREC-COLING 2024) is a standardised multi-script name-search benchmark built on the EU JRC-Names resource (Steinberger et al. 2011). — [ACL Anthology 2024.lrec-main.838](https://aclanthology.org/2024.lrec-main.838.pdf)
- Blissett & Ji (2019) train a zero-shot cross-lingual name encoder from Wikipedia interlanguage links for low-resource languages. — [ACL Anthology D19-6131](https://preview.aclanthology.org/fix_video/D19-6131.pdf)
- OpenSanctions Pairs (arXiv 2603.11051, 2026) is a large public benchmark of sanctions entity-matching pairs spanning multiple scripts. Its authors note that LLMs struggle with cross-script transliteration. — [arXiv 2603.11051](https://arxiv.org/pdf/2603.11051)

### Inferences
- An adjudication model needs features beyond string similarity:
  - name-order invariance (token alignment or permutation)
  - Arabic particle and "al-" handling, plus tolerance for partial nasab chains (bin/ibn X bin Y)
  - matching on Hispanic paternal surname alone
  - initials-to-full-name compatibility
  - joined/split-token handling (e.g. "Abdulrahman" vs "Abdul Rahman")
  - cross-script comparison via transliteration or a name-equivalence dictionary
- Name commonness (frequency in a culture) should down-weight matches on common names. Both IBM's "typical vs distinctive" corpus approach and IDF weighting support this.

### Gaps
- I found no accessible numeric evaluation of Rosette or IBM GNR accuracy. Vendor materials describe methods, not benchmark results.
- I did not find primary sources specifically on Muhammad-variant counts, kunya/laqab handling, Wade-Giles vs pinyin matching accuracy, or Cyrillic transliteration standards (ICAO 9303, GOST, BGN/PCGN) in this pass. Those claims should not be cited without further research.

## Q4. Name-variant dictionaries, nicknames, noise tokens, company-name normalisation

### Takeaway
Dictionary-based standardisation is recommended when nicknames or variants are common, because string metrics cannot connect "Bill" to "William". For companies, mapping legal-form suffixes across languages to shared concepts and down-weighting generic "soft stopwords" sharply reduces false positives.

### Cited Findings
- Christen's Recommendation 2: if data contain many nicknames or name variations, apply dictionary-based name standardisation before matching. — [Christen 2006](https://users.cecs.anu.edu.au/~Peter.Christen/publications/tr-cs-06-02.pdf)
- OpenSanctions publishes an organisational-suffix list (S.A., Ltd, GmbH, etc.) with cross-language variants, plus a symbols resource for equivalents of words like "Holding" and "Management". — [OpenSanctions 2025](https://www.opensanctions.org/articles/2025-06-24-name-matching)
- logic-v2 maps OAO, Joint Stock Company and Aktiengesellschaft to one concept. It treats "Holding" and "Industries" as soft stopwords with reduced weight, and applies fuzzy matching only to the distinctive residual core. It also produces explanations such as "First names match, last names are a fuzzy 0.67 match". — [OpenSanctions logic-v2](https://www.opensanctions.org/articles/2025-09-11-logic-v2)
- Translated legal prefixes can break matching. The Russian "ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ" appears as "LIMITED LIABILITY COMPANY" in the US list entry for PROMLOGISTIKA. — [OpenSanctions 2025](https://www.opensanctions.org/articles/2025-06-24-name-matching)
- Learned approaches to variant spellings exist, e.g. "Learning Alternative Name Spellings" (arXiv 1405.2048) and mining digitised family trees for name synonyms (arXiv 1912.04003). — [arXiv 1405.2048](https://arxiv.org/pdf/1405.2048); [arXiv 1912.04003](https://arxiv.org/pdf/1912.04003)

### Inferences
- Normalisation pipeline:
  1. Unicode NFKC, case-fold and strip diacritics (keeping the original).
  2. Remove or flag honorifics and titles.
  3. Canonicalise legal suffixes into a separate "legal form" feature.
  4. Down-weight generic business terms.
  5. Expand nicknames and known variants.
  6. Then score the distinctive core.
- A legal-form mismatch (e.g. LLC vs GmbH) is weak evidence, at most a mild discriminator. Core-name similarity should dominate.

### Gaps
- I found no quantitative study on the effect of nickname tables or company-suffix stripping on screening false-positive rates.

## Q5. Neural and learned name matching (siamese networks, character embeddings, LLMs; 2018-2026)

### Takeaway
Learned models (siamese character-level networks, embeddings, LLMs) help mostly with recall and cross-script candidate generation. The published evidence that they beat well-tuned classical metrics for pairwise adjudication is modest and mixed, and explainability concerns push regulated screening toward deterministic or hybrid designs.

### Cited Findings
- Vinden, Foxcroft & Antonie (2022, IJPDS 7(3)) compared siamese neural network architectures with a Random Forest ensemble of existing string-similarity measures on 25,000 family-name variant pairs. Siamese networks may outperform in some instances but at "considerable computational cost". The authors suggest using them as an extra feature in record linkage. — [IJPDS article 2077](https://ijpds.org/article/view/2077)
- A 2019 arXiv paper ("Who wrote this book?") uses weight-shared siamese BiLSTMs with a 256-unit character embedding layer to decide whether two author-name strings refer to the same entity. — [arXiv 1905.01973](https://arxiv.org/pdf/1905.01973)
- A patent describes "Robust name matching with regularized embeddings", showing industrial use of learned name embeddings. — [US11822887B2](https://patents.google.com/patent/US11822887B2)
- A 2025 NLDB paper studies fairness of siamese fuzzy name matching across demographic or cultural groups. — [Frasincar et al., NLDB 2025](https://personal.eur.nl/frasincar/papers/NLDB2025a/nldb2025a.pdf)
- OpenSanctions (2025) holds that embedding-based name matching (its "project Eridu") is "phenomenal at surfacing a wide set of match candidates" but less suited to discerning false positives. It keeps its production matcher deterministic for explainability, citing regulators' need for explainable decisions. — [OpenSanctions logic-v2](https://www.opensanctions.org/articles/2025-09-11-logic-v2); [OpenSanctions 2025](https://www.opensanctions.org/articles/2025-06-24-name-matching)
- OpenSanctions Pairs (2026) benchmarks LLMs on sanctions entity matching and reports weakness on cross-script transliteration. — [arXiv 2603.11051](https://arxiv.org/pdf/2603.11051)
- An NCIRL thesis proposes a hybrid explainable sanctions-screening framework that combines Sentence-BERT embeddings with fuzzy matching. It is a student thesis, so treat it as low-weight evidence. — [NCIRL thesis](https://norma.ncirl.ie/9864/1/gayatrimaheshjadhav.pdf)

### Inferences
- A practical architecture for alert adjudication: classical and phonetic features plus embedding similarity as inputs, a learned classifier (gradient boosting or logistic regression) calibrated on labelled alert dispositions, and explanations at feature level.

### Gaps
- I could not access full results tables for Vinden et al. or OpenSanctions Pairs, so there are no precision, recall or F1 numbers. I found no peer-reviewed sanctions-specific siamese evaluation with public numbers.

## Q6. How OFAC's Sanctions List Search scores, and documented thresholds

### Takeaway
OFAC's tool runs two techniques: whole-string Jaro-Winkler, and per-name-part Jaro-Winkler plus Soundex with a composite score. It displays the higher of the two. Candidates are pre-filtered by first letter and at least 50% edit-distance similarity. OFAC publishes no recommended threshold; the slider runs to 100 (exact match only). A 2026 reverse-engineering effort by OpenSanctions shows the scores come from a SimMetrics.NET Jaro-Winkler variant that always applies the prefix bonus.

### Cited Findings
- OFAC FAQ 249:
  - The search first finds potential matches by the first letter of the search terms, then keeps names at least 50% similar by edit distance.
  - It uses "Jaro-Winkler, a string difference algorithm, and Soundex, a phonetic algorithm".
  - Technique 1 compares the entire entered string against full list-name strings.
  - Technique 2 splits the entry into name parts, compares each with Jaro-Winkler and Soundex, and calculates a score per part plus a composite.
  - The Score column shows "the higher of the two scores".
  — [OFAC FAQ 249](https://ofac.treasury.gov/faqs/249)
- The Minimum Name Score slider: 100 returns only exact character matches, and lowering it broadens results. OFAC states users must make their own threshold determinations based on internal risk assessments. It does not recommend a cutoff. Searches cover the SDN and Consolidated lists, and delisted names are excluded. — [OFAC FAQs topic 1636](https://ofac.treasury.gov/faqs/topic/1636); [OFAC Sanctions List Search tool page](https://ofac.treasury.gov/sanctions-list-search-tool)
- OpenSanctions (1 July 2026) traced OFAC's scorer to SimMetrics.NET, a C# port of SimMetrics-Java used on the ASP.NET site. The original Winkler method applies the prefix bonus only when the base Jaro score exceeds 0.7, but SimMetrics.NET skips that check and always applies the bonus. An emulator reproducing this matched OFAC scores about 96% of the time, against about 90% for modern libraries such as rapidfuzz and jellyfish. The article does not give the prefix-length or scaling parameters. — [OpenSanctions, "How we reverse-engineered OFAC's sanctions screening algorithm" (2026)](https://www.opensanctions.org/articles/2026-07-01-ofac-matcher/)
- Third-party API vendors expose OFAC-like Jaro-Winkler+phonetic matchers with configurable thresholds (e.g. yente "name-based" and "ofac" algorithms). The OpenSanctions "ofac" variant adds penalties for mismatched country, DOB, gender and identifiers, which OFAC's tool does not document. — [OpenSanctions OFAC matcher article](https://www.opensanctions.org/articles/2026-07-01-ofac-matcher/); [OpenSanctions score tuning FAQ](https://www.opensanctions.org/faq/api/score-tuning/)

### Inferences
- OFAC's score is a pure name-string score with no use of DOB or nationality. Always applying the prefix bonus inflates scores for names that share a prefix. A high OFAC score is therefore weak evidence of identity on its own, and secondary identifiers must drive adjudication.
- Reimplementing "OFAC-style" scoring with standard libraries will diverge from the official tool on about 10% of cases unless the always-on-bonus quirk is replicated.

### Gaps
- OFAC does not document how part scores are aggregated into the composite (averaging or weighting), the Jaro-Winkler parameters, or the Soundex variant. I found no official statement of commonly used industry thresholds (e.g. 80-85%). Treat any such figure as practitioner folklore unless separately sourced.
