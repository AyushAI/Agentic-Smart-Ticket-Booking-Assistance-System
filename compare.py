import logging

logger = logging.getLogger(__name__)


def compare_options(state: dict) -> dict:
    """
    Picks best outbound AND return options.
    Strategy: cheapest within budget, respecting arrival constraints already
    applied in tool_node.
    """

    # ── Outbound recommendation ───────────────────────────────────────────────
    options = state.get("travel_options", [])

    if not options:
        state["recommendation"] = {"message": "No outbound travel options were found."}
        state["reasoning_trace"].append("compare: no outbound options")
    else:
        state["recommendation"] = _pick_best(options, state.get("budget"), "outbound")
        state["reasoning_trace"].append(
            f"compare: outbound → {state['recommendation'].get('operator')} "
            f"({state['recommendation'].get('mode')}) ₹{state['recommendation'].get('price')}"
        )

    # ── Return recommendation ─────────────────────────────────────────────────
    return_options = state.get("return_options", [])

    if state.get("is_return"):
        if not return_options:
            state["return_recommendation"] = {
                "message": "No return travel options were found matching your constraints."
            }
            state["reasoning_trace"].append("compare: no return options found")
        else:
            state["return_recommendation"] = _pick_best(return_options, state.get("budget"), "return")
            state["reasoning_trace"].append(
                f"compare: return → {state['return_recommendation'].get('operator')} "
                f"({state['return_recommendation'].get('mode')}) "
                f"₹{state['return_recommendation'].get('price')}"
            )

    return state


def _pick_best(options: list, budget: str | None, leg: str) -> dict:
    """
    Pick cheapest option within budget.
    Falls back to overall cheapest if nothing fits budget.
    """
    filtered = options
    if budget:
        try:
            budget_val = float(str(budget).replace(",", "").strip())
            within = [o for o in options if o.get("price", float("inf")) <= budget_val]
            if within:
                filtered = within
        except ValueError:
            pass

    try:
        cheapest = min(filtered, key=lambda x: float(x.get("price", float("inf"))))
    except (ValueError, TypeError) as e:
        logger.error("Error comparing %s options: %s", leg, e)
        return {"message": f"Could not compare {leg} options."}

    return {
        "mode":      cheapest.get("mode", "unknown"),
        "operator":  cheapest.get("operator", "N/A"),
        "departure": cheapest.get("departure", "N/A"),
        "arrival":   cheapest.get("arrival", "N/A"),
        "price":     cheapest.get("price"),
        "time":      cheapest.get("time", "N/A"),
        "message": (
            f"{cheapest.get('operator', cheapest.get('mode', 'unknown'))} "
            f"({cheapest.get('mode', '').title()}) | "
            f"Departs {cheapest.get('departure', 'N/A')} → "
            f"Arrives {cheapest.get('arrival', 'N/A')} | "
            f"Duration: {cheapest.get('time', 'N/A')} | "
            f"₹{cheapest.get('price')}"
        ),
    }