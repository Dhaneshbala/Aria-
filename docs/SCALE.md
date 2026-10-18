# ARIA at scale — what breaks, and what it actually costs

Single-user localhost ARIA cannot serve 10M people. This note maps the road
so nobody mistakes "works on my Mac" for "ready to launch".

## What breaks, by headcount

| Users | First breakage |
|---|---|
| 2+ on one box | `DATA_DIR` is global — chats/memories mix. Needs per-user data roots keyed by login. |
| 10+, LAN/shared | No login. `ARIA_API_TOKEN` (just added) covers a trusted group, not accounts. |
| 100+ | One Ollama queue (semaphore 2), one ChromaDB lock, JSON files with file locks. Throughput walls everywhere. |
| 1k+ | Need real auth (OAuth), per-tenant Postgres, object storage, request queueing, rate limits per user. |
| 100k+ | Model serving becomes the business: 12B needs ~10GB VRAM *per replica*; hundreds of concurrent chats need a GPU fleet (vLLM/TGI), autoscaling, and six-figure monthly GPU bills. |
| 10M | CDN, multi-region inference, safety/abuse pipelines, COPPA/GDPR-K for a Year-9 audience, support org. Different company. |

## Cost sketch (order of magnitude, 12B model)

- One concurrent chat ≈ one loaded replica ≈ ~$0.50–2/hr of GPU (A10G/L4 class).
- 10M *monthly active* with 1% concurrent ≈ 100k concurrent chats ≈ tens of millions $/month.
- Mitigations that actually move the number: smaller distilled models for easy queries, aggressive caching (quiz/notes are cacheable), queue + "thinking…" UX instead of instant for free tier.

## What to build first (if growth is real)

1. `ARIA_API_TOKEN` → real accounts (this gate is the seam to build on).
2. `DATA_DIR` → per-user roots (mechanical once identity exists).
3. ChromaDB → Postgres + pgvector (multi-writer safe).
4. Ollama → API-first model layer (swap local/Ollama/cloud per query type).
5. Everything else only when 1–4 are done.

## Honest recommendation

Grow in this order: family → classroom → school → public. Each step funds
the next and the architecture above arrives just in time, not prematurely.
