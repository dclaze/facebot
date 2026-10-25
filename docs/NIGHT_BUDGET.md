# Halloween night budget — 2026-10-25

The deployed voice pipeline uses local speech recognition, Ollama dialogue and
local speech synthesis. Vision integration also uses local inference. Inference
service charges are **$0**. Existing hardware, electricity and internet are not
free, but no incremental purchase or paid API fallback is authorized. Electricity
cost needs measured combined watts and the owner's marginal electricity rate;
formula: watts /1000 ×12hours ×price/kWh. No power reading has been taken.

## Workload scenarios

Planning assumptions, not measured visitor behavior:3000 visitors, average group
size4, one active ghost,12hours. This gives750 encounters. Include25% headroom for
repairs, interrupted attempts and spontaneous comments. Group replies may address
several people at once; visitor count is not model-call count.

| Scenario | Replies/group | Base replies | Budgeted generation attempts | Local service fees |
|---|---:|---:|---:|---:|
| Light | 2 | 1500 | 1875 | $0 |
| Planning | 4 | 3000 | 3750 | $0 |
| Busy | 8 | 6000 | 7500 | $0 |

If average group size is2, double these counts. If everyone interacts separately,
multiply by4. Peak crowd bursts, overlap, real voice latency and thermal limits
matter more than the average. The busy case is not a demonstrated capacity. The
12-hour actual-device soak remains required. Local image sampling consumes compute
and electricity but no per-image paid inference budget.

## Optional Codex trial is separate

Only bounded synthetic subscription probes have been evaluated. Two runtime
probes consumed22761 input and54 output tokens total. The lean probe used5144
input tokens,25 output tokens and4301ms from CLI start to complete text; the
baseline was17617 input/29 output and3529ms. These are two samples, not a latency
percentile, acoustic result or allowance calibration. No live visitor cloud mode
is enabled by this estimate.

Extrapolating the **measured lean CLI** workload, without assuming prompt caching:

| Scenario | Input tokens | Output tokens |
|---|---:|---:|
| Light + headroom | 9,645,000 | 46,875 |
| Planning + headroom | 19,290,000 | 93,750 |
| Busy + headroom | 38,580,000 | 187,500 |

A supported compact provider could reduce this, but a1000-token local prompt does
not prove a1000-token hosted harness. A1536-token total-input ceiling, if actually
verified on that provider, would cap the planning case at5,760,000 input tokens.
Prepared local replies reduce model calls, but are not generated-latency evidence.

**Subscription percentage cannot be derived reliably from these token totals.**
OpenAI documents that model, context, reasoning, tool use and caching affect
allowance, and that credit rates do not directly determine included subscription
usage. Check the account's actual limits; don't convert API prices or credit rates
into remaining subscription percent. [Official pricing/usage guidance](https://learn.chatgpt.com/docs/pricing).

No reset credits, API billing or paid fallback. Local remains the night-of default
until a supported trial establishes quality, latency, bounded context and a safe
allowance cap; the present CLI timings do not meet the conversation target.

## Tracking

`scripts/codex-usage.py` performs a model-free account read and writes ignored
numeric receipts to `.local/codex-usage.json` and `.local/codex-usage-history.jsonl`.
Run at implementation milestones and before long runs. Shared account percentage
includes all chats. Its known nested-run receipt totals are a partial development
ledger, not total Facebot attribution or a visitor-runtime bill. Keep runtime
probes separately labeled. Latest check22:55:48UTC:69%remaining; preserve5%, start
no discretionary work at7%. No credit redemption. Recheck immediately before the
event; today's quota is not a promised Halloween balance.
