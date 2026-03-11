from typing import TypedDict, List, Dict, Optional


class AgentState(TypedDict):
    """
    Central state object passed through the LangGraph workflow.
    Supports single-leg and multi-leg (return) journeys.
    """

    messages: List[str]

    # ── Outbound leg ────────────────────────────────────────────────────────
    origin: Optional[str]           # IATA code e.g. "BOM"
    destination: Optional[str]      # IATA code e.g. "NAG"
    date: Optional[str]             # YYYY-MM-DD
    budget: Optional[str]
    preferred_mode: Optional[str]   # "flight", "train", "bus", or None (any)

    # ── Return leg (optional) ────────────────────────────────────────────────
    is_return: bool                 # True if user wants a return journey
    return_date: Optional[str]      # YYYY-MM-DD
    return_mode: Optional[str]      # preferred mode for return e.g. "bus"
    return_fallback_mode: Optional[str]  # fallback if return_mode not available e.g. "train"
    return_arrival_by: Optional[str]     # arrival constraint e.g. "10:00"

    # ── Results ──────────────────────────────────────────────────────────────
    travel_options: List[Dict]           # outbound options
    return_options: List[Dict]           # return options

    recommendation: Dict                 # outbound recommendation
    return_recommendation: Dict          # return recommendation

    reasoning_trace: List[str]
    conversation_memory: List[str]
    needs_clarification: bool