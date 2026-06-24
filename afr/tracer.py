# afr/tracer.py
from datetime import datetime, timezone
from claude_agent_sdk import (
    query, ClaudeAgentOptions,
    AssistantMessage, TextBlock, ToolUseBlock,
    UserMessage, ToolResultBlock, ResultMessage, SystemMessage, ThinkingBlock
)
from afr.schemas import Run, Span, SpanType, RunStatus
import itertools


def _now():
    return datetime.now(timezone.utc)

async def record_run(agent_name: str, task: str, options: ClaudeAgentOptions) -> Run:
    seq = itertools.count()
    run = Run(agent_name=agent_name,
            started_at=_now(),
            input={"task": task}
            )  
    pending: dict[str, Span] = {}      # tool_use_id -> the open tool_call span
    try:
        async for message in query(prompt=task, options=options):
            if isinstance(message, SystemMessage):
                run.metadata.update({
                    "model": message.data.get("model"),
                    "session_id": message.data.get("session_id"),
                })
            elif isinstance(message, AssistantMessage):
                llm_span = Span(type=SpanType.LLM_CALL, name="assistant_turn", started_at=_now())
                llm_span.sequence = next(seq)
                for block in message.content:
                    if isinstance(block, TextBlock):
                        if llm_span.output is None:
                            llm_span.output = {}    #initialize(cant be none)
                        # accumulate every text fragment — one turn can have several
                        llm_span.output.setdefault("text", []).append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        tool_call = Span(parent_span_id=llm_span.id, type=SpanType.TOOL_CALL, name=block.name, started_at=_now(), input=block.input, attributes={"tool_name": block.name})
                        tool_call.sequence = next(seq)
                        pending[block.id] = tool_call
                        #make a tool_call span (parent_span_id = llm_span.id),
                        #set input = block.input and attributes["tool_name"] = block.name,
                        #then stash it: pending[block.id] = that span  (DON'T append yet)
                    elif isinstance(block, ThinkingBlock):
                        if llm_span.output is None:
                            llm_span.output = {}
                        llm_span.output.setdefault("thinking", []).append(block.thinking)
                llm_span.ended_at = _now()
                run.spans.append(llm_span)
            elif isinstance(message, UserMessage):
                for block in message.content:
                    if isinstance(block, ToolResultBlock):
                        span = pending.pop(block.tool_use_id, None)
                        if span is None:
                            # orphan result: no span we opened matches. Record it,
                            # don't crash the whole run.
                            run.metadata.setdefault("orphan_results", []).append(block.tool_use_id)
                            continue
                        if block.is_error:
                            span.error = str(getattr(block, "content", ""))
                        else:
                            span.output = {"result": getattr(block, "content", None)}
                            span.error = None
                        span.ended_at = _now()
                        run.spans.append(span)
                        #span = pending.pop(block.tool_use_id);
                        #fill span.output, span.error (if is_error), span.ended_at;
                        #run.spans.append(span)
            elif isinstance(message, ResultMessage):
                if message.is_error:
                    run.status = RunStatus.ERROR
                    
                else:
                    run.status = RunStatus.SUCCESS
                    run.output = {"result": message.result}
                run.ended_at = _now()

                run.metadata.update({
                    "cost_usd": getattr(message, "total_cost_usd", None),
                    "duration_ms": getattr(message, "duration_ms", None),
                    "num_turns": getattr(message, "num_turns", None),
                })
                #run.status = error vs success (from is_error); run.ended_at;
                #run.output = {"result": message.result};
                #run.metadata += cost_usd / duration_ms / num_turns
    except Exception as e:
        run.status = RunStatus.ERROR
        run.metadata["error"] = repr(e)

    finally:
        for span in pending.values():
            span.error = "incomplete: no tool result"
            run.spans.append(span)        # span.ended_at stays None — never finished
        if run.status == RunStatus.RUNNING:
            run.status = RunStatus.ERROR
        if run.ended_at is None:
            run.ended_at = _now()
            

    return run