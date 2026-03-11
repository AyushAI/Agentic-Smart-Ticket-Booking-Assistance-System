import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langchain_groq import ChatGroq

from tools import load_tools
from memory import retrieve_memory, store_conversation
from airport_codes import AIRPORT_CODES
from ethics import is_unethical
from audit_log import init_db, log_search

load_dotenv()
logger = logging.getLogger(__name__)

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0
)

tools = load_tools()
init_db()


def city_to_airport(city: str) -> str | None:
    if not city:
        return None
    return AIRPORT_CODES.get(city.strip().lower())


def resolve_date(date_str: str) -> str | None:
    """
    Convert natural language dates to YYYY-MM-DD.
    Handles: 'tomorrow', 'today', 'YYYY-MM-DD' (pass-through).
    LLM is instructed to resolve relative dates but this is a safety net.
    """
    if not date_str:
        return None
    date_str = date_str.strip().lower()
    today = datetime.now().date()
    if date_str == "tomorrow":
        return str(today + timedelta(days=1))
    if date_str == "today":
        return str(today)
    # Already YYYY-MM-DD — validate format
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        return None


def agent_node(state: dict) -> dict:
    """
    Extracts full travel intent including return journey details,
    preferred modes, arrival constraints, and fallback logic.
    """
    query = state["messages"][-1]

    # ── Ethics gate ──────────────────────────────────────────────────────────
    blocked, reason = is_unethical(query)
    if blocked:
        state["recommendation"] = {"message": f"⛔ {reason}"}
        state["needs_clarification"] = True
        state["reasoning_trace"].append(f"ETHICS BLOCK: {reason}")
        log_search(session_id=state.get("session_id", "unknown"),
                   query=query, state=state, was_blocked=True, block_reason=reason)
        return state

    store_conversation(query)
    memory = retrieve_memory(query)

    today_str = str(datetime.now().date())

    # ── LLM extraction prompt ────────────────────────────────────────────────
    prompt = f"""
You are a travel assistant. Today's date is {today_str}.

Extract ALL travel details from the user request. Support single and return journeys.

User request: {query}

Conversation memory: {memory}

Return ONLY a raw JSON object — no markdown, no backticks, no explanation:

{{
  "origin": "<city name or empty string>",
  "destination": "<city name or empty string>",
  "date": "<YYYY-MM-DD — resolve 'tomorrow', 'next Monday' etc relative to today {today_str}>",
  "budget": "<numeric value or empty string>",
  "preferred_mode": "<flight|train|bus or empty string if not specified>",
  "is_return": <true or false>,
  "return_date": "<YYYY-MM-DD — if is_return true, calculate from departure date + duration mentioned>",
  "return_mode": "<preferred mode for return: flight|train|bus or empty string>",
  "return_fallback_mode": "<fallback mode if return_mode unavailable: flight|train|bus or empty string>",
  "return_arrival_by": "<HH:MM arrival constraint for return, or empty string>"
}}
"""

    response = llm.invoke(prompt)

    try:
        raw = response.content.strip().strip("```json").strip("```").strip()
        data = json.loads(raw)

        origin_city = data.get("origin", "")
        destination_city = data.get("destination", "")

        state["origin"] = city_to_airport(origin_city)
        state["destination"] = city_to_airport(destination_city)
        state["date"] = resolve_date(data.get("date", ""))
        state["budget"] = data.get("budget") or None
        state["preferred_mode"] = data.get("preferred_mode") or None
        state["is_return"] = bool(data.get("is_return", False))
        state["return_date"] = resolve_date(data.get("return_date", ""))
        state["return_mode"] = data.get("return_mode") or None
        state["return_fallback_mode"] = data.get("return_fallback_mode") or None
        state["return_arrival_by"] = data.get("return_arrival_by") or None

    except (json.JSONDecodeError, AttributeError) as e:
        logger.error("Failed to parse LLM response: %s | Raw: %s", e, response.content)
        state["recommendation"] = {"message": "Sorry, I had trouble understanding your request. Please rephrase."}
        state["needs_clarification"] = True
        state["reasoning_trace"].append("Agent failed to parse LLM JSON response")
        return state

    state["reasoning_trace"].append(
        f"Agent extracted: {origin_city}({state.get('origin')}) → "
        f"{destination_city}({state.get('destination')}) on {state.get('date')} "
        f"[mode: {state.get('preferred_mode') or 'any'}] | "
        f"Return: {state.get('is_return')} on {state.get('return_date')} "
        f"[mode: {state.get('return_mode') or 'any'}, "
        f"fallback: {state.get('return_fallback_mode') or 'none'}, "
        f"arrive by: {state.get('return_arrival_by') or 'any time'}]"
    )

    # ── Clarification check ───────────────────────────────────────────────────
    missing = []
    if not state["origin"]:      missing.append("origin city")
    if not state["destination"]: missing.append("destination city")
    if not state["date"]:        missing.append("travel date")
    if state["is_return"] and not state["return_date"]:
        missing.append("return date")

    if missing:
        state["needs_clarification"] = True
        state["recommendation"] = {"message": f"I need a bit more detail. Please provide: {', '.join(missing)}."}
        state["reasoning_trace"].append(f"Agent requested clarification for: {missing}")
    else:
        state["needs_clarification"] = False

    return state


def _parse_tool_output(tool_name: str, output) -> list[dict]:
    """Normalise MCP tool output — handles JSON string wrapped in content dict."""
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
            if isinstance(parsed, list):
                return [i for i in parsed if isinstance(i, dict)]
            if isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            pass
        return []

    if isinstance(output, list):
        # MCP adapter wraps result as [{"type":"text","text":"[{...}]"}]
        content_texts = []
        for item in output:
            if isinstance(item, dict) and "text" in item:
                content_texts.append(item["text"])
            else:
                content = getattr(item, "content", None)
                if content and isinstance(content, str):
                    content_texts.append(content)
                elif content and isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and "text" in c:
                            content_texts.append(c["text"])

        if content_texts:
            all_items = []
            for text in content_texts:
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        all_items.extend([i for i in parsed if isinstance(i, dict)])
                    elif isinstance(parsed, dict):
                        all_items.append(parsed)
                except json.JSONDecodeError:
                    pass
            if all_items:
                return all_items

        # Direct list of dicts
        dicts = [i for i in output if isinstance(i, dict) and "price" in i]
        if dicts:
            return dicts

        return []

    if isinstance(output, dict):
        return [output]

    return []


async def _invoke_tools_async(tool_list, origin, destination, date, mode_filter=None):
    """
    Call all MCP tools concurrently. If mode_filter is set (e.g. "bus"),
    only invoke the matching tool.
    """
    async def call_one(tool):
        name = getattr(tool, "name", str(tool))
        # Apply mode filter — skip tools that don't match
        if mode_filter and mode_filter.lower() not in name.lower():
            return []
        try:
            raw = await tool.ainvoke(
                {"origin": origin, "destination": destination, "date": date}
            )
            print(f"[DEBUG] tool={name} type={type(raw).__name__} raw={repr(raw)[:300]}")
            return _parse_tool_output(name, raw)
        except Exception as e:
            logger.error("Tool %s failed: %s", name, e)
            return {"_error": True, "name": name, "msg": str(e)}

    return await asyncio.gather(*[call_one(t) for t in tool_list])


def tool_node(state: dict) -> dict:
    """
    Fetches outbound AND return travel options.
    Respects preferred_mode for outbound and return_mode for return leg.
    """
    if state.get("needs_clarification"):
        return state

    origin      = state["origin"]
    destination = state["destination"]
    date        = state["date"]
    outbound_mode = state.get("preferred_mode")

    # ── Outbound search ───────────────────────────────────────────────────────
    raw_outbound = asyncio.run(
        _invoke_tools_async(tools, origin, destination, date, mode_filter=outbound_mode)
    )

    outbound_results = []
    for item in raw_outbound:
        if isinstance(item, list):
            outbound_results.extend(item)
        elif isinstance(item, dict) and item.get("_error"):
            state["reasoning_trace"].append(f"Tool {item['name']} failed: {item['msg']}")

    state["travel_options"] = outbound_results
    state["reasoning_trace"].append(
        f"Outbound search: {len(outbound_results)} option(s) found "
        f"[mode filter: {outbound_mode or 'all'}]"
    )

    # ── Return search (if requested) ──────────────────────────────────────────
    if state.get("is_return") and state.get("return_date"):
        return_mode = state.get("return_mode")
        fallback    = state.get("return_fallback_mode")

        # Search return leg — swap origin/destination
        raw_return = asyncio.run(
            _invoke_tools_async(
                tools,
                destination,   # return origin = outbound destination
                origin,        # return destination = outbound origin
                state["return_date"],
                mode_filter=return_mode
            )
        )

        return_results = []
        for item in raw_return:
            if isinstance(item, list):
                return_results.extend(item)
            elif isinstance(item, dict) and item.get("_error"):
                state["reasoning_trace"].append(f"Return tool {item['name']} failed: {item['msg']}")

        # ── Apply arrival constraint ──────────────────────────────────────────
        arrival_by = state.get("return_arrival_by")
        if arrival_by and return_results:
            filtered_by_arrival = [
                opt for opt in return_results
                if opt.get("arrival", "99:99") <= arrival_by
            ]
            if filtered_by_arrival:
                return_results = filtered_by_arrival
                state["reasoning_trace"].append(
                    f"Return: filtered to {len(return_results)} option(s) arriving by {arrival_by}"
                )
            else:
                # No options meet arrival constraint — try fallback mode
                state["reasoning_trace"].append(
                    f"Return: no {return_mode} arrives by {arrival_by} — trying fallback: {fallback}"
                )
                if fallback:
                    raw_fallback = asyncio.run(
                        _invoke_tools_async(
                            tools,
                            destination,
                            origin,
                            state["return_date"],
                            mode_filter=fallback
                        )
                    )
                    fallback_results = []
                    for item in raw_fallback:
                        if isinstance(item, list):
                            fallback_results.extend(item)

                    # Filter fallback by arrival constraint too
                    fallback_on_time = [
                        opt for opt in fallback_results
                        if opt.get("arrival", "99:99") <= arrival_by
                    ]
                    if fallback_on_time:
                        return_results = fallback_on_time
                        state["reasoning_trace"].append(
                            f"Return: using fallback {fallback} — "
                            f"{len(return_results)} option(s) arrive by {arrival_by}"
                        )
                    elif fallback_results:
                        # Fallback exists but doesn't meet time — show anyway with warning
                        return_results = fallback_results
                        state["reasoning_trace"].append(
                            f"Return: fallback {fallback} found but none arrive by {arrival_by} — "
                            f"showing best available"
                        )
                    else:
                        state["reasoning_trace"].append(
                            f"Return: no fallback {fallback} options found either"
                        )

        state["return_options"] = return_results
        state["reasoning_trace"].append(
            f"Return search: {len(return_results)} option(s) found "
            f"[mode: {return_mode or 'all'}, fallback: {fallback or 'none'}]"
        )

    return state