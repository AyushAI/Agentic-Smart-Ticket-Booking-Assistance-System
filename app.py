import uuid
import streamlit as st
from graph import build_graph
from audit_log import init_db, log_search, get_recent_searches

init_db()

@st.cache_resource
def get_agent():
    return build_graph()

agent = get_agent()

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

st.set_page_config(page_title="AI Travel Booking Agent", page_icon="✈️")
st.title("✈️ AI Travel Booking Agent")
st.caption("Powered by LangGraph + Groq + Amadeus")

query = st.text_input(
    "Where do you want to travel?",
    placeholder='e.g. "Flight from Mumbai to Nagpur tomorrow, return by bus after 10 days, arrive by 10 AM"',
)

if st.button("Search", type="primary"):

    if not query.strip():
        st.warning("Please enter a travel query first.")
    else:
        with st.spinner("Thinking..."):

            state = {
                "messages": [query],
                "session_id": st.session_state.session_id,
                "origin": None,
                "destination": None,
                "date": None,
                "budget": None,
                "preferred_mode": None,
                "is_return": False,
                "return_date": None,
                "return_mode": None,
                "return_fallback_mode": None,
                "return_arrival_by": None,
                "travel_options": [],
                "return_options": [],
                "recommendation": {},
                "return_recommendation": {},
                "reasoning_trace": [],
                "conversation_memory": [],
                "needs_clarification": False,
            }

            result = agent.invoke(state)

            was_blocked = "ETHICS BLOCK" in " ".join(result.get("reasoning_trace", []))
            log_search(
                session_id=st.session_state.session_id,
                query=query,
                state=result,
                was_blocked=was_blocked,
            )

        # ── Helper to render one leg ──────────────────────────────────────────
        def render_recommendation(rec: dict, label: str):
            st.subheader(label)
            if not rec:
                st.info("No recommendation available.")
                return
            if "message" in rec:
                if "⛔" in rec["message"]:
                    st.error(rec["message"])
                else:
                    st.info(rec["message"])
            if "mode" in rec:
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Mode",      rec.get("mode", "—").title())
                col2.metric("Operator",  rec.get("operator", "—"))
                col3.metric("Departs",   rec.get("departure", "—"))
                col4.metric("Arrives",   rec.get("arrival", "—"))
                col5.metric("Price",     f"₹{rec.get('price', '—')}")

        def render_options_table(options: list, label: str):
            if not options:
                return
            st.subheader(label)
            st.dataframe(
                options,
                use_container_width=True,
                column_order=["mode", "operator", "departure", "arrival", "time", "price"],
                column_config={
                    "mode":      "Mode",
                    "operator":  "Operator / Flight",
                    "departure": "Departs",
                    "arrival":   "Arrives",
                    "time":      "Duration",
                    "price":     st.column_config.NumberColumn("Price (₹)", format="₹%.0f"),
                    "currency":  None,
                },
            )

        # ── Outbound ──────────────────────────────────────────────────────────
        render_recommendation(result.get("recommendation", {}), "🛫 Outbound Recommendation")
        render_options_table(result.get("travel_options", []), "📋 Outbound Options")

        # ── Return (only if is_return) ────────────────────────────────────────
        if result.get("is_return"):
            st.divider()
            render_recommendation(result.get("return_recommendation", {}), "🛬 Return Recommendation")
            render_options_table(result.get("return_options", []), "📋 Return Options")

        # ── Reasoning trace ───────────────────────────────────────────────────
        with st.expander("🔍 Reasoning Trace (Audit Trail)"):
            for i, step in enumerate(result.get("reasoning_trace", []), 1):
                st.write(f"{i}. {step}")

# ── Audit log viewer ──────────────────────────────────────────────────────────
st.divider()
with st.expander("🗃️ Audit Log (last 20 searches)"):
    rows = get_recent_searches(20)
    if rows:
        import pandas as pd
        df = pd.DataFrame(rows)[[
            "id", "timestamp", "query", "origin", "destination",
            "travel_date", "budget", "options_count", "was_blocked", "block_reason"
        ]]
        df["was_blocked"] = df["was_blocked"].map({0: "✅", 1: "⛔"})
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No searches logged yet.")