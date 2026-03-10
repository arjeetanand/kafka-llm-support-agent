import json
import os
from typing import Annotated, TypedDict

from confluent_kafka import Consumer
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

# --- 1. Define LangGraph State and Agent ---

# State represents the data passed between nodes in the graph
class TicketState(TypedDict):
    ticket_id: str
    customer_name: str
    issue_text: str
    sentiment: str
    category: str
    draft_reply: str

# Initialize the Local LLM (Ollama)
llm = ChatOllama(model="llama3", temperature=0.2)


def analyze_ticket(state: TicketState) -> TicketState:
    """Analyzes the ticket for sentiment and category."""
    prompt = f"""
    Analyze the following customer support ticket and extract two things to exactly two words: 
    1. Sentiment (Positive, Neutral, Negative)
    2. Category (Billing, Technical, General)
    
    Ticket: "{state['issue_text']}"
    
    Respond strictly in the format: [Sentiment], [Category]
    """
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content.strip()
    
    try:
        parts = content.split(",")
        sentiment = parts[0].strip().replace("[", "").replace("]", "")
        category = parts[1].strip().replace("[", "").replace("]", "")
    except Exception:
        sentiment = "Unknown"
        category = "Unknown"
        
    return {"sentiment": sentiment, "category": category}

def process_action(state: TicketState) -> TicketState:
    """Takes action based on the analysis."""
    
    if state["sentiment"] == "Negative" and state["category"] == "Billing":
        draft_reply = f"Hi {state['customer_name']}, I apologize for the billing issue. I've escalated this to our finance team for an immediate refund check."
    elif state["category"] == "Technical":
        draft_reply = f"Hi {state['customer_name']}, sorry to hear about the technical issues. Could you please provide your device details so we can investigate?"
    else:
        draft_reply = f"Hi {state['customer_name']}, thank you for reaching out! A representative will be with you shortly."

    return {"draft_reply": draft_reply}

# Build Graph
builder = StateGraph(TicketState)
builder.add_node("analyze_ticket", analyze_ticket)
builder.add_node("process_action", process_action)
builder.add_edge(START, "analyze_ticket")
builder.add_edge("analyze_ticket", "process_action")
builder.add_edge("process_action", END)
agent = builder.compile()

# --- 2. Define Kafka Consumer ---

def start_kafka_consumer():
    consumer_config = {
        "bootstrap.servers": "localhost:9092",
        "group.id": "support-agent-group",
        "auto.offset.reset": "earliest"
    }
    
    consumer = Consumer(consumer_config)
    consumer.subscribe(["support-tickets"])
    
    print("🤖 Agent is running and waiting for support tickets...")
    
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print("❌ Kafka Error:", msg.error())
                continue
            
            value = msg.value().decode("utf-8")
            ticket = json.loads(value)
            
            print(f"\n📥 Received Ticket from {ticket.get('customer_name')}: {ticket.get('issue_text')}")
            print("⏳ Agent is thinking...")
            
            # --- 3. Run Agent Workflow ---
            initial_state = {
                "ticket_id": ticket.get("ticket_id"),
                "customer_name": ticket.get("customer_name"),
                "issue_text": ticket.get("issue_text"),
                "sentiment": "",
                "category": "",
                "draft_reply": ""
            }
            
            final_state = agent.invoke(initial_state)
            
            print(f"📊 Analysis: Sentiment=[{final_state['sentiment']}], Category=[{final_state['category']}]")
            print(f"✅ Auto-Reply: {final_state['draft_reply']}")
            print("-" * 50)
            
    except KeyboardInterrupt:
        print("\n🔴 Stopping agent")
    finally:
        consumer.close()

if __name__ == "__main__":
    start_kafka_consumer()
