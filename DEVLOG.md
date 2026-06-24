# Agent Flight Recorder — Dev Log

_A timeline of what I built, broke, fixed, and learned. Most recent first._

## 2026-06-23 — M1.3: traces POST to the API + thinking capture

**Built:**
- `afr/client.py` `post_run()`: serializes a `Run` with `model_dump(mode="json")` and POSTs it to the collector over `httpx.AsyncClient`. Wired into `record_subject.py` (dump-then-post, so a local JSON copy survives even if the POST fails).
- `POST /runs` is now idempotent: wipe-and-reinsert on a duplicate `run.id` (`session.get` → `delete` → `flush` → re-add), all in one transaction. Cascade handles the child spans.
- Per-run span ordering via a real `sequence` column: a per-run `itertools.count()` numbers spans at *creation* time, threaded through schema → DB → API, with `order_by="SpanRow.sequence"` on the relationship.
- `ThinkingBlock` capture: the model's reasoning now lands in `llm_span.output["thinking"]` instead of being dropped — the "cockpit voice recorder" signal.
- Cleanups: `metadata` is now always-a-dict (dropped the dead `is None` guard), and `db.py`'s `output` hint matches its nullable column.

**Bugs & fixes:**
- `session.flush` with no parentheses — I referenced the method instead of calling it, so the flush silently never ran and a re-POST would self-collide on the primary key. The `x.method` vs `x.method()` trap fails with zero error. Added the `()`.
- I put `seq = itertools.count()` at *module* scope — so the counter was shared across every run and leaked numbers between them (and wasn't concurrency-safe). Moved it inside `record_run` so each run gets a fresh counter from 0.
- My first `ThinkingBlock` branch skipped the `if output is None` guard the `TextBlock` branch had — so it crashed (`None.setdefault`) on *pure-thinking turns*, which were the exact spans I was trying to fix. Added the guard.
- First version dumped thinking into `output["text"]`, blending reasoning with the model's actual answer. Gave it its own `thinking` key so the two stay distinguishable.

**Learned:**
- Idempotency is a property of the *write endpoint*, but HTTP is what makes it *necessary* — the lost-response-then-retry failure only exists over a network. In-process calls don't have that ambiguity.
- Why "one transaction" for wipe-and-reinsert is correctness, not tidiness: atomicity means I can lose the *update* but never lose the *data* — a crash between delete and insert rolls back, so I never end up with the old run gone and nothing in its place. (The "A" in ACID.)
- Order should be a DB *guarantee* (`ORDER BY`/`order_by`), not a reliance on insertion order — and a monotonic sequence number beats `started_at` because wall-clock timestamps can tie.
- A flight recorder is really two halves: in-process *instrumentation* (has to be, to watch the stream) shipping to an out-of-band *collector* over HTTP. That split is what makes it framework-agnostic.
- State belongs at the narrowest scope that needs it — the module-level counter bug was that lesson in miniature.

**Decisions:**
- Transport is HTTP, not an in-process call — decoupling, production-realistic (like OTel/Sentry collectors), and language/framework-agnostic for the future LangGraph agent.
- `post_run` raises on a failed POST (fail loud in dev) rather than swallowing — a recorder must never *silently* lose data. Buffer/retry is a later refinement.
- Upsert is wipe-and-reinsert for now; noted that mutating evidence conflicts with the audit north star — the eventual answer is append-only/immutable records (revisit ~M4).
- Capturing thinking matters *more* for AFR than for generic observability — reasoning is the most audit-relevant signal, so it gets its own key, separate from the answer.

**Next:** GitHub Actions workflow (lint on push), then commit/push M1.2 + M1.3. Open follow-ups: `RedactedThinkingBlock` capture, an explicit `httpx` timeout, and the first real `pytest` (fake stream → assert span tree) so CI has something meaningful to run.

## 2026-06-17 — M1.2: tracer `record_run` maps the SDK stream to a Run

**Built:**
- `afr/tracer.py` `record_run()`: consumes the Claude Agent SDK message stream and assembles a `Run`. Correlates split tool-call/result via `pending[tool_use_id]`, builds the llm/tool span tree, finalizes at `ResultMessage`. Wrapped the stream loop in try/except/finally so the run always finalizes.
- `examples/record_subject.py`: drives the subject agent through `record_run()` and saves the assembled trace to `traces/<id>.json`.
- `.gitignore`: ignore `traces/` (local sample data); cleaned up a stray `EOF` line.

**Bugs & fixes:**
- `pending.pop(tool_use_id)` could `KeyError` on an orphan result and abort the whole run — a recorder must never crash the flight. Fixed with `pop(id, None)` + a guard that logs the orphan to `metadata` and continues.
- `run.metadata = message.data` dumped the SDK's entire init blob and rebound to its dict. Curated it to `{model, session_id}` merged into my own dict via `.update()`.
- `output["reason_text"] = block.text` overwrote on multiple `TextBlock`s. Switched to `setdefault("text", []).append(...)` so I accumulate every fragment.

**Learned:**
- The whole theme of these three bugs was the same mistake in different costumes: a recorder silently losing or fabricating data. The fix in each case was swapping a "crash or clobber" operation for a "degrade and accumulate" one (`.pop(k, None)`, `.get`, `.setdefault`).
- `is None` vs `== None`, and that `setdefault`'s default is evaluated every call.
- Custom slash commands live in a `commands/` folder; `!` injects bash output at fire-time; `$ARGUMENTS` passes input.

**Decisions:**
- `Run.metadata` is curated known fields, not an unbounded vendor dump — so my stored shape doesn't drift with the SDK (matters for the audit-evidence north star).
- Traces save locally to `traces/<id>.json` for now; the database (M1.3) becomes the real home.

**Next:** M1.3 — POST the assembled run to `/runs`. Also two open findings: empty llm spans where `ThinkingBlock`s went uncaptured, and llm-span timestamps that measure parse time, not inference time.
