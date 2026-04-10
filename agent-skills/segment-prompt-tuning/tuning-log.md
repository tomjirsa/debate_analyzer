# Prompt tuning session log

Append one line per completed segment when you want a paper trail: `date`, `uid`, `iterations`, `pass/fail`, short note.

Example:

- 2025-03-27 | `b04e88d7-...` | 3 | pass | tightened anti-hallucination wording
- 2025-03-27 | `94883fd1-6c5a-476d-abc7-cdb8e70aab77` | 1 | partial | Ollama qwen2.5:7b; fixes baseline English/hallucination; stray token "Suggestuje" in summary
- 2025-03-27 | draft v3 + `94883` / `5ec20f1f` | 3 | pass | Added Czech-only + no-inference + no-fabricated-votes + spelling; merged into `prompts.py` `PROMPT_SEGMENT_SUMMARY`

## 2025-03-27 — 10 rounds × 10 segments (current `segment_summary_prompt_draft.txt`, Ollama `qwen2.5:7b`, `LLM_MAX_MODEL_LEN=65536`)


| Round | uid (prefix) | Rubric   | Notes                                                                                              |
| ----- | ------------ | -------- | -------------------------------------------------------------------------------------------------- |
| 1     | `b04e88d7`   | pass     | Program, čas jednání, 1a, Dům zdraví / studie; Czech OK                                            |
| 2     | `89bd6ffd`   | pass     | Výběrové řízení KCL, dočasný výkon ředitele; Czech OK                                              |
| 3     | `29f71baf`   | **fail** | Hallucinated role (“Sedlákův smluvní poslanec”); transcript is hlasování o jednací době + Sedláček |
| 4     | `5ec20f1f`   | pass     | Technická poznámka, **svolat** MJZ, dotazy v 17:00                                                 |
| 5     | `94883fd1`   | partial  | Czech OK; “Rozhodují” is strong vs transcript (domluva o čase)                                     |
| 6     | `98b452a6`   | pass     | Dotazy nejpozději v 17:00, lze dřív                                                                |
| 7     | `688cc7d0`   | partial  | Core OK; “Zendulky” vs Zendulka; časový rámec “nebyl sválen” ASR-heavy                             |
| 8     | `14baf0ec`   | **fail** | Garbled opener (“Sprezření odborníků”); v transcriptu vítání odborníků + Proluce                   |
| 9     | `075b55d9`   | partial  | Architekti, debata; shortened                                                                      |
| 10    | `7bd31742`   | pass     | Studie náměstí Krále IV., polifunkce, lékaři                                                       |


**Follow-ups:** Short procedural segments (round 3) still confuse entity names; consider stricter “use only names and roles as in the segment” or post-processing. Round 8 shows garbled first sentence; may need stronger “first sentence must be grammatical Czech” or model with better Czech.

## 2025-03-27 — sequential run over all 20 test segments (`sequential_tune_experiment.py`)

- Automated gates (no English regex hits, 3–8 keywords): **20/20 pass** on first run (heuristic does not catch hallucinations or garbled Czech).
- Merged three strengthener rules into `segment_summary_prompt_draft.txt` and `src/debate_analyzer/analysis/prompts.py` `PROMPT_SEGMENT_SUMMARY` anyway (names/roles, grammatical opener, short procedural segments).

## 2026-04-10 — `merge_speaker_prompt` (Ollama `qwen2.5:7b`, `test_llm_analysis.json`)

- **True same-speaker partials:** v `test_llm_analysis.json` nejsou žádné **3+** po sobě jdoucí segmenty se stejným `speaker`; jsou jen **dva** páry indexů `(20,21)` a `(68,69)` se stejným řečníkem. Pro ladění speaker-merge použij `--start 20 --count 2` nebo `--start 68 --count 2`. Delší seznamy stejného řečníka vyžadují jiný export nebo rozšíření CLI.
- **CLI:** `run_merge_summaries.py --analysis data/test/test_llm_analysis.json --start 20 --count 2 --prompt-file …/merge_speaker_prompt_draft.txt`
- **Změny promptu:** výhradně jeden řečník (jednotné číslo); zákaz přičítat cizí stanoviska; stejné modality jako u transcript merge (žádné neurčité „bylo hlasováno“); latinka bez cyrilice; diakritika + kontrola keywords; singular vs „řečníci“ pro jeho vlastní výroky.
- **Spot-check:** `qwen2.5:7b` občas stále v keywords opakuje tvary bez háčků u „světlá výška“ / „minimální“ — modelová limit; souhrn je většinou v pořádku.
- **Merged into:** `src/debate_analyzer/analysis/merge_speaker_prompt.txt` a oba drafty (`agent-skills` + `.cursor/skills`).

## 2026-04-10 — `merge_transcript_prompt` (Ollama `qwen2.5:7b`, `test_llm_analysis.json`)

- **CLI:** `run_merge_summaries.py --analysis data/test/test_llm_analysis.json --start 0 --count 8 --prompt-file …/merge_transcript_prompt_draft.txt`
- **Issue:** first run mixed Cyrillic into a word („navrhнутa“); partials were segment summaries, not true per-speaker merges, but still valid stress test.
- **Prompt changes:** dedupe repeated themes across partials; forbid vague „bylo hlasováno/schváleno“ when inputs only propose; **Latin Czech only** (no Cyrillic / mixed-script words); examples for cases („pozice ředitele“, „zákonem o obcích“); keywords must be natural phrases (no broken inflection).
- **Merged into:** `src/debate_analyzer/analysis/merge_transcript_prompt.txt` and drafts (`agent-skills` + `.cursor/skills`).

## 2025-03-27 — merge prompts (`merge_*_prompt.txt`: segment chunk, speaker, transcript)

- **Stress:** `run_merge_summaries.py --start 5 --count 5` on `test_llm_analysis.json` (multi-speaker window).
- **Changes:** multi-actor / neutral wording (avoid single „řečník“ for mixed partials); modality for votes/approval; keyword count ~5–15; grammar + explicit example „řečníci navrhují“ vs „navrhuji“; copy names from partials.
- **Spot-check (qwen2.5:7b):** after v3, output uses „Řečníci navrhují…“; remaining minor issues (e.g. „Zaslal“ without subject) depend on model.

