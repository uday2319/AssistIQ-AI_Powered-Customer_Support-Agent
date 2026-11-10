"""
Staff page: review refunds the AI agent found eligible,
then approve or reject them.

Opens as a second page next to the customer chat when you run
`streamlit run ui.py`.
"""

import os
from datetime import datetime, timezone

import requests
import streamlit as st


API_BASE = os.getenv("SUPPORT_API_URL", "http://localhost:8000").rstrip("/")


st.set_page_config(
    page_title="Refund Approvals",
    page_icon="🧾",
    layout="wide",
)

st.title("🧾 Refund Approvals")
st.caption(
    "Refund requests the AI agent checked and found eligible. "
    "Money only moves after you approve."
)


# ------------------------------------------------------------
# Staff key
# ------------------------------------------------------------

with st.sidebar:
    st.text_input(
        "Admin key",
        type="password",
        key="admin_key",
        help="Must match ADMIN_API_KEY on the server.",
    )

if not st.session_state.get("admin_key"):
    st.info("Enter the admin key in the sidebar to see pending refunds.")
    st.stop()

HEADERS = {"X-Admin-Key": st.session_state.admin_key}


def call_api(method: str, path: str, **kwargs):
    """Call the support API. Returns None if the server can't be reached."""
    try:
        return requests.request(
            method, API_BASE + path, headers=HEADERS, timeout=60, **kwargs
        )
    except requests.exceptions.RequestException:
        return None


def waiting_time(requested_at: str) -> str:
    """'5 min', '2 h', '3 days' since the refund was requested."""
    try:
        started = datetime.fromisoformat(requested_at)
    except ValueError:
        return "-"

    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)

    minutes = int((datetime.now(timezone.utc) - started).total_seconds() // 60)

    if minutes < 60:
        return f"{max(minutes, 0)} min"
    if minutes < 60 * 24:
        return f"{minutes // 60} h"
    return f"{minutes // (60 * 24)} days"


def decide(conversation_id: str, order_id: str, decision: str):
    response = call_api(
        "POST",
        f"/approvals/{conversation_id}",
        json={"decision": decision},
    )

    if response is not None and response.status_code == 200:
        word = "approved" if decision == "approved" else "rejected"
        st.session_state.flash = f"Refund for order {order_id} {word}. The customer has been told."
    else:
        st.session_state.flash_error = f"Could not update the refund for order {order_id}. Please refresh and try again."


# ------------------------------------------------------------
# Load the queue
# ------------------------------------------------------------

header_left, header_right = st.columns([5, 1])
with header_right:
    if st.button("🔄  Refresh", use_container_width=True):
        st.rerun()

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))
if "flash_error" in st.session_state:
    st.error(st.session_state.pop("flash_error"))

response = call_api("GET", "/approvals")

if response is None:
    st.error(f"Couldn't reach the support API at {API_BASE}. Is FastAPI running?")
    st.stop()

if response.status_code == 401:
    st.error("Wrong admin key.")
    st.stop()

if response.status_code == 503:
    st.error("Approvals are switched off on the server. Set ADMIN_API_KEY there.")
    st.stop()

if response.status_code != 200:
    st.error("The support API returned an error. Please try again.")
    st.stop()

pending = response.json()["pending"]


# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

count_col, total_col, _ = st.columns([1, 1, 3])
count_col.metric("Waiting", len(pending))
total_col.metric("Total amount", f"{sum(item['amount'] for item in pending):,.2f}")

st.divider()

if not pending:
    st.success("All caught up. No refunds are waiting for approval.")
    st.stop()


# ------------------------------------------------------------
# One card per refund
# ------------------------------------------------------------

for item in pending:

    with st.container(border=True):

        order_col, customer_col, amount_col, wait_col = st.columns(4)
        order_col.metric("Order", item["order_id"])
        customer_col.metric("Customer", item["customer_id"])
        amount_col.metric("Amount", f"{item['amount']:,.2f}")
        wait_col.metric("Waiting", waiting_time(item["requested_at"]))

        with st.expander("Conversation"):
            for line in item.get("transcript", []):
                role = "user" if line["role"] == "customer" else "assistant"
                with st.chat_message(role):
                    st.markdown(line["content"])

        approve_col, reject_col = st.columns(2)

        with approve_col:
            if st.button(
                "✅  Approve refund",
                key=f"approve_{item['conversation_id']}",
                type="primary",
                use_container_width=True,
            ):
                decide(item["conversation_id"], item["order_id"], "approved")
                st.rerun()

        with reject_col:
            if st.button(
                "❌  Reject",
                key=f"reject_{item['conversation_id']}",
                use_container_width=True,
            ):
                decide(item["conversation_id"], item["order_id"], "rejected")
                st.rerun()
