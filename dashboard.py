import streamlit as st
from confluent_kafka import Consumer
import json
import time
from database import get_all_tickets, get_stats

# --- Page Configuration ---
st.set_page_config(page_title="Support Agent Dashboard", page_icon="🤖", layout="wide")

st.title("🤖 AI Support Agent Dashboard")

# --- Sidebar Controls ---
st.sidebar.title("Dashboard Settings")
view_mode = st.sidebar.radio("View Mode", ["Live Kafka Stream", "Historical Database"])

if view_mode == "Live Kafka Stream":
    st.markdown("Watching the `processed-tickets` Kafka topic for real-time agent decisions.")
    
    # Refresh Controls
    col_a, col_b = st.columns([1, 4])
    with col_a:
        auto_refresh = st.checkbox("🔄 Auto-Refresh (3s)", value=True)
    with col_b:
        if st.button("Manual Refresh"):
            st.rerun()

    # Initialize session state to store tickets
    if "live_tickets" not in st.session_state:
        st.session_state.live_tickets = []

    # --- Kafka Consumer Setup ---
    @st.cache_resource
    def get_kafka_consumer():
        conf = {
            'bootstrap.servers': 'localhost:9092',
            'group.id': 'streamlit-dashboard-group-static',
            'auto.offset.reset': 'earliest'
        }
        c = Consumer(conf)
        c.subscribe(['processed-tickets'])
        return c

    consumer = get_kafka_consumer()

    # Function to poll Kafka synchronously
    def poll_kafka():
        for _ in range(10):
            msg = consumer.poll(0.1)
            if msg is None:
                break
            if msg.error():
                continue
                
            try:
                val = msg.value().decode('utf-8')
                ticket_data = json.loads(val)
                if not any(t.get("ticket_id") == ticket_data.get("ticket_id") for t in st.session_state.live_tickets):
                    st.session_state.live_tickets.insert(0, ticket_data)
            except Exception as e:
                pass

    poll_kafka()
    display_tickets = st.session_state.live_tickets
    
    # Live Metrics (In-memory)
    total_count = len(display_tickets)
    actions_count = sum(1 for t in display_tickets if t.get("tools_executed"))
    negatives_count = sum(1 for t in display_tickets if "negative" in str(t.get("sentiment", "")).lower())

else:
    st.markdown("Viewing persisted ticket history from the local SQLite database.")
    display_tickets = get_all_tickets(limit=100)
    
    # Persistent Metrics (From DB)
    stats = get_stats()
    total_count = stats["total"]
    actions_count = stats["actions"]
    negatives_count = stats["negatives"]
    auto_refresh = False

# --- UI Rendering ---

if not display_tickets:
    st.info("No tickets found yet. Run `db_worker.py`, `support_agent.py`, and `producer.py`.")
else:
    # Metrics Row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Tickets", total_count)
    with col2:
        st.metric("Actions Taken", actions_count)
    with col3:
        st.metric("Negative Sentiment", negatives_count)

    st.markdown("---")
    
    # Draw each ticket as a beautiful card
    for ticket in display_tickets:
        with st.container():
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.subheader(f"Ticket from {ticket.get('customer_name', 'Unknown')}")
            
            sentiment = ticket.get("sentiment", "Unknown")
            category = ticket.get("category", "Unknown")
            
            if "Negative" in sentiment:
                c2.error(f"Sentiment: {sentiment}")
            elif "Positive" in sentiment:
                c2.success(f"Sentiment: {sentiment}")
            else:
                c2.warning(f"Sentiment: {sentiment}")
                
            c3.info(f"Category: {category}")
            
            st.markdown("**Original Issue:**")
            st.write(f"> {ticket.get('issue_text', '')}")
            
            # Routing Info
            dept_topic = f"{ticket.get('category', 'unknown').lower()}-dept"
            st.markdown(f"📍 **Routed To:** `{dept_topic}`")
            
            st.markdown("**AI Response:**")
            if ticket.get("tools_executed"):
                st.success("⚡ **Action Taken:** Agent executed an external API Tool.")
            
            st.code(ticket.get("draft_reply", ""), language="markdown")
            st.markdown("---")

# Auto-refresh mechanism
if auto_refresh:
    time.sleep(3)
    st.rerun()
