"""Problem 2: count the tokens in data/shop_handbook.md and price them with data/prices.json."""

import json
from pathlib import Path

import tiktoken

HERE = Path(__file__).resolve().parent
MODEL = "gpt-6-luna"

# newline="" keeps the file's \r\n line endings exactly as stored; default text mode would
# silently turn them into \n and undercount by 11 tokens.
with open(HERE / "data" / "shop_handbook.md", encoding="utf-8", newline="") as f:
    handbook = f.read()
prices = json.loads((HERE / "data" / "prices.json").read_text(encoding="utf-8"))[MODEL]

# tiktoken has no mapping for gpt-6-luna, so fall back to o200k_base (OpenAI's newest encoding).
try:
    enc = tiktoken.encoding_for_model(MODEL)
except KeyError:
    enc = tiktoken.get_encoding("o200k_base")

tokens = len(enc.encode(handbook))
print(f"encoding:   {enc.name}")
print(f"characters: {len(handbook):,}")
print(f"words:      {len(handbook.split()):,}")
assert enc.decode(enc.encode(handbook)) == handbook, "round-trip failed"
print(f"tokens:     {tokens:,}")
print(f"chars/token: {len(handbook) / tokens:.2f}")

per_token = {k: v / 1_000_000 for k, v in prices.items()}
uncached_1 = tokens * per_token["input_per_1m"]
write_1 = tokens * per_token["cache_write_per_1m"]
read_1 = tokens * per_token["cached_input_per_1m"]

print(f"\nno cache, 1 call:        ${uncached_1:.6f}")
print(f"no cache, 1000 calls:    ${uncached_1 * 1000:.4f}")
print(f"cache write (call 1):    ${write_1:.6f}")
print(f"cache read (each later): ${read_1:.6f}")
print(f"cached, 1000 calls:      ${write_1 + 999 * read_1:.4f}")
