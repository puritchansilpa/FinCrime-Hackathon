# LLM Approaches to Entity Matching, Information Extraction, and Sanctions/Adverse-Media Alert Adjudication (2022-2026)

Scope note: focused on 2022-2026; WePS (2007-2010) is included as foundational, pre-LLM work. Evidence is graded throughout: [ACADEMIC] = peer-reviewed or preprint with a stated method; [REGULATOR-RESEARCH] = central-bank staff research; [PRACTITIONER] = a data provider describing its own pipeline, with no metrics; [VENDOR] = marketing claims with no published methodology.

## 1. LLM entity matching: what was tried, accuracy, cost, consistency

### Takeaway
Since GPT-3 (2022), frontier LLMs have matched or beaten fine-tuned PLM matchers such as Ditto/RoBERTa zero-shot (around 89%+ F1 on most standard benchmarks). Their main advantage is robustness on unseen entities, where they beat transferred PLMs by at least 8 F1 points. Results are prompt-sensitive, especially for weaker or open models. Few-shot examples and matching rules help some models but hurt others. Fine-tuned small models (GPT-4o-mini, Llama-3.1) can match or beat zero-shot GPT-4 at a tiny fraction of the cost. Listwise "select" prompting and batching cut cost and improve consistency.

### Cited Findings
- **Narayan et al. 2022 (PVLDB 16(4)) [ACADEMIC]:** they cast entity matching, imputation and error detection as prompts, serialising rows to text and asking "Are products A and B the same?". The largest GPT-3 (175B, text-davinci-002) outperformed state-of-the-art ML/DL methods using only a few examples — [arXiv 2205.09911](https://arxiv.org/pdf/2205.09911); [PVLDB](https://www.vldb.org/pvldb/vol16/p738-narayan.pdf)
- With 10 manually chosen demonstrations, GPT-3 matched or beat the state of the art on 11 of 14 benchmark datasets — [Hazy Research blog, Jan 2023](https://hazyresearch.stanford.edu/blog/2023-01-13-datawrangling)
- **Contamination caveat:** Peeters & Bizer note that the standard EM benchmarks are widely discussed online, so GPT-3/ChatGPT training data likely includes them, which may inflate scores — [Using ChatGPT for Entity Matching, arXiv 2305.03423](https://arxiv.org/pdf/2305.03423)
- **Peeters, Steiner & Bizer, "Entity Matching using Large Language Models" (EDBT 2025; arXiv 2310.11244 v1-v4) [ACADEMIC]:**
  - Models: GPT-4o-mini, GPT-4 (0613), GPT-4o, Llama2-70B, Llama3.1-70B, Mixtral-8x7B, with RoBERTa and Ditto as baselines.
  - Datasets: WDC Products (80% corner cases), Abt-Buy, Walmart-Amazon, Amazon-Google, DBLP-Scholar, DBLP-ACM, each downsampled to about 1,250 test pairs.
  - All runs used temperature 0 — [arXiv 2310.11244v4](https://arxiv.org/html/2310.11244v4)
  - Zero-shot GPT-4 reached ≥89% F1 on 5 of 6 datasets. It was 2.65-4.71 points ahead of the best PLM on three datasets and 0.73-4.49 points behind on the other three — [arXiv 2310.11244v4](https://arxiv.org/html/2310.11244v4)
  - Prompt sensitivity: GPT-4's mean standard deviation across prompts was 2.26 F1, versus 6.18-18.54 for the other models. No single prompt was best across models and datasets — [arXiv 2310.11244v4](https://arxiv.org/html/2310.11244v4)
  - Unseen entities: transferred RoBERTa/Ditto lost 22-61 F1 points, and every LLM beat the best transferred PLM by at least 8 points. v1 reported a 34-57% F1 gap for GPT-4 — [v4](https://arxiv.org/html/2310.11244v4); [v1](https://arxiv.org/pdf/2310.11244v1.pdf)
  - In-context demonstrations helped only about 61% of model/dataset combinations. GPT-4 lost on WDC and Abt-Buy; GPT-mini and Mixtral often lost 4-26 points; GPT-4o improved everywhere — [arXiv 2310.11244v4](https://arxiv.org/html/2310.11244v4)
  - Handwritten or learned matching rules in the prompt cost GPT-4 1-3 points but gained the other models 0.3-17 points — [arXiv 2310.11244v4](https://arxiv.org/html/2310.11244v4)
  - Fine-tuning (10 epochs; LoRA 4-bit for Llama) gave about 1-26 points over the best zero-shot prompt. Fine-tuned GPT-mini and Llama3.1 beat zero-shot GPT-4 by about 1-10 points on 4 of 6 datasets. GPT-mini generalised well across datasets; fine-tuning reduced generalisation for the Llama models — [arXiv 2310.11244v4](https://arxiv.org/html/2310.11244v4); [EDBT 2025 slides](https://www.sowi.uni-mannheim.de/media/Einrichtungen/dws/DWS_News/Documents/Peeters-Entity-Matching-using-LLMs-EDBT2025.pdf)
  - Cost at Aug-2024 prices, zero-shot, per pair: GPT-mini about $0.00006, GPT-4o about $0.00024, GPT-4 about $0.00474 (0.006¢, 0.024¢ and 0.474¢). Few-shot and rule prompts use 1.3-11x more tokens. GPT-4 was about 50% slower than the other OpenAI models — [arXiv 2310.11244v4](https://arxiv.org/html/2310.11244v4)
  - Explanations: GPT-4 can output structured per-attribute importance and similarity values. These correlate with cosine similarity at 0.75-0.85 and with Generalized Jaccard at 0.73-0.83 — [arXiv 2310.11244v4](https://arxiv.org/html/2310.11244v4)
- **Failure modes from Peeters et al.'s error analysis (directly relevant to name/DOB matching):**
  - False positives came from "partial information matches" (19 cases) and "overemphasis on author similarity" (16) on DBLP-Scholar, and from overemphasis on one matching attribute such as brand or model on Walmart-Amazon (23 of 26 judged relevant).
  - False negatives came from surface variation in titles or venues and from incomplete attribute lists — [arXiv 2310.11244v4](https://arxiv.org/html/2310.11244v4)
- **BATCHER (Fan et al., ICDE 2024) [ACADEMIC]:** batches several pairs per prompt and uses covering-based demonstration selection. It reports 4x-7x cost savings with higher and more stable accuracy than standard per-pair prompting (GPT-3.5-turbo-0301, 8 ER datasets). The best configuration was diversity-based question batching plus covering-based demonstration selection — [arXiv 2312.03987](https://arxiv.org/html/2312.03987v1); [code](https://github.com/fmh1art/batcher)
- **"Match, Compare, or Select?" / ComEM (Wang et al., COLING 2025) [ACADEMIC]:** pairwise binary matching ignores global consistency across candidate records. A "select" strategy, which picks the match from a candidate list, improved average F1 by 17.58% over pairwise matching. ComEM first uses a medium LLM to rank and filter, then a strong LLM to select from the top-k. This adds up to about 4% F1 over select-only, at lower cost — [arXiv 2405.16884](https://arxiv.org/html/2405.16884v3); [ACL Anthology](https://preview.aclanthology.org/setup/2025.coling-main.8)

### Inferences
- A watchlist hit is a one-record-versus-few-candidates problem, so the "select" framing fits it well. Peeters' error classes map directly to sanctions false positives: partial matches, and overweighting a matching name while ignoring a conflicting DOB.
- A model that is strong zero-shot (GPT-4 class) should not be fed hand-written rules in the prompt. Rules are better applied deterministically outside the LLM, which also preserves auditability.
- At published 2024 prices, LLM cost per adjudication is negligible compared with analyst time. Latency is the binding constraint, not dollars (see Section 5).

### Gaps
- Per-dataset Narayan 2022 F1 values were not retrieved. "MatchGPT" appears to be the Mannheim group's code name for this line of work, but this was not verified from a primary page here.
- No retrieved 2025-2026 EM benchmark covers person/KYC records rather than products and bibliographic data. All the cited EM benchmarks are product or citation data.

## 2. LLMs for structured information extraction (dates, places, relations) with JSON outputs; hallucination; date normalisation

### Takeaway
Schema-constrained JSON output reliably fixes syntax but not semantics. The main failure modes are wrong values, missing values, and values invented to satisfy a required field. Temporal normalisation is still hard: LLM accuracy on ISO-TimeML/SCATE-style normalisation benchmarks sits around 0.6-0.7. Nullable fields, explicit "not stated" options, typed date formats and post-hoc validators are the recommended mitigations.

### Cited Findings
- LLMStructBench has 995 manually verified samples of JSON extraction from text. It scores structural validity separately from semantic accuracy and classifies errors as missing keys, missing values, and wrong values — [arXiv 2602.14743](https://arxiv.org/html/2602.14743v1)
- In layout-rich document extraction, error sources include LLM hallucination and source values that are not aligned to a common format, for example varying date formats. These require output cleaning — [arXiv 2502.18179](https://arxiv.org/pdf/2502.18179)
- Typed JSON schemas with a declared date format reduced formatting errors in metadata extraction — [arXiv 2510.19334](https://arxiv.org/pdf/2510.19334)
- Practitioner report: a model filled a *required* date field with a plausible value when the source text contained none. The fix was to make the field nullable and add validators. The output was "perfect JSON" that was still wrong — [Towards Data Science](https://towardsdatascience.com/your-llm-can-return-perfect-json-and-still-be-wrong/) [PRACTITIONER]
- Temporal normalisation:
  - Discourse-aware in-context learning for TimeML VALUE normalisation is "competitive" with task-specific models — [arXiv 2404.07775](https://arxiv.org/html/2404.07775v1)
  - Having LLMs generate executable SCATE code beats direct interval generation by more than 10 points in accuracy and F1. Average accuracy across six models was about 0.62, with Claude 3.7 at about 0.69 — [arXiv 2507.06450](https://arxiv.org/html/2507.06450v1)
  - Note that these benchmarks are not directly comparable to each other.

### Inferences
- For DOB, death-date and report-date extraction, let the LLM output the verbatim date string plus the evidence span. Normalise deterministically in code (partial dates, year-only, DD/MM vs MM/DD ambiguity), and require null when nothing is present. This avoids the documented "required field → fabricated value" failure.
- Relative expressions in web articles ("last year", "aged 54") need the document's publication date as an anchor. Normalisation research shows this anchoring is where LLM accuracy drops.

### Gaps
- I found no published hallucination *rate* specific to biographical dates or places in noisy web text.
- I found no benchmark for extraction from sanctions or PEP profile free-text.

## 3. Person-name / namesake disambiguation in web search results; entity linking

### Takeaway
WePS (2007-2010) defined the canonical task of clustering the top ~100 web results for an ambiguous person name by actual individual, later adding attribute extraction (DOB, occupation, etc.). It found simple agglomerative clustering strong and B-Cubed the appropriate metric. LLM-era work has moved to entity *linking* using candidate generation plus LLM multiple-choice selection with KB descriptions. No retrieved LLM-era paper benchmarks person-namesake disambiguation specifically.

### Cited Findings
- **WePS (foundational, pre-LLM):**
  - WePS-1 ran at SemEval-2007 as name coreference only. WePS-2 refined the metrics and added an attribute extraction task. WePS-3 proposed merging clustering and attribute extraction into one task — [WePS resources repo](https://github.com/jotaefea/weps); [WePS-3 CfP](https://groups.google.com/g/web-people-search-task/c/uHfn-uhVVzA); [SemEval-2007 task paper](https://preview.aclanthology.org/fix_video/S07-1012.pdf)
  - Each name query comes with about 100 top web pages — [Kalashnikov et al. TKDE 2008](https://www.ics.uci.edu/~dvk/pub/TKDE08_dvk_WePS.pdf)
  - B-Cubed was argued to be the appropriate clustering metric — [arXiv 1401.4590](https://arxiv.org/pdf/1401.4590)
  - Single-pass and agglomerative clustering performed best on the SemEval-2007 data — [Springer chapter](https://link.springer.com/doi/10.1007/978-3-642-00570-1_15)
- **LLM entity linking (2024-2026):**
  - ChatEL and EntGPT-P use multi-step prompting: generate candidates, have the LLM generate auxiliary context about the mention, then ask a multiple-choice question. EntGPT-P's worked example is disambiguating "George Bush" — [arXiv 2402.06738](https://www.arxiv.org/pdf/2402.06738); [arXiv 2402.14858](https://arxiv.org/html/2402.14858v1)
  - Another approach first prunes candidates by KG type, then appends Wikipedia descriptions so the LLM can handle entities it never saw in training — [arXiv 2505.02737](https://arxiv.org/pdf/2505.02737v1)
  - LELA (2026) targets truly zero-shot, end-to-end LLM entity linking across unseen domains — [arXiv 2605.26956](https://arxiv.org/pdf/2605.26956)

### Inferences
- For "web results mostly about namesakes", the WePS framing argues for treating each result as a document to be assigned to a person cluster or "not our subject". The decision should rest on extracted discriminating attributes (DOB/age, nationality, occupation, location), not name similarity. Any attribute conflict should push the result to "different person".
- LLM entity-linking work shows that giving the model a short reference profile (the watchlist record and customer KYC) as the "KB description" is the pattern that works.

### Gaps
- I found no LLM-era benchmark on the WePS datasets, and no published error rate for LLM namesake rejection in adverse-media search results.

## 4. Adverse media screening: pipelines and LLM use

### Takeaway
Pre-LLM systems used search, NER, classification and entity-resolution pipelines. Published LLM work is thin. One 2025 academic agentic-RAG system (Univ. Luxembourg) reports an Adverse Media Index but no metrics in its abstract. The most concrete practitioner account (OpenSanctions, 2026) uses dual-LLM adjudication with an adversarial reviewer and flags prompt-injection and manipulated-narrative risks.

### Cited Findings
- **Pre-LLM baseline:** "Adverse Media Mining for KYC and ESG Compliance" (2021) describes an ML system for real-time and batch adverse-media search on person and organisation queries — [arXiv 2110.11542](https://arxiv.org/abs/2110.11542v1)
- **Chernakov, Jafarnejad & Frank, "An Agentic LLM Framework for Adverse Media Screening in AML Compliance" [ACADEMIC preprint]:**
  - An LLM agent searches the web, retrieves documents and computes an Adverse Media Index (AMI) per subject with RAG.
  - Evaluation uses PEPs, watchlist and sanctioned persons from OpenSanctions, plus clean names from academic sources.
  - The abstract claims the system distinguishes high-risk from low-risk individuals but gives no metrics. The paper itself flags that common names may match thousands of individuals and that transliteration and aliases complicate resolution — [arXiv 2602.23373](https://arxiv.org/abs/2602.23373); [ORBilu](https://orbilu.uni.lu/handle/10993/67145)
  - Note: the arXiv ID (2602) and the reported 29 Dec 2025 submission date do not line up; verify the record.
- **OpenSanctions, "How LLMs are changing screening" (May 2026) [PRACTITIONER]:**
  - Classical name matching proposes candidate pairs. Two LLM roles then assess each pair independently: an "analyst" and an adversarial "senior reviewer". Disagreement goes to manual review.
  - Domain knowledge is written as prose "scopes" per dataset; for example, terror splinter groups must not be merged.
  - Examples: a reviewer vetoed a merge of two same-named Chinese NPC deputies from different provincial delegations, and the LLM rejected two Austrian municipal deputies with a 0.97 structured similarity score because they came from different villages.
  - Reported failure: LLMs struggled with career transitions, for example that a former Defence Minister could later become Prime Minister.
  - No accuracy metrics are given. Customers reportedly use LLMs for alert qualification and KYC acceleration — [OpenSanctions](https://www.opensanctions.org/articles/2026-05-12-llms-screening/)
- **OpenSanctions risk commentary:**
  - Internal KYC notes are opinion-laden and can amplify bias.
  - PR firms reportedly edit politicians' Wikipedia pages, and the author expects planted prompt injections in official biographies.
  - Adverse-media tools will increasingly struggle to tell genuinely adverse coverage from coverage manufactured to look adverse — [OpenSanctions](https://www.opensanctions.org/articles/2026-05-12-llms-screening/)
- A USPTO patent describes "contextualized entity resolution and sentiment analysis in adverse media screening". This is evidence of industry pipeline designs, not of performance — [USPTO 12481667](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12481667)

### Inferences
- Web search results should be treated as untrusted input to the LLM, since prompt injection is a stated risk. The adjudicator should only see extracted facts or quoted spans, not follow instructions in page content.

### Gaps
- I found no peer-reviewed precision/recall figures for LLM adverse-media relevance or namesake classification.

## 5. LLMs/GenAI for sanctions/PEP alert adjudication and L1 review: published and vendor results

### Takeaway
The only independent quantitative evidence found is a Federal Reserve Board staff paper (Allen & Hatfield, FEDS 2025-092). It reports LLMs cutting name/address-matching false positives by 92% and raising detection by 11% compared with the best fuzzy matcher. However, the LLMs were more than 10,000x slower, which motivates a fuzzy→LLM cascade. Vendor figures (50-80% false-positive reduction, "100% true positive retention") are unverified marketing.

### Cited Findings
- **Allen & Hatfield, "Can LLMs Improve Sanctions Screening in the Financial System? Evidence from a Fuzzy Matching Assessment" (Federal Reserve Board, Sept 2025, updated Dec 2025) [REGULATOR-RESEARCH]:**
  - Compared four LLM families with common fuzzy-matching algorithms on name and address matching.
  - Across realistic thresholds, the LLMs cut false positives by 92% and raised detection by 11% relative to the best fuzzy system. Smaller models in the same families cut false positives by about 80% with the same detection gain.
  - The LLMs were more than four orders of magnitude slower. A cascade that sends uncertain cases to the LLM and easy cases to exact/fuzzy matching was nearly 2x faster than LLM-only, at similar accuracy.
  - The authors expect payments screening to need tiered designs, while slower processes such as CDD and lending could rely more on LLMs.
  - Analyst time savings were not measured — [FRB page](https://www.federalreserve.gov/econres/feds/can-llms-improve-sanctions-screening-in-the-financial-system-evidence-from-a-fuzzy-matching-assessment.htm); [PDF](https://www.federalreserve.gov/econres/feds/files/2025092pap.pdf); [FRBSF listing](https://www.frbsf.org/research-and-insights/publications/board-of-governors/2025/10/can-llms-improve-sanctions-screening-financial-system-evidence-fuzzy-matching-assessment/)
- **Vendor claims (no methodology published) [VENDOR]:**
  - SymphonyAI "AI Overlay for Screening" (formerly SensaAI) claims 80% false-positive reduction, "100% true positive retention" and no training data required. An earlier proof of concept reported 56% — [SymphonyAI](https://www.symphonyai.com/financial-services/sensaai-for-sanctions)
  - WorkFusion's AI agent "Evelyn" claims to remove 80% of false positives and to deliver 50-70% L1 hit adjudication — [WorkFusion](https://www.workfusion.com/solutions/streamline-sanctions-screening-alert-review/)
  - Socure reports its LLM-powered watchlist engine improved the false-positive ratio from 100:1 to 3:1 — [Socure blog](https://www.socure.com/blog/llms-new-standard-in-watchlist-screening). A 2024 Socure announcement claimed a 30% false-positive reduction from GenAI case management — [TMCnet](https://www.tmcnet.com/usubmit/2024/04/24/9999654.htm)
  - Genpact case study: riskCanvas plus AWS Bedrock writes match summaries with a suggested decision, with a reported 50% reduction in analyst total cost of ownership — [Genpact](https://genpact.com/insight/a-leap-in-sanctions-screening-accuracy-and-efficiency)
  - Moody's recommends a hybrid of ML, LLMs and humans, and cautions on the cost of agentic AI in screening — [Moody's](https://www.moodys.com/web/en/us/kyc/resources/insights/managing-the-cost-of-agentic-ai-in-sanctions-screening-why-machine-learning-matters.html)
  - An unsourced industry article cites 40-70% false-positive reduction from AI decision support at L1 — [SCCE article](https://dev.corporatecompliance.org/news-and-insights/articles/managing-sanctions-alert-fatigue-and-strengthening-level-1-compliance)
- **Consultancy view (not regulatory guidance) [PRACTITIONER]:**
  - Auto-dispose only low-risk, high-confidence cases and escalate the rest.
  - "GenAI outputs are not inherently explainable and may not perfectly reflect model logic or vary between runs." Interpretable signals should come from the underlying model or rules, with GenAI only writing the narrative — [FTI Consulting, Feb 2026](https://www.fticonsulting.com/insights/articles/beyond-speculation-applying-ai-sanctions-compliance)

### Inferences
- The Fed result is about *name/address matching*, not full alert adjudication with DOB, nationality and adverse-media context. It supports LLMs as a better matcher but does not validate end-to-end auto-closure.
- The 92% and 11% figures are relative to fuzzy baselines on the authors' constructed test set; check the PDF for dataset construction before quoting them as operational.

### Gaps
- I found no regulator speech (FCA, MAS, FinCEN, OFAC, HKMA) specifically endorsing or limiting LLM-based sanctions alert closure.
- I found no bank-published live production metrics, and no independent validation of vendor claims. The Fed paper's dataset details and model names were not extractable because the PDF was compressed binary.

## 6. Hybrid designs: LLM as extractor plus deterministic decider; LLM-as-judge with abstention; self-consistency; calibration and determinism

### Takeaway
The converging pattern across academic, regulator-staff and practitioner sources has four parts:
- a cheap deterministic or fuzzy first pass;
- the LLM used for extraction, or for adjudicating only uncertain cases;
- disagreement or low confidence routed to humans;
- explainability anchored in deterministic signals.

Verbalised LLM confidence is systematically overconfident, and self-consistency is a useful but not standalone abstention signal. Temperature 0 is standard in EM research but does not by itself guarantee run-to-run determinism.

### Cited Findings
- Cascade (fuzzy/exact → LLM for uncertain cases) kept accuracy at about 2x the speed of LLM-only — [FRB FEDS 2025-092](https://www.federalreserve.gov/econres/feds/can-llms-improve-sanctions-screening-in-the-financial-system-evidence-from-a-fuzzy-matching-assessment.htm)
- Medium LLM filters and strong LLM selects (ComEM) gave higher F1 at lower cost — [arXiv 2405.16884](https://arxiv.org/html/2405.16884v3)
- Dual-LLM analyst plus adversarial reviewer, with disagreement escalated to a human — [OpenSanctions](https://www.opensanctions.org/articles/2026-05-12-llms-screening/)
- Deterministic or interpretable model as the decider, with GenAI writing the narrative. The source warns GenAI output "may... vary between runs" — [FTI Consulting](https://www.fticonsulting.com/insights/articles/beyond-speculation-applying-ai-sanctions-compliance)
- Peeters et al. ran all LLMs at temperature 0 "to reduce randomness" — [arXiv 2310.11244v4](https://arxiv.org/html/2310.11244v4)
- Verbalised confidence is systematically overestimated, especially in instruction-tuned models — [arXiv 2510.20460](https://arxiv.org/html/2510.20460v1)
- A 2026 audit found neither self-consistency nor cross-model agreement reliable as a *standalone* abstention score. Self-consistency correlated best with correctness on GPQA, but verbalised confidence gave the better risk-coverage trade-off — [arXiv 2607.08065](https://arxiv.org/pdf/2607.08065)
- Risk-controlled refusal frameworks (UniCR) combine several signals, including self-consistency dispersion, into a calibrated probability with refusal thresholds — [arXiv 2509.01455](https://arxiv.org/html/2509.01455v1)
- I-CALM uses verbal confidence to decide when to abstain and characterises an abstention-hallucination frontier — [arXiv 2604.03904](https://arxiv.org/html/2604.03904)
- Confidence-informed self-consistency weights majority votes by confidence and needs fewer samples — cited within [arXiv 2510.20460](https://arxiv.org/html/2510.20460v1)

### Inferences
- A defensible design for the target system:
  - The LLM extracts typed facts with evidence spans and null-when-absent: DOB, death date, nationality, aliases, report date, and whether a source is about the same person.
  - Deterministic rules decide. For example, a hard DOB conflict means discount; an exact DOB plus nationality match means escalate; a death date before account activity is a strong discount, and so on.
  - Abstain or escalate when extraction disagrees across runs or models, or when evidence is absent.
  - Cache the prompt, model version and output for reproducibility and audit, since temperature 0 alone is not fully deterministic. This addresses the FTI "varies between runs" concern.
- Never auto-close on the LLM's self-reported confidence alone, because the literature shows it is overconfident. Use agreement signals plus rule-based conflicts.

### Gaps
- I found no study measuring run-to-run variance at temperature 0 for EM or adjudication specifically.
- The calibration papers were assessed from search snippets, not full text, and several are 2026 preprints that are not peer-reviewed.
