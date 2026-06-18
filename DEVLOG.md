# Agent Flight Recorder — Dev Log

_A timeline of what I built, broke, fixed, and learned. Most recent first._

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
