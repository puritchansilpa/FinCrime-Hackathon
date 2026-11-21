# 2-minute demo: script and shot list

**Story in one line:** every decision follows the same four steps. The system clears namesakes only on a stated contradiction, confirms only on agreement, and for everything else tells the analyst the one fact that would settle it.

**Narration:** about 280 words, which is 2 minutes at a calm pace. Every number and example below is real, from the dev run.

## Before recording

1. **Rebuild the app from a fresh run:**
   ```sh
   system/run dev output/dev.jsonl
   python3 tools/build_review_ui.py
   ```
2. **Open `build/review_ui.html` in Chrome** at 1440 px wide, zoom 100%.
   - Pick light or dark mode and keep it for the whole video.
   - The page embeds the event's data: record locally, and don't share the file.
3. **Terminal:** have it ready with large font and these two commands typed:
   ```sh
   python3 validate.py --data dev --output output/dev.jsonl --score dev/practice_labels.jsonl
   python3 adversarial/run.py
   ```
4. **Clear earlier analyst decisions** (DevTools → Application → Local Storage), so the export count starts at 0.
5. **Optional title card** (3 seconds, before 0:10): four boxes in a row.

   **1 Who is the customer? → 2 Who is the listed person? → 3 Compare each fact → 4 Apply the rules**

   Underneath: *contradiction → clear · agreement → confirm · otherwise → review*
6. **Hits used, all real:**

   | Hit | Used for |
   |---|---|
   | `H-582410` | **how a decision works:** Elvira Velasco Morillo, SAME_ENTITY. Joint account; verified ID from a KYC note; hit's birth year from the profile ("a 30-year-old in November 1998") |
   | `H-017810` | Aleksandar Raskovic → "Rajković, Aleksandar": REVIEW, leaning SAME; the hit's date of birth would settle it |
   | `H-622EDD` | the same customer → "Raković, Aleksandar": cleared on DOB, via the one search result about this PEP |

## Script

| Time | On screen | Say |
|---|---|---|
| **0:00–0:10** | Queue page (`#/`), the four totals | "A bank screened 440 customers and got 819 watchlist hits. Most are just people with similar names, but clearing a real match is the costliest mistake there is." |
| **0:10–0:20** | Title card, then open `H-582410`. Scroll slowly to the **Customer** card; point at the *How it was found* line (joint holders, the screened name picks CUS-377745) and the verified name and DOB chip `NOTE-14E25A` | "Every decision follows four steps. One: who is the customer? We follow the alert's link, here a joint account, pick the holder that fits, and trust the latest approved ID check over what was typed." |
| **0:20–0:30** | **Watchlist hit** card: *Date of birth: 1967 or 1968 (age in profile)* | "Two: who is the listed person? Their birth date may be listed, written in the profile, or in a search result, but only one about this listing, never a namesake." |
| **0:30–0:38** | **Fact by fact** table: Name, Date of birth and Country all *Agree*, each with its evidence chip | "Three: compare name, birth date, country, timing and death, fact by fact, each tied to the record it came from." |
| **0:38–0:45** | Scroll up to the **Same entity** tag and the reason text | "Four, the rules: a contradiction clears the hit, agreement confirms it, anything else goes to review." |
| **0:45–0:55** | Terminal: run `validate.py`, then `adversarial/run.py` | "It's deterministic Python: 50 of 50 practice labels, zero unsafe clearances, 128 of 128 on our hard cases, identical across five runs." |
| **0:55–1:10** | Queue. Point at *Cleared 465*, *Same entity 124*, *Needs review 230*; tick **Confidence band → Leaning same entity** | "465 hits are cleared, each on a named contradiction. 124 go to compliance. The 230 it can't settle are ranked by how much one fact would save, and banded by which way the evidence leans." |
| **1:10–1:30** | Search `H-017810`, open it. **Confidence band** (leaning same entity), then **Evidence required** (Hit date of birth: confirm when born in 1979; clear when before 1978 or after 1980) | "This one leans the same: the verified name and country agree, but the hit gives no date of birth. So the system says what would settle it: born in 1979 confirms; before 1978 or after 1980 clears." |
| **1:30–1:45** | Back, open `H-622EDD`. **Search results**: one *Used*, the rest *Not used*. Click `NOTE-CA9BBC`; the drawer highlights the name and DOB | "Same customer, another profile. Namesake search results are thrown out; the one about this Serbian PEP puts his birth in 1972 or '73. The customer's verified ID, read from this note, says 1979. Cleared." |
| **1:45–1:55** | Close the drawer, back to `H-017810` → **Your decision** → *Clear as a different person*. The button stays disabled; pick `DOB_MISMATCH`, type a source, save. Point at **Export (1)** | "Analysts get the same guard-rail: they can't clear without naming the contradiction and its source, and every decision is exported for audit." |
| **1:55–2:00** | Back to the queue | "Clear on contradiction, confirm on agreement, and when in doubt, review, with the next step spelled out." |

## Points to make if there's extra time, or for Q&A

- **The LLM only reads text, it never decides.** It's called only when the patterns can't read a note. Every value it returns must appear in the note, and the check's result always comes from the note's own wording. On dev it isn't called at all.
- **Unknown stays unknown.** A place we can't map to a country, a placeholder name like "N/A", or an impossible date like 31 February can only lead to review, never to a clearance.
- **The customer side in more detail:** links, joint accounts, search for unlinked alerts, records merged by phone and DOB or by document number, and the latest approved identity check (from the KYC provider or a note).
- **The watchlist side in more detail:** listed DOBs; ages and "born on" sentences in the profile, but only about the listed person, never a relative or co-defendant; and search results filtered to the same listing and a country tied to the hit.

## Backup if something fails live

Record the screen once, cleanly, in advance. Screenshots of each step are a fallback: H-582410 (customer card, hit card, fact table), the queue, H-017810 band and evidence required, H-622EDD search results, the note drawer, and the blocked clear button.
