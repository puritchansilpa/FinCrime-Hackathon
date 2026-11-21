# Regulatory Expectations and Industry Benchmarks for Sanctions/PEP Name Screening and Alert Adjudication

Research date: 2026-11-21. Primary sources fetched where possible; items verified only through secondary (law-firm/vendor) summaries are flagged. ~15 tool calls; some primary PDFs (Wolfsberg 2019, FATF 2021, OFAC Framework 2019) were not fetched in full this session.

## 1. Regulatory guidance: what regulators and standard-setters expect from screening and alert handling

### Takeaway
Across the US, UK, EU and Singapore, regulators expect risk-based, calibrated screening that includes fuzzy matching, with prompt alert review, documented reasons for every dismissal, vendor oversight, and regular testing. OFAC FAQ 5 is the clearest public statement of how to decide whether a hit is a true match. One big change for anyone citing SR 11-7: in April 2026 the US agencies rescinded both SR 11-7 / OCC 2011-12 and the 2021 BSA/AML model-risk statement, replaced them with new guidance, and placed generative and agentic AI outside its scope.

### Cited Findings

**US – OFAC**
- OFAC FAQ 5, "When screening for sanctions, how do I determine if I have a valid match to a name on one of OFAC's lists?" (released 30 Jan 2015, updated 9 Sep 2026), sets out six steps:
  1. Confirm the alert is against an OFAC list, not another agency's list.
  2. Confirm an OFAC nexus. If the nexus is a country, region, government or other unlisted target, escalate to a supervisor or compliance before acting.
  3. Evaluate match quality. Review the **full list entry** and compare its identifiers (aliases, date of birth, nationality, ID numbers, addresses) with the transaction or customer data, and gather more information if needed. If few details align, the match may be invalid. If multiple details align, continue.
  4. For exact or close matches you cannot rule out, follow internal procedures and check whether a general or specific licence applies.
  5. Block (where a blocked person has an interest) or reject (where the transaction is prohibited but there is no blockable interest).
  6. **Document the steps taken and the information relied on**, report blocked or rejected items to OFAC within 10 business days, and keep records. OFAC "does not confirm potential matches or false positives" and encourages risk-based determinations.
  — [OFAC FAQ 5](https://ofac.treasury.gov/faqs/5)
- The OFAC *Framework for OFAC Compliance Commitments* (May 2019) names five components: management commitment, risk assessment, internal controls, testing/auditing and training. OFAC uses it to decide whether to require compliance commitments in settlements. — [Davis Polk summary](https://www.davispolk.com/index%2Ephp/print/pdf/node/94561); primary document: [OFAC Framework PDF](https://ofac.treasury.gov/media/16331/download?inline) (not fetched this session. Its appendix of root causes reportedly includes "sanctions screening software or filter faults", but this should be verified in the PDF.)

**US – model risk management (SR 11-7 and successors)**
- **SR 21-8 / OCC Bulletin 2021-19** (statement dated 9 Apr 2021, OCC bulletin 12 Apr 2021), the Interagency Statement on Model Risk Management for Bank Systems Supporting BSA/AML Compliance, said MRM guidance *can inform* BSA/AML systems but creates no new requirements. Banks could treat a system as a model, a tool or something else. — [OCC Bulletin 2021-19](https://occ.gov/news-issuances/bulletins/2021/bulletin-2021-19.html); [Fed SR 21-8 PDF](https://www.federalreserve.gov/supervisionreg/srletters/SR2108.pdf); [NCUA release](https://ncua.gov/newsroom/press-release/2021/agencies-issue-statement-and-request-information-bank-secrecy-actanti-money-laundering-compliance)
- The companion 2021 RFI explicitly asked how MRM principles apply to **OFAC sanctions screening tools**. Industry comment letters argued that OFAC systems should not be presumed to be models and that applying MRM to them is costly. — [OCC RFI](https://www.comptrollerofthecurrency.gov/news-issuances/news-releases/2021/nr-occ-2021-43b.pdf); [comment letter](https://www.fdic.gov/regulations/laws/Federal/2021/2021-rfi-model-risk-management-principles-3064-za23-c-007.pdf); [comment letter](https://www.fdic.gov/regulations/laws/Federal/2021/2021-rfi-model-risk-management-principles-3064-za23-c-003.pdf)
- **OCC Bulletin 2026-13, "Model Risk Management: Revised Guidance" (17 Apr 2026)**, issued jointly by the OCC, Federal Reserve and FDIC:
  - It **rescinds OCC 2011-12 / SR 11-7, OCC 2021-19 (the BSA/AML MRM statement)**, the Comptroller's Handbook MRM booklet and OCC 1997-24.
  - It defines a model as a complex quantitative method applying statistical, economic or financial theory. **Deterministic rule-based processes without such theory are excluded.**
  - It is aimed mainly at banks with more than $30bn in assets, and noncompliance alone will not lead to supervisory criticism.
  - **Generative AI and agentic AI are explicitly out of scope.** A future RFI on AI model risk is planned.
  - It does not mention sanctions screening.
  — [OCC Bulletin 2026-13](https://occ.treas.gov/news-issuances/bulletins/2026/bulletin-2026-13.html)
- The Dec 2018 FinCEN/federal banking agencies joint statement encouraging innovative BSA/AML approaches (pilots, AI) is a known primary document, but it was not fetched this session. See Gaps.

**International – FATF**
- FATF, *Opportunities and Challenges of New Technologies for AML/CFT* (July 2021), and its companion *Suggested Actions* list these safeguards for new tools:
  - explainability and transparency of processes and outcomes
  - **human oversight**
  - privacy, cybersecurity, and alignment with standards
  - supervisors building enough expertise to exercise "informed oversight"
  — [FATF Digital Transformation page](https://www.fatf-gafi.org/en/publications/Digitaltransformation/Digital-transformation.html); [Suggested Actions PDF (hosted by Saudi FIU)](https://www.aml.gov.sa/en-us/GuidanceReports/Suggested%20Actions%20New%20Technologies%20AML-CFT.pdf); [Kroll summary](https://www.kroll.com/en/insights/publications/financial-compliance-regulation/fatf-new-technologies-aml-cft)
- The FATF Guidance on PEPs (Recommendations 12 and 22, June 2013) is the reference for PEP screening. Its detailed content was not retrieved this session (see Gaps).

**UK – FCA / OFSI**
- FCA, *Sanctions systems and controls: firms' response to increased sanctions due to Russia's invasion of Ukraine* (published 6 Sep 2023, updated 20 Mar 2024), reviewed more than 90 firms. Its main findings:
  - **Calibration.** Tools must be "adequately calibrated". Some were "too sensitive, causing a high number of false positive names" and others "not sensitive enough", so minor name variations let sanctioned persons go undetected. Some firms could not explain why their systems failed to alert on names on OFSI's list.
  - **Fuzzy matching.** Most firms had fuzzy logic, and the FCA wants it enhanced continually to keep up with evasion.
  - **Backlogs.** "Many firms had significant backlogs in the assessment, escalation, and reporting of alerts", which were made worse by a lack of governance and internal SLAs.
  - **Vendor oversight.** There was over-reliance on third-party tools, and some firms did not understand how their tools were calibrated or when lists were updated. The FCA recommends SLAs for list updates and regular testing.
  — [FCA review](https://www.fca.org.uk/publications/good-and-poor-practice/sanctions-systems-and-controls-firms-response-increased-sanctions-due-russias-invasion-ukraine)
- FCA Handbook FCTR 8 (sanctions thematic review, good and poor practice):
  - Poor practice: failing to regularly review the calibration and rules of automated systems.
  - Good practice: systems "calibrated to include 'fuzzy matching', including name reversal, digit rotation and character manipulation".
  — [FCA Handbook FCTR 8.3](https://handbook.fca.org.uk/handbook/fctr8/fctr8s3)
- A later FCA sanctions systems-and-controls review (reported May 2026) is known only through law-firm summaries:
  - Good practice included periodic calibration and QA testing, and getting vendors to **retest after list updates or changes to matching logic**.
  - Common root causes were outdated lists, suboptimal configuration and calibration, and gaps in ownership/control screening.
  - Stronger firms applied fuzzy matching to more name elements and governed screening exclusions formally.
  — [Regulation Tomorrow, May 2026](https://www.regulationtomorrow.com/2026/05/fca-publishes-findings-from-a-review-of-sanctions-systems-and-controls-in-firms/); [Stephenson Harwood](https://www.stephensonharwood.com/insights/beyond-screening-fca-sets-out-its-expectations-for-effective-sanctions-controls/) (**not verified against the FCA primary text**)

**EU – EBA**
- In **EBA/GL/2024/14** (all supervised entities) and **EBA/GL/2024/15** (PSPs and CASPs under the Transfer of Funds Regulation 2023/1113), issued 14 Nov 2024, the EBA set common EU standards for restrictive-measures governance and controls. They require:
  - an effective screening system that reliably identifies targets
  - regular review of how the screening system performs
  - procedures for investigating alerts, **including cases where an unambiguous determination is not possible**
  - regular staff training
  The Finnish FSA states that the guidelines apply from 30 Dec 2025.
  — [EBA press release](https://www.eba.europa.eu/publications-and-media/press-releases/eba-issues-final-guidance-internal-policies-procedures-and-controls-ensure-implementation-union-and); [EBA Final Report](https://www.eba.europa.eu/sites/default/files/2024-11/eaeae49d-81a5-4154-8af9-5014f6ee8881/Final%20Report%20Guidelines%20restrictive%20measures%20.pdf); [FIN-FSA notice](https://www.finanssivalvonta.fi/en/publications-and-press-releases/supervision-releases/2025/eba-guidelines-on-ensuring-compliance-with-eu-and-national-restrictive-measures--applicable-from-30-dec-2025/)

**Singapore – MAS**
- MAS, *Strengthening AML/CFT Name Screening Practices* (information paper, 2022), is based on 2021 thematic inspections. Findings and expectations:
  - Some firms' tools lacked fuzzy logic and caught only 100% matches.
  - Firms need a name-matching policy tied to their risk appetite, with rules for name order, middle names and token conflicts.
  - Alerts should be handled promptly with documented **justification for each dismissal**.
  - Expected controls include four-eyes checks, risk-focused QA and second-line checks.
  - Poor practice: **dismissing alerts on a consolidated basis** instead of addressing each alert's specific concerns.
  - Poor data maintenance degrades screening accuracy.
  — [MAS information paper](https://www.mas.gov.sg/publications/monographs-or-information-paper/2022/strengthening-aml-cft-name-screening-practices); details via [Waystone](https://compliance.waystone.com/mas-paper-on-strengthening-aml-cft-name-screening-practices/) and [Ripjar](https://ripjar.com/singapore-aml-update-mas-name-screening-guidance-2022) (secondary)

**Industry – Wolfsberg Group**
- *Wolfsberg Guidance on Sanctions Screening* (Jan 2019):
  - An alert "is not, by itself, an indication of sanctions risk". It must be investigated.
  - It covers how firms assess the effectiveness of automated and/or manual screening controls.
  - Independent testing should cover alert generation, thresholds, rules, and data accuracy and completeness.
  - Testing and monitoring should drive "ongoing iterative tuning".
  - Suppression/"good guy" lists are acknowledged as a way to manage repeat false positives.
  - Not all elements apply equally to all firms.
  — [Wolfsberg announcement](https://wolfsberg-group.org/news/publication-of-guidance-on-sanctions-screening/); [copy of guidance PDF](https://www.europeansanctions.com/wp-content/uploads/2022/07/Wolfsberg-Guidance-on-Sanctions-Screening.pdf); [LearnSignal summary](https://www.learnsignal.com/blog/wolfsberg-group-guidance-sanctions-screening-2019-tuning-alert-handling-list-management-lookbacks-guide/)
- *Wolfsberg Principles for Using AI and Machine Learning in Financial Crime Compliance* (1 Dec 2022) set out five elements: legitimate purpose, proportionate use, design and technical expertise, **accountability and oversight**, and **openness and transparency**. They support AI/ML use provided outcomes are fair, effective and **explainable**. — [Regulation Tomorrow](https://www.regulationtomorrow.com/2022/12/the-wolfsberg-group-publishes-principles-for-using-artificial-intelligence-and-machine-learning-in-financial-crime-compliance/); [copy of principles PDF](https://www.cbr.ru/Content/Document/File/146046/AI_ML.pdf)

### Inferences
- OFAC FAQ 5 effectively defines the minimum audit trail for clearing an alert: which list entry was compared, which identifiers matched or conflicted, and what information the decision relied on. An automated or AI adjudicator should produce exactly this per alert.
- MAS's criticism of consolidated dismissals implies that bulk auto-closure without reasoning specific to each alert is a supervisory red flag.
- With SR 11-7 and the 2021 BSA/AML statement rescinded (April 2026), the narrower definition of "model" and the exclusion of GenAI/agentic AI leave a gap in US supervisory guidance for LLM-based adjudication. Firms will likely fall back on the general explainability, oversight and testing principles from FATF, Wolfsberg and the FCA until the promised RFI produces guidance.
- Across jurisdictions, regulators fault both failure modes: over-sensitive calibration (backlogs) and under-sensitive calibration (misses). They frame backlogs as a compliance risk in their own right.

### Gaps
- The full text of the OFAC 2019 Framework root-cause appendix was not fetched. The exact wording on "screening software or filter faults" is unverified.
- The 2018 FinCEN/agency joint statement on innovative efforts was not fetched. Its contents are from background knowledge only (it encouraged pilots and said pilot results exposing gaps would not automatically lead to supervisory action). Verify before citing.
- The FATF 2013 PEP guidance text was not retrieved. Its detail on PEP database use and screening was not confirmed.
- No OFSI-specific screening guidance was retrieved (e.g., OFSI General Guidance, OFSI enforcement notices).
- The FCA Financial Crime Guide (FCG 7) text itself was not fetched. Only FCTR 8 and the 2023 review were.
- The FCA 2026 review is known only through secondary sources.

## 2. Expectations on explainability, auditability, documented rationale, human-in-the-loop, tuning/calibration and testing

### Takeaway
No regulator prohibits automating alert review. What they consistently require is a documented rationale for each dismissal, QA or second review, an understanding of how vendor tools are calibrated, periodic testing and retesting after list or logic changes, and, for AI, explainability and human oversight.

### Cited Findings
- **Documented rationale:** OFAC requires firms to "document the steps" and the information relied on — [OFAC FAQ 5](https://ofac.treasury.gov/faqs/5). MAS requires justification for alert dismissals and detailed resolution guidance — [Waystone on MAS 2022](https://compliance.waystone.com/mas-paper-on-strengthening-aml-cft-name-screening-practices/).
- **Human-in-the-loop / QA:** MAS expects four-eyes checks, risk-focused QA and second-line checks — [Ripjar on MAS](https://ripjar.com/singapore-aml-update-mas-name-screening-guidance-2022). FATF lists human oversight as a safeguard for new technology — [FATF Suggested Actions](https://www.aml.gov.sa/en-us/GuidanceReports/Suggested%20Actions%20New%20Technologies%20AML-CFT.pdf). Wolfsberg's AI principles require accountability and oversight — [Regulation Tomorrow](https://www.regulationtomorrow.com/2022/12/the-wolfsberg-group-publishes-principles-for-using-artificial-intelligence-and-machine-learning-in-financial-crime-compliance/).
- **Explainability:** FATF lists "explainability and transparency of processes and outcomes" as a safeguard — [FATF Suggested Actions](https://www.aml.gov.sa/en-us/GuidanceReports/Suggested%20Actions%20New%20Technologies%20AML-CFT.pdf). Wolfsberg calls for "explainable outcomes" — [Regulation Tomorrow](https://www.regulationtomorrow.com/2022/12/the-wolfsberg-group-publishes-principles-for-using-artificial-intelligence-and-machine-learning-in-financial-crime-compliance/). The FCA criticised firms that could not explain why their systems failed to alert — [FCA 2023](https://www.fca.org.uk/publications/good-and-poor-practice/sanctions-systems-and-controls-firms-response-increased-sanctions-due-russias-invasion-ukraine).
- **Tuning/calibration:** The FCA expects calibration matched to risk and regular review of calibration and rules — [FCA 2023](https://www.fca.org.uk/publications/good-and-poor-practice/sanctions-systems-and-controls-firms-response-increased-sanctions-due-russias-invasion-ukraine); [FCTR 8.3](https://handbook.fca.org.uk/handbook/fctr8/fctr8s3). Wolfsberg recommends iterative tuning driven by testing — [Wolfsberg guidance copy](https://www.europeansanctions.com/wp-content/uploads/2022/07/Wolfsberg-Guidance-on-Sanctions-Screening.pdf).
- **Testing:**
  - The EBA requires regular review of screening system performance — [EBA press release](https://www.eba.europa.eu/publications-and-media/press-releases/eba-issues-final-guidance-internal-policies-procedures-and-controls-ensure-implementation-union-and).
  - The FCA expects regular testing including of outsourced tools — [FCA 2023](https://www.fca.org.uk/publications/good-and-poor-practice/sanctions-systems-and-controls-firms-response-increased-sanctions-due-russias-invasion-ukraine) — and, per secondary sources on the 2026 review, vendor retesting after list or matching-logic changes — [Regulation Tomorrow 2026](https://www.regulationtomorrow.com/2026/05/fca-publishes-findings-from-a-review-of-sanctions-systems-and-controls-in-firms/).
  - OFAC enforcement commentary recommends testing algorithms against close name variants — [HSF Kramer on Payoneer](https://www.hsfkramer.com/notes/sanctions/2021-08/ofac-settlement-with-money-transmitter-highlights-key-ofac-expectations-in-sanctions-compliance-programs).
  - SWIFT-linked sanctions testing services describe tuning tests that compare configuration options against objectives such as reducing false positives — [SWIFT resource](https://swift.com/swift_resource/251880).
- **Backlog handling:** OFAC faulted Payoneer for auto-releasing flagged payments during backlogs. Flagged items should be held — [Kelley Drye](https://www.kelleydrye.com/viewpoints/blogs/trade-and-manufacturing-monitor/ofac-settlement-with-payoneer-inc-highlights-sanctions-expectations-for-online-services); [OFAC enforcement release PDF](https://ofac.treasury.gov/media/911571/download).
- **Data quality:** LSEG argues that false positives are driven as much by data quality, workflow design and analyst decision practices as by the matching engine — [LSEG blog](https://www.lseg.com/en/training/learning-centre/blog/why-false-positives-remain-a-challenge-in-compliance-screening).

### Inferences
- A defensible AI adjudication design would:
  - attach a reason per alert, comparing identifiers against the list entry
  - route only high-confidence false positives to automated clearance
  - send uncertain or "no unambiguous determination" cases (the EBA's phrase) to humans
  - apply sampling QA, four-eyes review on escalations and dismissals, and regression testing after every list or model change
  - never auto-release under backlog pressure

### Gaps
- No regulator found publishes a quantitative threshold for acceptable false-negative rates or required QA sample sizes.
- No primary regulatory text was found that specifically addresses LLM-based alert clearing in sanctions. The 2026 US MRM guidance explicitly defers on GenAI.

## 3. Benchmarks: false-positive rates, alert volumes, analyst time, cost of compliance, enforcement cases

### Takeaway
Industry claims of 85–95%+ false positives in name screening are ubiquitous but come mostly from vendors with no stated method. The best independent quantitative evidence is a Sept 2025 Federal Reserve staff paper showing LLMs cut false positives by about 92% relative to the best fuzzy baseline. Global financial crime compliance cost was put at $206.1bn (LexisNexis, 2023). OFAC enforcement cases repeatedly cite fuzzy-matching blind spots and improper release of alerts.

### Cited Findings

**False positives and analyst time**
- Vendor claims put name-screening false positives at 85–95%, attributed to an unlocated "2026 benchmark" — [Signzy](https://www.signzy.com/blogs/how-false-positives-hide-real-sanctions-alerts). Another vendor says 90–95% — [Sayari](https://sayari.com/resources/blog/financial-industry-compliance-challenges/). (Vendor marketing; methodology not disclosed.)
- Time per alert is contested: Sayari says about 30 minutes to investigate a false alert — [Sayari](https://sayari.com/resources/blog/financial-industry-compliance-challenges/). Signzy describes a median disposition time under 30 seconds — [Signzy](https://www.signzy.com/blogs/how-false-positives-hide-real-sanctions-alerts). The roughly 60x gap likely reflects simple versus complex alerts and differing definitions.
- A Sayari case study claims that, by "widely cited industry benchmarks", 90–95% of analyst time goes to clearing false positives. It reports a vendor-claimed 70% alert reduction and resolution in under 2 minutes — [Sayari case study](https://sayari.com/resources/case-studies/top-bank-sanctions-trade/) (unsourced vendor claims).

**AI versus fuzzy matching**
- Federal Reserve FEDS 2025-092, *Can LLMs Improve Sanctions Screening in the Financial System? Evidence from a Fuzzy Matching Assessment* (Allen & Hatfield, Sept 2025):
  - Four LLM families "reduced sanctions screening false positives by 92 percent" and "increased detection rates by 11 percent relative to the best-performing fuzzy matching baseline".
  - Smaller models performed comparably.
  - LLMs were more than four orders of magnitude slower.
  - A proposed cascade sends only high-uncertainty cases to LLMs, runs about twice as fast as pure LLM screening, and is roughly as accurate.
  - Tiered approaches are likely needed for high-volume payments screening.
  - Staff working paper, not Board policy. It does not estimate analyst time saved.
  — [Fed FEDS 2025-092](https://www.federalreserve.gov/econres/feds/can-llms-improve-sanctions-screening-in-the-financial-system-evidence-from-a-fuzzy-matching-assessment.htm); [PDF](https://www.federalreserve.gov/econres/feds/files/2025092pap.pdf)
  - Note: one secondary summary cited "80%". The Fed abstract says 92%, so use 92%.
- An academic study found that NLP improved detection but raised false positives, and that the threshold drives the trade-off — [PMC11621073](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11621073/).

**Cost of compliance**
- LexisNexis Risk Solutions, *True Cost of Financial Crime Compliance* (Sept 2023), put the global cost for financial institutions at **US$206.1bn**, based on 1,181 respondents. EMEA costs exceeded US/Canada by 39.8%. APAC was 74.5% and LATAM 24.7% of US/Canada. — [LexisNexis press release](https://risk.lexisnexis.com/about-us/press-room/press-release/20230926-global-financial-crime-compliance-costs). One outlet cites differing prior-year figures (a "$214bn in 2022" comparison), which is internally inconsistent. Treat the time series with caution — [fintech.global](https://fintech.global/?p=133082).

**Enforcement cases involving screening or clearing failures**
- **JPMorgan Chase (2018):** the vendor filter failed to flag names with hyphens, initials or additional middle/last names. Settled for $5.26M (violations 2008–2012) — [Law.com](https://law.com/corpcounsel/2018/12/03/ofac-settlement-highlights-limitations-of-search-software); [JD Supra](https://jdsupra.com/legalnews/deficiencies-in-sanctions-screening-50268)
- **Cobham/Aeroflex (2018):** the search used "Almaz Antey Telecom" and missed the listed "Almaz Antey" (an ownership/name-variant failure) — [Law.com](https://law.com/corpcounsel/2018/12/03/ofac-settlement-highlights-limitations-of-search-software)
- **Apple (2019):** the screening tool failed to match "SIS d.o.o." to the listed "SIS DOO". "d.o.o." is the Slovenian LLC form, so this was a legal-suffix normalisation failure — [Orrick](https://media.orrick.com/Media%20Library/public/files/insights/2021/2021-03-31-compliance-lessons-in-recent-office-of-foreign-assets-control-enforcement.pdf); [Visual Compliance](https://www.visualcompliance.com/blog/?p=1626)
- **Amazon (2020):** screening failed to catch "Krimea" as a variant of Crimea. The statutory maximum was $1,038,206,212 — [Orrick](https://media.orrick.com/Media%20Library/public/files/insights/2021/2021-03-31-compliance-lessons-in-recent-office-of-foreign-assets-control-enforcement.pdf)
- **Payoneer (July 2021, $1,385,901.40):** OFAC cited:
  - "weak algorithms that allowed close matches to SDN List entries not to be flagged"
  - flagged payments auto-released without review during backlog periods
  - failure to screen BICs present in SDN entries
  - weak location/IP screening
  — [OFAC release PDF](https://ofac.treasury.gov/media/911571/download); [HSF Kramer](https://www.hsfkramer.com/notes/sanctions/2021-08/ofac-settlement-with-money-transmitter-highlights-key-ofac-expectations-in-sanctions-compliance-programs); [Paul Weiss](https://www.paulweiss.com/insights/client-memos/ofac-enforcement-action-against-us-payments-company-shows-the-importance-of-robust-sanctioned-person-and-location-screening)
- **Supervisory findings (UK):** significant alert backlogs at many firms, mis-calibration, and inability to explain missed alerts — [FCA 2023](https://www.fca.org.uk/publications/good-and-poor-practice/sanctions-systems-and-controls-firms-response-increased-sanctions-due-russias-invasion-ukraine)

### Inferences
- The enforcement record identifies specific test cases any screening or adjudication system should handle:
  - hyphens, initials and extra name tokens (JPMorgan)
  - legal-form suffix normalisation such as d.o.o./DOO (Apple)
  - transliteration and spelling variants such as Krimea/Crimea (Amazon)
  - partial or extended entity names (Cobham)
  - non-name identifiers such as BICs (Payoneer)
- Payoneer also shows that alert disposition under volume pressure is itself a failure mode.
- For a hackathon or pitch, the Fed paper (92% fewer false positives, +11% detection) is the most citable non-vendor evidence that AI can reduce false positives without sacrificing recall. Its cascade design matches the regulatory preference for routing uncertain cases to humans.

### Gaps
- No independent (regulator, ACAMS or academic) survey was found that measures name-screening false-positive rates or minutes per alert with a disclosed method. All 85–99% figures found are vendor claims.
- No data were found on typical alert volumes per analyst per day or on FTE counts for screening teams.
- The LexisNexis report's breakdown of screening-specific costs and its 2024–2026 editions were not retrieved.
- OFAC cases from 2022–2026 involving screening (e.g., later fintech/crypto cases) were not researched in depth.

## 4. Typical analyst SOP for discounting a hit: primary/secondary identifiers, DOB tolerance, country

### Takeaway
The only authoritative public SOP is OFAC FAQ 5: compare the full list entry's identifiers (name/aliases, DOB, nationality, ID numbers, address) with your data; discount when few details align; escalate when several align; document everything. Industry practice adds name-matching rules (name order, middle names, token conflicts) and four-eyes review, but no primary source found specifies DOB tolerance windows or a formal primary/secondary identifier hierarchy.

### Cited Findings
- **Identifiers to compare:**
  - OFAC lists aliases, date of birth, nationality, ID numbers and addresses. "If few details align, the match may be invalid", while multiple aligned details require escalation and procedures. Matches to an unlisted country, region or government must be escalated — [OFAC FAQ 5](https://ofac.treasury.gov/faqs/5).
  - OFAC FAQ 5 also directs reviewers to compare against the **full** SDN entry, not just the name.
  - The Payoneer case shows non-name identifiers such as BICs must be screened where list entries contain them — [Kelley Drye](https://www.kelleydrye.com/viewpoints/blogs/trade-and-manufacturing-monitor/ofac-settlement-with-payoneer-inc-highlights-sanctions-expectations-for-online-services).
- **Name logic:** MAS expects rules for name-order differences, the importance of middle names and conflicting tokens — [Ripjar on MAS 2022](https://ripjar.com/singapore-aml-update-mas-name-screening-guidance-2022). The FCA expects fuzzy matching to handle name reversal, digit rotation and character manipulation — [FCTR 8.3](https://handbook.fca.org.uk/handbook/fctr8/fctr8s3).
- **Unresolvable cases:** the EBA requires procedures for alerts where no unambiguous determination is possible — [EBA press release](https://www.eba.europa.eu/publications-and-media/press-releases/eba-issues-final-guidance-internal-policies-procedures-and-controls-ensure-implementation-union-and).
- **Reasoning per alert, not in bulk:** MAS criticised dismissing alerts on a consolidated basis — [Waystone on MAS 2022](https://compliance.waystone.com/mas-paper-on-strengthening-aml-cft-name-screening-practices/).

### Inferences
- A practical discount rule consistent with OFAC FAQ 5 runs:
  1. Assess the strength of the name match, including aliases, token order and transliteration.
  2. Look for a **conflicting** strong identifier: a different full DOB or year of birth beyond a set tolerance, a different nationality or country of residence, a different government ID number, or a different gender or entity type (individual versus vessel versus entity). Any of these supports discounting.
  3. A merely **absent** identifier does not support discounting. Gather more information or escalate.
  4. Several concordant identifiers mean escalation and a check for licences.
- Commonly used industry conventions are not sourced here and should be treated as assumptions, not regulatory requirements:
  - treating name plus DOB plus nationality as the primary identifiers, and address, gender and place of birth as secondary
  - DOB tolerance windows such as ±1–2 years for list entries with only a year or a range ("circa")

### Gaps
- No primary regulatory or Wolfsberg text was found specifying DOB tolerance, a ranking of primary and secondary identifiers, or a numeric match-score threshold. These are institution-specific and normally set in internal procedures and vendor configuration.
- The Wolfsberg 2019 full text sections on alert handling were not read directly in this session and may contain more detailed adjudication guidance.
