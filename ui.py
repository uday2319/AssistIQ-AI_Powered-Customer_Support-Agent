import streamlit as st
import requests
import uuid


# ============================================================
# CONFIGURATION
# ============================================================

API_URL = "http://localhost:8000/chat"


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="AI Customer Support",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    /* ---------- Overall page ---------- */

    .stApp {
        background-color: #f8fafc;
    }

    .block-container {
        max-width: 1500px;
        padding: 35px 45px 50px 45px;
    }


    /* ---------- Header ---------- */

    h1 {
        color: #111827 !important;
        font-size: 32px !important;
        margin-bottom: 5px !important;
    }

    h2 {
        color: #111827 !important;
    }

    h3 {
        color: #111827 !important;
    }

    p {
        color: #374151;
        font-size: 16px;
        line-height: 1.6;
    }


    /* ---------- Buttons ---------- */

    .stButton > button {
        width: 100%;
        min-height: 48px;

        background-color: white;
        color: #1f2937;

        border: 1px solid #e5e7eb;
        border-radius: 10px;

        font-size: 15px;
        font-weight: 500;
    }

    .stButton > button:hover {
        background-color: #f1f5f9;
        border-color: #cbd5e1;
        color: #111827;
    }


    /* ---------- Chat ---------- */

    [data-testid="stChatMessage"] {
        padding: 12px 4px;
    }

    [data-testid="stChatMessage"] p {
        font-size: 16px;
        line-height: 1.7;
    }


    /* ---------- Chat input ---------- */

    [data-testid="stChatInput"] {
        margin-top: 15px;
    }

    [data-testid="stChatInput"] textarea {
        color: #111827 !important;
        background-color: white !important;

        font-size: 17px !important;
        line-height: 1.5 !important;

        caret-color: #111827 !important;
    }

    [data-testid="stChatInput"] textarea::placeholder {
        color: #6b7280 !important;
        opacity: 1 !important;
        font-size: 16px !important;
    }


    /* ---------- Text input ---------- */

    input {
        color: #111827 !important;
        background-color: white !important;
        font-size: 16px !important;
    }


    /* ---------- Cards ---------- */

    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: white;
        border-radius: 14px;
        border-color: #e5e7eb;
    }


    /* ---------- Divider ---------- */

    hr {
        border-color: #e5e7eb;
        margin-top: 20px;
        margin-bottom: 25px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "customer_id" not in st.session_state:
    st.session_state.customer_id = "C002"

if "order" not in st.session_state:
    st.session_state.order = None


# ============================================================
# HEADER
# ============================================================

header_left, header_right = st.columns([5, 1])

with header_left:

    st.title("🤖 AI Customer Support")

    st.caption(
        "Intelligent customer assistance powered by AI"
    )


with header_right:

    st.success("● AI Online")


st.divider()


# ============================================================
# MAIN LAYOUT
# ============================================================

left, center, right = st.columns(
    [1.5, 4.6, 1.9],
    gap="large",
)


# ============================================================
# LEFT — NAVIGATION
# ============================================================

with left:

    st.subheader("Navigation")

    if st.button("💬  Chat", key="nav_chat"):
        pass

    if st.button("📦  Orders", key="nav_orders"):
        st.session_state.messages.append(
            {
                "role": "user",
                "content": "Show me my order information.",
            }
        )
        st.rerun()

    if st.button("💰  Refunds", key="nav_refunds"):
        st.session_state.messages.append(
            {
                "role": "user",
                "content": "I want to request a refund.",
            }
        )
        st.rerun()

    if st.button("🚚  Track Order", key="nav_track"):
        st.session_state.messages.append(
            {
                "role": "user",
                "content": "Track my order.",
            }
        )
        st.rerun()

    if st.button("❓  Help & Policies", key="nav_policy"):
        st.session_state.messages.append(
            {
                "role": "user",
                "content": "Tell me about the refund, cancellation and shipping policies.",
            }
        )
        st.rerun()


    st.write("")
    st.write("")

    st.subheader("Quick Actions")


    if st.button("🚚  Track Order", key="quick_track"):
        st.session_state.messages.append(
            {
                "role": "user",
                "content": "Track my order.",
            }
        )
        st.rerun()


    if st.button("❌  Cancel Order", key="quick_cancel"):
        st.session_state.messages.append(
            {
                "role": "user",
                "content": "I want to cancel my order.",
            }
        )
        st.rerun()


    if st.button("↩️  Request Refund", key="quick_refund"):
        st.session_state.messages.append(
            {
                "role": "user",
                "content": "I want to request a refund.",
            }
        )
        st.rerun()


    if st.button("📖  Check Policy", key="quick_policy"):
        st.session_state.messages.append(
            {
                "role": "user",
                "content": "Tell me about your refund and cancellation policies.",
            }
        )
        st.rerun()


    if st.button("👨‍💼  Talk to Human", key="quick_human"):
        st.session_state.messages.append(
            {
                "role": "user",
                "content": "I want to talk to a human support agent.",
            }
        )
        st.rerun()


# ============================================================
# CENTER — CHAT
# ============================================================

with center:

    st.subheader("Customer Support Assistant")


    # --------------------------------------------------------
    # Welcome screen
    # --------------------------------------------------------

    if not st.session_state.messages:

        with st.container(border=True):

            st.markdown("## 👋 Welcome to AI Customer Support")

            st.write(
                "I'm your AI support assistant. I can help you "
                "with orders, refunds, cancellations, deliveries, "
                "and store policies."
            )

            st.markdown("### What can I help you with today?")

            st.write("📦 Track an order")
            st.write("↩️ Request a refund")
            st.write("❌ Cancel an order")
            st.write("📖 Check a policy")
            st.write("👨‍💼 Talk to a human agent")


    # --------------------------------------------------------
    # Display conversation
    # --------------------------------------------------------

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):

            st.markdown(message["content"])


    # --------------------------------------------------------
    # Chat input
    # --------------------------------------------------------

    user_message = st.chat_input(
        "Message the AI support agent..."
    )


    # --------------------------------------------------------
    # Send message
    # --------------------------------------------------------

    if user_message:

        # Add user's message to the UI immediately.
        st.session_state.messages.append(
            {
                "role": "user",
                "content": user_message,
            }
        )


        # Data sent to FastAPI.
        payload = {
            "customer_id": st.session_state.customer_id,
            "conversation_id": st.session_state.conversation_id,
            "message": user_message,
        }


        try:

            response = requests.post(
                API_URL,
                json=payload,
                timeout=120,
            )


            # Gemini/API rate limit.
            if response.status_code == 429:

                assistant_message = (
                    "The AI service is temporarily rate-limited. "
                    "Please try again shortly."
                )


            # Other API errors.
            elif response.status_code != 200:

                assistant_message = (
                    "The support service returned an error. "
                    "Please try again."
                )


            else:

                data = response.json()

                assistant_message = data.get(
                    "response",
                    "I couldn't generate a response.",
                )


                # Save order information returned by FastAPI.
                if data.get("order"):

                    st.session_state.order = data["order"]


        except requests.exceptions.ConnectionError:

            assistant_message = (
                "I couldn't connect to the support server. "
                "Make sure FastAPI is running on port 8000."
            )


        except requests.exceptions.Timeout:

            assistant_message = (
                "The request took too long. Please try again."
            )


        except Exception as e:

            assistant_message = (
                "Something went wrong while contacting "
                "the support agent."
            )


        # Add AI response.
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": assistant_message,
            }
        )


        # Refresh the page.
        st.rerun()


# ============================================================
# RIGHT — CUSTOMER INFORMATION
# ============================================================

with right:

    st.subheader("Customer")


    # --------------------------------------------------------
    # Customer ID
    # --------------------------------------------------------

    customer_id = st.text_input(
        "Customer ID",
        value=st.session_state.customer_id,
    )

    st.session_state.customer_id = customer_id


    # --------------------------------------------------------
    # Customer card
    # --------------------------------------------------------

    with st.container(border=True):

        st.subheader("👤 Customer")

        st.caption("Authenticated customer")

        st.markdown(
            f"### {st.session_state.customer_id}"
        )


    # --------------------------------------------------------
    # Current order
    # --------------------------------------------------------

    st.subheader("📦 Current Order")


    with st.container(border=True):

        if st.session_state.order:

            order = st.session_state.order

            st.markdown(
                f"**Order ID**  \n"
                f"`{order.get('order_id', 'N/A')}`"
            )

            st.markdown(
                f"**Status**  \n"
                f"{order.get('status', 'N/A')}"
            )

            st.markdown(
                f"**Expected Delivery**  \n"
                f"{order.get('expected_delivery', 'N/A')}"
            )

        else:

            st.markdown("### 📦")

            st.write(
                "No order information yet."
            )

            st.caption(
                "Ask the AI to track an order."
            )


    # --------------------------------------------------------
    # AI Agent
    # --------------------------------------------------------

    st.subheader("🤖 AI Agent")


    with st.container(border=True):

        st.success("● Online")

        st.markdown("**Capabilities**")

        st.write("✓ Order tracking")
        st.write("✓ Refund requests")
        st.write("✓ Order cancellation")
        st.write("✓ Policy search")
        st.write("✓ Human approval")


    # --------------------------------------------------------
    # Conversation
    # --------------------------------------------------------

    st.subheader("Conversation")


    with st.container(border=True):

        st.caption("Conversation ID")

        st.code(
            st.session_state.conversation_id,
            language=None,
        )


    # --------------------------------------------------------
    # New conversation
    # --------------------------------------------------------

    if st.button(
        "🔄  New Conversation",
        key="new_conversation",
    ):

        st.session_state.conversation_id = str(
            uuid.uuid4()
        )

        st.session_state.messages = []

        st.session_state.order = None

        st.rerun()