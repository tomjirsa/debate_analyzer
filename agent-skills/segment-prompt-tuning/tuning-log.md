# Prompt tuning session log

Append one line per completed segment when you want a paper trail: `date`, `uid`, `iterations`, `pass/fail`, short note.

Example:

- 2025-03-27 | `b04e88d7-...` | 3 | pass | tightened anti-hallucination wording

- 2025-03-27 | `94883fd1-6c5a-476d-abc7-cdb8e70aab77` | 1 | partial | Ollama qwen2.5:7b; fixes baseline English/hallucination; stray token "Suggestuje" in summary

- 2025-03-27 | draft v3 + `94883` / `5ec20f1f` | 3 | pass | Added Czech-only + no-inference + no-fabricated-votes + spelling; merged into `prompts.py` `PROMPT_SEGMENT_SUMMARY`

## 2025-03-27 — 10 rounds × 10 segments (current `segment_summary_prompt_draft.txt`, Ollama `qwen2.5:7b`, `LLM_MAX_MODEL_LEN=65536`)

| Round | uid (prefix) | Rubric | Notes |
|------:|--------------|--------|--------|
| 1 | `b04e88d7` | pass | Program, čas jednání, 1a, Dům zdraví / studie; Czech OK |
| 2 | `89bd6ffd` | pass | Výběrové řízení KCL, dočasný výkon ředitele; Czech OK |
| 3 | `29f71baf` | **fail** | Hallucinated role (“Sedlákův smluvní poslanec”); transcript is hlasování o jednací době + Sedláček |
| 4 | `5ec20f1f` | pass | Technická poznámka, **svolat** MJZ, dotazy v 17:00 |
| 5 | `94883fd1` | partial | Czech OK; “Rozhodují” is strong vs transcript (domluva o čase) |
| 6 | `98b452a6` | pass | Dotazy nejpozději v 17:00, lze dřív |
| 7 | `688cc7d0` | partial | Core OK; “Zendulky” vs Zendulka; časový rámec “nebyl sválen” ASR-heavy |
| 8 | `14baf0ec` | **fail** | Garbled opener (“Sprezření odborníků”); v transcriptu vítání odborníků + Proluce |
| 9 | `075b55d9` | partial | Architekti, debata; shortened |
| 10 | `7bd31742` | pass | Studie náměstí Krále IV., polifunkce, lékaři |

**Follow-ups:** Short procedural segments (round 3) still confuse entity names; consider stricter “use only names and roles as in the segment” or post-processing. Round 8 shows garbled first sentence; may need stronger “first sentence must be grammatical Czech” or model with better Czech.

## 2025-03-27 — sequential run over all 20 test segments (`sequential_tune_experiment.py`)

- Automated gates (no English regex hits, 3–8 keywords): **20/20 pass** on first run (heuristic does not catch hallucinations or garbled Czech).
- Merged three strengthener rules into `segment_summary_prompt_draft.txt` and `src/debate_analyzer/analysis/prompts.py` `PROMPT_SEGMENT_SUMMARY` anyway (names/roles, grammatical opener, short procedural segments).

## 2025-03-27 — merge prompt (`merge_summaries_prompt.txt`)

- **Stress:** `run_merge_summaries.py --start 5 --count 5` on `test_llm_analysis.json` (multi-speaker window).
- **Changes:** multi-actor / neutral wording (avoid single „řečník“ for mixed partials); modality for votes/approval; keyword count ~5–15; grammar + explicit example „řečníci navrhují“ vs „navrhuji“; copy names from partials.
- **Spot-check (qwen2.5:7b):** after v3, output uses „Řečníci navrhují…“; remaining minor issues (e.g. „Zaslal“ without subject) depend on model.
