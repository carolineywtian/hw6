# HW6: Campus Customs Vendor Desk Agent

An AI agent that reads one vendor document (an HTML quote, a PDF, or an email) and reports the vendor, SKU, unit price, lead time, minimum order, and a **recommend / do_not_recommend** decision based on the Campus Customs Shop Handbook. It is built with PydanticAI on `gpt-6-luna` through Portkey.

It is defended against booby-trapped documents at three levels:

- **Code:** only the text a person would see reaches the AI.
- **Design:** the AI only copies five facts. Code makes the decision and writes the reason, and the AI never holds the email or payment tools.
- **Prompt:** security rules in `prompts/prompt.md`.

**Results at a glance** (open `output/hw6_report.html` in any browser; no internet needed):

- Caching made each document 81% cheaper.
- Booby-trapped documents that fooled the agent: 4 of 12 without defenses, 0 of 12 with them.
- The defended agent is also the cheapest setup.
- 10 exam documents processed with 0 trap calls.

---

## Run my agent

Built and tested with Python 3.14 on macOS.

```bash
git clone https://github.com/carolineywtian/hw6.git
cd hw6
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then open .env and paste your own PORTKEY_API_KEY
```

Run the defended agent on one vendor document:

```bash
python agent.py --doc data/practice_docs/p01_bluehen_quote.html
```

It prints the tool calls, anything the code layer removed or flagged, the answer, and the token counts and cost. Every run is appended to `output/usage_log.json` and `output/audit_trail.json`.

**Options:**

| Command | What it runs |
|---|---|
| `python agent.py --doc <file>` | The final defended agent (all three layers). This is the default. |
| `python agent.py --doc <file> --no-defenses` | The undefended agent (Problem 7): reads the raw file, holds all four tools, and decides itself. |
| `python agent.py --doc <file> --layers code,prompt` | Any mix of the `code`, `design`, and `prompt` layers (Problem 6). |
| `python agent.py --doc <file> --no-cache` | Makes every request uncacheable (Problem 4). |

Any file in `data/practice_docs/`, `data/exam_docs/`, or `data/my_attacks/` works as `--doc`. The correct answers for the practice documents are in `data/practice_key.json`.

`send_email` and `approve_payment` are fake "trap" tools. They never send or pay anything; they only record the call in `output/trap_calls.json`. For my agent, that file has stayed `[]`.

## Re-run the experiments

Each script writes the output files listed next to it. Every run makes real model calls (a few cents in total) and appends to the logs.

| Problem | Command | Writes |
|---|---|---|
| 2 | `python count_handbook_tokens.py` | prints the token count used in `output/handbook_estimate.md` |
| 4 | `python cache_test.py` | `output/cache_test.json` (the write-up is `output/cache_test.md`) |
| 5 | `python person_view.py` then `python attack_test.py` | `output/person_view/`, `output/attack_results.json` |
| 6 | `python defense_test.py` | `output/defense_results.json` |
| 8 | `python exam_test.py` | `output/exam_results.json` (read-only) + `output/exam_results_provenance.json` |
| 8 | `python exam_test.py --verify` | checks that `exam_results.json` exactly matches the logged runs and was not edited (no API calls) |
| 9 | `python build_report.py` | `output/hw6_report.html`, rebuilt from the saved results |

**Notes:**

- `person_view.py` and `ocr.swift` (the "what a person sees" check in Problem 5) need macOS and Google Chrome.
- Re-running `exam_test.py` replaces my submitted exam results. To check them without changing anything, use `--verify`.

## Where things are

| Path | What it is |
|---|---|
| `AI_prompts.md` | Every prompt I gave my vibe coder, problem by problem |
| `agent.py`, `tools.py`, `models.py`, `prompts/prompt.md` | The agent (Problem 3), with the Problem 4 cache setups and the Problem 6 defenses |
| `prompt_undefended.py` | The no-defenses prompt used by `--no-defenses` |
| `data/` | Course data (handbook, prices, practice key, 12 practice docs, 10 exam docs) + my 2 red-team attacks in `data/my_attacks/` |
| `output/harness.md` | How the agent is built: the Safety section, every field and tool, and notes for each problem |
| `output/*.md` | Write-ups: handbook estimate, caching, attacks, defenses, red team |
| `output/*.json` | Raw results and logs |
| `output/hw6_report.html` | One-file results page |

## Keeping the key safe

My real `.env` is not in this repo: `.gitignore` keeps it out. `.env.example` has a placeholder only. Put your own key in `.env`, and the agent finds it there or in any parent folder.
