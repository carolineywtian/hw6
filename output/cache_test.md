# Problem 4: With and Without Cached Tokens

My vendor desk agent sends the same instructions and the 10,069-token handbook on every model call. This test measures what reusing that prefix from the provider's prompt cache is worth. I ran the agent on all 12 practice documents in two setups and saved every model call (72 calls) to `output/cache_test.json`.

- **Run:** 2026-10-17, 14:21 to 15:31, with `python cache_test.py`.
- **Model:** `gpt-6-luna` through Portkey. Every response came back from the `gpt-6-luna-global` deployment.
- **Prices (`data/prices.json`, per 1M tokens):** input $0.10, cached input $0.01, cache write $0.125, output $0.50.
- **Cost formula, per call:** (input − cached − cache write) × $0.10 + cached × $0.01 + cache write × $0.125 + output × $0.50, all ÷ 1,000,000. The API counts cached and cache-write tokens *inside* `input_tokens`, so they are split out and not charged twice.

---

## 1. The two setups, and proof that each does what it should

| Setup | How it is built (`agent.py`) | What the API reported |
|---|---|---|
| **With cache** | The instructions and handbook are byte-for-byte identical on every call. A cache breakpoint sits right after them (`openai_cache_instructions`), and all calls share one `prompt_cache_key`. The batch starts with its own label (`Cache group p4-4892b3b0`), so it begins with a cold cache, matching Problem 2's "1 write, then reads" model. | **369,009 of 411,454 input tokens (89.7%) were read from cache.** After the first document, a typical call 1 read **11,119** tokens from cache and wrote only about 20. |
| **Without cache** | A brand-new random ID is put at the very start of the instructions on **every** call. Prompt caching only reuses an exact matching prefix, so no call can match an earlier one. | **0 cached tokens on all 36 calls.** |

**Professor's rule ("a without-cache run that still shows cached tokens does not count"):** `cache_test.py` checks every no-cache call automatically. The result in `cache_test.json` is `"no_cache_calls_with_cached_tokens": []` and `"no_cache_setup_valid": true`.

**Every call was a real model call.** Portkey, the gateway, keeps its own saved copies of earlier responses and can return one instead of calling the model (see Surprise 1). Every call in this test sent `x-portkey-cache-force-refresh: true`, and Portkey reported `REFRESH` on all 72 calls (`"all_calls_real": true`). None of these numbers are replays.

**Accuracy did not change:** 12/12 correct with cache and 12/12 without. No trap tool fired in either setup.

---

## 2. Total cost, cost per document, and percent saved

| | With cache | Without cache |
|---|---|---|
| Documents (model calls) | 12 (36) | 12 (36) |
| Input tokens | 411,454 | 412,182 |
| of which cached (read) | 369,009 | **0** |
| of which cache write | 37,909 | 407,646 |
| of which plain uncached | 4,536 | 4,536 |
| Output tokens | 2,089 | 1,998 |
| **Total cost** | **$0.00992681** | **$0.05240836** |
| **Cost per document** | **$0.00082723** | **$0.00436736** |
| Cost per model call | $0.00027574 | $0.00145579 |

**Saved:** $0.05240836 − $0.00992681 = **$0.04248155**, and $0.04248155 ÷ $0.05240836 = **81.06% cheaper with cache.**

### Per document

| Document | With cache: cached / write | With cache: cost | Without cache: cached / write | Without cache: cost |
|---|---|---|---|---|
| p01_bluehen_quote.html | 22,445 / 11,491 | $0.00177662 | 0 / 33,992 | $0.00435330 |
| p02_elmcity_quote.html | 22,404 / 11,492 | $0.00177034 | 0 / 33,962 | $0.00437655 |
| p03_ivyprint_catalog.html | 33,539 / 373 | $0.00051132 | 0 / 33,968 | $0.00435230 |
| p04_harborstitch_quote.html | 33,562 / 370 | $0.00050117 | 0 / 33,982 | $0.00436755 |
| p05_maplemills_quote.pdf | 33,533 / 347 | $0.00050650 | 0 / 33,990 | $0.00440405 |
| p06_qtextile_quote.pdf | 33,522 / 362 | $0.00048977 | 0 / 33,940 | $0.00436330 |
| p07_longwharf_quote.pdf | 33,526 / 340 | $0.00051206 | 0 / 33,927 | $0.00436818 |
| p08_chapelst_email.eml | 22,448 / 11,491 | $0.00178065 | 0 / 33,992 | $0.00435480 |
| p09_westville_email.eml | 33,399 / 536 | $0.00053879 | 0 / 34,032 | $0.00439480 |
| p10_eastrock_email.eml | 33,586 / 391 | $0.00051004 | 0 / 34,034 | $0.00436055 |
| p11_yorkst_quote.html | 33,532 / 392 | $0.00053262 | 0 / 33,931 | $0.00435118 |
| p12_bluehen_quote.pdf | 33,513 / 324 | $0.00049693 | 0 / 33,896 | $0.00436180 |
| **Total** | **369,009 / 37,909** | **$0.00992681** | **0 / 407,646** | **$0.05240836** |

**Three with-cache documents cost about 3.5× the others.** p01, p02, and p08 each had one call that found nothing in the cache:

- p01 call 1 was the expected cold start.
- p02 call 2 and p08 call 1 were unexpected misses (Surprise 5).

Each miss rewrote about 11,100 tokens at the write price. On the other **9 documents, with no miss, the average was $0.00051102 per document, 88.30% cheaper than without cache.**

---

## 3. Real numbers vs my Problem 2 estimate

Problem 2 estimated the **handbook alone, per model call**: 10,069 tokens, costing $0.0010069 uncached, $0.00010069 as a cached read, or $0.001258625 as a cache write.

| | Problem 2 estimate | Real (this test) | Real ÷ estimate |
|---|---|---|---|
| Input tokens per call (call 1) | 10,069 (handbook only) | 11,265 average | 1.12× |
| Tokens read from cache on a warm call 1 | 10,069 | 11,119 | 1.10× |
| Cost per call, **no cache** | $0.0010069 | $0.00145579 | **1.45×** |
| Cost per call, **warm cache** (call 1) | $0.00010069 | $0.00013333 | **1.32×** |
| 1,000 calls, no cache | $1.0069 | $1.4558 | 1.45× |
| 1,000 calls, with cache | $0.1018 | $0.2757 | 2.71× |
| Percent saved by caching | 89.9% | **81.06%** measured, **88.30%** on documents with no cache miss | |

**Where the token gap comes from.** Each real call 1 is about 11,265 tokens:

| Part | Tokens |
|---|---|
| Handbook (the Problem 2 count) | 10,069 |
| `prompt.md` instructions | 727 |
| Tool definitions, the output schema, and message formatting | about 445 |
| The user message | 15 |
| The cache-group label | 9 |

Calls 2 and 3 also carry the document text (about 110–145 tokens) and the earlier turns, so input grows to about 11,600. All of the extra prefix is cacheable too, which is why a warm call reads 11,119 cached tokens, not just 10,069.

**Why "no cache" costs 45% more per call than estimated:**

- About 12% of that is the extra tokens above.
- Problem 2 assumed uncached tokens are billed at the plain $0.10 input price. In reality the API **writes every uncacheable prompt to the cache at $0.125** (Surprise 2), which adds about 24%.
- Output tokens add the rest.

**Why "with cache" costs more than estimated:**

- Problem 2 counted one handbook write per 1,000 calls. This test had 3 cache writes in only 36 calls.
- Every call also writes its new tail, about 20–350 tokens, at the write price.
- Output tokens (10.5% of the with-cache cost) cannot be cached at all.

**The biggest difference:** Problem 2 priced **one call**, but each document takes **three calls**:
1. read the document
2. check the rules
3. return the answer

So the handbook is sent three times per document, and a real document costs about 3× Problem 2's per-call number.

---

## 4. Projection: 1,000 documents a day for 30 days (30,000 documents)

Based on the measured cost per document from this test:

| | Per document | Per day (1,000) | **30 days (30,000)** |
|---|---|---|---|
| Without cache | $0.00436736 | $4.37 | **$131.02** |
| With cache, measured average (includes the 3 cold or missed calls) | $0.00082723 | $0.83 | **$24.82** |
| With cache, steady state (9 documents with no miss) | $0.00051102 | $0.51 | **$15.33** |
| **Saved by caching** | | $3.54 to $3.86 a day | **$106.20 (81.1%) to $115.69 (88.3%)** |

**Why the real number should land near the steady-state row.** At 1,000 documents a day, a document arrives about every 30–90 seconds (every 36 seconds across a 10-hour workday, every 86 seconds across 24 hours). The cache keeps a prefix for at least 30 minutes, so it should almost never go cold. Each cold write or miss costs only about $0.0013 extra, the difference between a missed call ($0.0014) and a warm one ($0.00013). Even 50 misses a day would add only about $0.07 a day, or $2 a month.

**What would change this projection:**

- **Any edit to `prompt.md` or the handbook** creates a new prefix and one fresh cold write. That is a trivial cost.
- **Longer documents** add uncached tokens to calls 2 and 3. The practice documents are only 110–145 tokens each.
- **A price change in `prices.json`** scales everything.

---

## 5. Surprises in the numbers, and why they happen

1. **Portkey replayed saved answers, token counts included.** Before this test, a "fresh" p08 run returned *exactly* the same token counts, call for call, as a p08 run from 13:52. Portkey's header said `x-portkey-cache-status: HIT`. Portkey, the gateway between my code and the model, keeps its own copy of earlier responses and sends one back when a request matches, without calling the model. That is a different cache from the model's prompt cache, and it makes a run look real when it is not. Five earlier logged runs were replays, including the two Problem 3 proof runs. They are now marked `portkey_replay: true` in `usage_log.json`, and the Problem 3 proof was re-run. Every call now sends `x-portkey-cache-force-refresh: true`, and the logs record Portkey's status per call.

2. **"Without cache" cost more than plain input.** The no-cache setup paid **$0.05240836**. If its input had been billed at the plain $0.10 price, it would have cost $0.04221720. The provider still **writes** every new prompt into the cache, at $0.125/1M, even though my random ID guarantees nothing will ever read it back. That is a **24.1% premium**. There is no setting to stop the writes: I also tried the API's "explicit" cache mode (Surprise 3), and it still wrote about 11,100 tokens per call. So turning caching "off" is worse than never having caching. You pay the write fee with no reads to make up for it.

3. **The API's "explicit" cache mode did not turn caching off.** PydanticAI exposes `openai_prompt_cache_options={"mode": "explicit"}`, which is documented to cache only at breakpoints you set. With no breakpoints set, real calls still read about 11,100 cached tokens each. That would have broken the professor's rule, so the no-cache setup uses the random-ID method instead, and the API's own numbers show it works.

4. **At first, the cache only worked *within* one document.** My first with-cache attempt (batch `p4-ec56082f`, 4 documents, stopped early and kept in `usage_log.json`) paid a full 11,500-token cache write on **every** document's first call. The newer cache stores entries at "breakpoints", and by default the only breakpoint is at the very end of each prompt. The end of the prompt includes the document-specific message, so the next document never matched. Calls 2 and 3 of the *same* document did match, because they extend call 1's exact prompt. Adding a breakpoint right after the instructions and handbook (`openai_cache_instructions`) fixed it. From then on, the next document's call 1 read 11,119 tokens from cache.

5. **The cache missed twice even while warm.** p02's call 2 and p08's call 1 read 0 cached tokens, even though the documents before and after them hit. Prompt caches live on individual servers. `prompt_cache_key` makes it *likely*, but not certain, that a request lands on the server holding the cache. Each miss cost about $0.0013 extra and dropped the measured savings from 88.3% to 81.1%.

6. **One document costs three calls.** The agent:
   1. calls `read_document`
   2. calls `check_purchasing_rules`
   3. returns the structured answer

   Each step is a separate model call that resends the instructions and handbook. Caching matters three times as much as Problem 2's one-call picture suggests.

7. **Caching even reuses the earlier turns.** In with-cache runs, the cached count *grows* across a document's calls. For p04 it went from 11,119 to 11,141 to 11,302. The cache matches the whole earlier prompt, including the tool call and the document text from call 1, not just the handbook.

8. **The API was sometimes very slow, and the cache survived it.** The p08 run (with cache) started at 14:28 and the next document did not start until 15:17. That 49-minute run was almost all API wait time. p09 still found the handbook in cache. The no-cache half ran 12 documents in about 12 minutes.

9. **Output is now a real share of the cost.** Output tokens cost 5× input, and caching cannot reduce them. They are only 0.5% of tokens but **10.5% of the with-cache cost** ($0.00104), so in a cached system the next savings would come from shorter outputs, not shorter prompts.
