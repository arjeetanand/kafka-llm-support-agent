import streamlit as st
from confluent_kafka import Consumer
import json
import time

# --- Page Configuration ---
st.set_page_config(page_title="Support Agent Dashboard", page_icon="🤖", layout="wide")

st.title("🤖 Live AI Support Agent Dashboard")
st.markdown("Watching the `processed-tickets` Kafka topic for real-time agent decisions.")

# Refresh Controls
col_a, col_b = st.columns([1, 4])
with col_a:
    auto_refresh = st.checkbox("🔄 Auto-Refresh (3s)", value=False)
with col_b:
    if st.button("Manual Refresh"):
        st.rerun()

# Initialize session state to store tickets
if "tickets" not in st.session_state:
    st.session_state.tickets = []

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
    # Poll up to 10 messages per rerun to prevent blocking the UI
    for _ in range(10):
        msg = consumer.poll(0.1)
        if msg is None:
            break
        if msg.error():
            continue
            
        try:
            val = msg.value().decode('utf-8')
            ticket_data = json.loads(val)
            # Add new ticket to the beginning of the list, preventing duplicates
            if not any(t.get("ticket_id") == ticket_data.get("ticket_id") for t in st.session_state.tickets):
                st.session_state.tickets.insert(0, ticket_data)
        except Exception as e:
            pass

# Fetch new messages
poll_kafka()

# --- UI Rendering ---
if not st.session_state.tickets:
    st.info("Waiting for tickets... (Ollama might still be thinking in the background terminal!)")
else:
    # Metrics Row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Processed", len(st.session_state.tickets))
    with col2:
        refunds = sum(1 for t in st.session_state.tickets if "refund" in str(t.get("draft_reply", "")).lower() or t.get("tools_executed"))
        st.metric("Actions Taken", refunds)
    with col3:
        negatives = sum(1 for t in st.session_state.tickets if "negative" in str(t.get("sentiment", "")).lower())
        st.metric("Negative Sentiment", negatives)

    st.markdown("---")
    
    # Draw each ticket as a beautiful card
    for ticket in st.session_state.tickets:
        with st.container():
            # Header row
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.subheader(f"Ticket from {ticket.get('customer_name', 'Unknown')}")
            
            # Status badges
            sentiment = ticket.get("sentiment", "Unknown")
            category = ticket.get("category", "Unknown")
            
            if "Negative" in sentiment:
                c2.error(f"Sentiment: {sentiment}")
            elif "Positive" in sentiment:
                c2.success(f"Sentiment: {sentiment}")
            else:
                c2.warning(f"Sentiment: {sentiment}")
                
            c3.info(f"Category: {category}")
            
            # Content
            st.markdown("**Original Issue:**")
            st.write(f"> {ticket.get('issue_text', '')}")
            
            st.markdown("**AI Response:**")
            
            tools_used = ticket.get("tools_executed", False)
            if tools_used:
                st.success("⚡ **Action Taken:** The LangGraph Agent executed an external API Tool to resolve this.")
            
            st.code(ticket.get("draft_reply", ""), language="markdown")
            st.markdown("---")

# Auto-refresh mechanism
if auto_refresh:
    time.sleep(3)
    st.rerun()
