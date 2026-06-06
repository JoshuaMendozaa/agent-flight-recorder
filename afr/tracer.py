# afr/tracer.py
from datetime import datetime, timezone
from claude_agent_sdk import (
    query, ClaudeAgentOptions,
    AssistantMessage, TextBlock, ToolUseBlock,
    UserMessage, ToolResultBlock, ResultMessage, SystemMessage,
)
from afr.schemas import Run, Span, SpanType, RunStatus

def _now():
    return datetime.now(timezone.utc)

async def record_run(agent_name: str, task: str, options: ClaudeAgentOptions) -> Run:
    run = Run(agent_name=agent_name,
            started_at=_now(),
            input={"task": task}
            )
    pending: dict[str, Span] = {}      # tool_use_id -> the open tool_call span

    async for message in query(prompt=task, options=options):
        if isinstance(message, SystemMessage):
            run.metadata = message.data
            # TODO: stash model / session_id into run.metadata (optional)
            ...
        elif isinstance(message, AssistantMessage):
            llm_span = Span(type=SpanType.LLM_CALL, name="assistant_turn", started_at=_now())
            for block in message.content:
                if isinstance(block, TextBlock):
                    if llm_span.output is None:
                        llm_span.output = {}    #initialize(cant be none)
                    llm_span.output["reason_text"] = block.text
                    #put the reasoning text into llm_span.output
                elif isinstance(block, ToolUseBlock):
                    tool_call = Span(parent_span_id=llm_span.id, type=SpanType.TOOL_CALL, name=block.name, started_at=_now(), input=block.input, attributes={"tool_name": block.name})
                    pending[block.id] = tool_call
                    #make a tool_call span (parent_span_id = llm_span.id),
                    #set input = block.input and attributes["tool_name"] = block.name,
                    #then stash it: pending[block.id] = that span  (DON'T append yet)
            llm_span.ended_at = _now()
            run.spans.append(llm_span)
        elif isinstance(message, UserMessage):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    span = pending.pop(block.tool_use_id)
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
    return run