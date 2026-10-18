# Problem 2: Handbook Size and Cost Estimate

The Campus Customs Shop Handbook (`data/shop_handbook.md`) is sent to the model on every call my agent makes. This file estimates how many tokens it is and what it costs on its own. These are estimates; Problem 4 checks them against real runs.

## 1. Token count

| Measure | Value |
|---|---|
| Characters (exact file, including `\r\n` line endings) | 29,241 |
| Words | 6,127 |
| Lines | 338 |
| **Tokens (o200k_base)** | **10,069** |
| Characters per token | 2.90 |

**How we got it:** We ran `count_handbook_tokens.py`, which loads the handbook exactly as stored and encodes it with OpenAI's `tiktoken` library (v0.14.0). `tiktoken` has no entry for `gpt-6-luna`, so the script falls back to `o200k_base`. That is the encoding OpenAI's newest models use (GPT-4o and later). We then count the encoded tokens.

```bash
.venv/bin/python count_handbook_tokens.py
```

**How we double-checked it:**

- The extracted `data/shop_handbook.md` is byte-for-byte identical to the copy inside `data.zip`.
- The file is plain ASCII with no byte-order mark. That is why it has 29,241 bytes and 29,241 characters.
- Decoding the 10,069 tokens gives back the exact original file (round-trip check), so nothing was dropped or added.
- Four separate `tiktoken` methods all return 10,069: `encode`, `encode_ordinary`, `encode` with special-token checks turned off, and `encode_ordinary_batch`. The handbook contains no special tokens.
- `o200k_harmony`, the other current OpenAI encoding, also gives 10,069.
- The older `cl100k_base` encoding (GPT-4 / GPT-3.5) gives 10,191, about 1% more. So the count is not sensitive to which modern encoding is used.

**Line-ending catch:** The handbook uses Windows `\r\n` line endings. Python's default `read_text()` silently converts these to `\n`, which removes 338 characters and gives **10,058** tokens, 11 fewer than the true file. Our first pass made exactly this mistake. The script now opens the file with `newline=""` so it counts the file exactly as stored. When we build the agent, we must read the handbook the same way. Otherwise the real runs in Problem 4 will be about 11 tokens lower.

**Why 2.90 characters per token instead of the usual ~4:** The handbook is mostly markdown tables, codes, prices, dates, and email addresses (for example `orders@bluehen-apparel.example` and `|---|`). Text like this splits into more tokens than plain English prose.

## 2. Prices for gpt-6-luna (`data/prices.json`)

| Token type | $ per 1M tokens | $ per token |
|---|---|---|
| Input (not cached) | $0.10 | $0.0000001 |
| Cache write | $0.125 | $0.000000125 |
| Cached input (cache read) | $0.01 | $0.00000001 |
| Output | $0.50 | not used here (the handbook is input only) |

Formula: **cost = tokens × (price per 1M ÷ 1,000,000)**

All dollar amounts below are exact (computed with Python's `Decimal`, no rounding) unless marked "about."

## 3. Handbook cost without cached tokens

Every call pays the full input price for all 10,069 handbook tokens.

**One call:**
10,069 × $0.10 ÷ 1,000,000 = **$0.0010069** (about 0.1 cents)

**1,000 calls:**
1,000 × $0.0010069 = **$1.0069** (about $1.01)

## 4. Handbook cost with cached tokens

The handbook is identical on every call, and it is far above the 1,024-token minimum OpenAI needs before it will cache a prompt prefix. So after the first call it can be read from cache. The first call pays to **write** the cache, and every later call pays the much cheaper **cached read** rate.

**Call 1 (cache write):**
10,069 × $0.125 ÷ 1,000,000 = **$0.001258625**

**Each later call (cache read):**
10,069 × $0.01 ÷ 1,000,000 = **$0.00010069**

**One call:**
- If it is the first call (cache miss plus write): **$0.001258625**
- If the cache is already warm (cache hit): **$0.00010069**, which is 10× cheaper than uncached

**1,000 calls (1 write + 999 reads):**
$0.001258625 + 999 × $0.00010069
= $0.001258625 + $0.10058931
= **$0.101847935** (about $0.10)

## 5. Side-by-side summary

| Scenario | 1 call | 1,000 calls |
|---|---|---|
| No caching | $0.0010069 | $1.0069 |
| With caching (first call writes, rest read) | $0.001258625 first / $0.00010069 after | $0.101847935 |
| **Savings from caching** | n/a | **$0.905052065 (about 89.9% cheaper)** |

Savings math: $1.0069 − $0.101847935 = $0.905052065, and $0.905052065 ÷ $1.0069 = 89.9%.

Caching only loses on the very first call: $0.001258625 vs $0.0010069, so it costs $0.000251725 more. It breaks even on the second call:
- Cached: $0.001258625 + $0.00010069 = $0.001359315
- Uncached: 2 × $0.0010069 = $0.0020138

## 6. What to watch for when we check against real runs (Problem 4)

- **Real input tokens will be a bit higher than 10,069.** The API adds a few tokens of message formatting around the system prompt, and each call also includes the vendor document and instructions. The handbook-only number here is a lower bound on input tokens per call.
- **Cached tokens may come in a bit under 10,069.** OpenAI caches in steps of 128 tokens after the first 1,024. So the reported `cached_tokens` is the longest matching prefix rounded down to one of those steps.
- **Caches expire.** A cached prefix usually lasts only a few minutes when idle. Calls spread far apart may pay the write or uncached price again instead of the cheap read price.
- **Cache write price.** `prices.json` lists a $0.125/1M cache-write price, so the estimate above charges it on call 1. If the real runs show no write charge, call 1 is billed at the normal $0.10/1M rate instead. The 1,000-call cached total would then be $0.0010069 + $0.10058931 = **$0.10159621**, a difference of only $0.000251725.
- **Line endings.** If the agent reads the handbook with default text mode, `\r\n` becomes `\n` and the handbook drops to 10,058 tokens. That is a difference of 11 tokens, or $0.0000011 per uncached call.
