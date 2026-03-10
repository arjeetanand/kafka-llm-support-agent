import json
import os
from typing import Annotated, TypedDict

from confluent_kafka import Consumer, Producer
from langchain_community.vectorstores import FAISS
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage, AnyMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition

# --- 1. Define LangGraph State and Agent ---

# State represents the data passed between nodes in the graph
class TicketState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    ticket_id: str
    customer_name: str
    issue_text: str
    context: str
    sentiment: str
    category: str
    draft_reply: str

# Initialize the Local LLM (Ollama)
llm = ChatOllama(model="llama3.2", temperature=0.2)

# Initialize RAG Vector Store
embeddings = OllamaEmbeddings(model="nomic-embed-text")
vectorstore = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

# --- Defining Agentic Tools ---
@tool
def refund_customer(ticket_id: str, amount: str) -> str:
    """Refunds a customer. Only call this tool if company policy explicitly allows a refund."""
    print(f"\n[TOOL EXECUTION] Processing Refund of {amount} for Ticket {ticket_id}...")
    return f"Success: Refund processed."

@tool
def escalate_to_human(ticket_id: str, reason: str) -> str:
    """Escalates complex technical issues or angry customers to a human agent."""
    print(f"\n[TOOL EXECUTION] Escalating Ticket {ticket_id} to Human Support. Reason: {reason}...")
    return f"Success: Ticket {ticket_id} escalated to human."

tools = [refund_customer, escalate_to_human]
llm_with_tools = llm.bind_tools(tools)



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

def retrieve_context(state: TicketState) -> TicketState:
    """Retrieves relevant knowledge base articles."""
    docs = retriever.invoke(state["issue_text"])
    context = "\n".join([doc.page_content for doc in docs])
    return {"context": context}

def process_action(state: TicketState) -> TicketState:
    """Drafts a reply or calls tools based on the issue."""
    sys_prompt = f"""
    You are a professional customer support agent.
    Ticket ID: {state['ticket_id']}
    Customer Name: {state['customer_name']}
    Issue Category: {state['category']}
    Sentiment: {state['sentiment']}
    
    Current Knowledge Base Context:
    {state['context']}
    
    ### STRICT ACTION RULES:
    1. If Category is "Billing" AND Sentiment is "Negative": You MUST process a refund. ALWAYS use the `refund_customer` tool.
    2. If Category is "Technical" AND Sentiment is "Negative": You MUST escalate. ALWAYS use the `escalate_to_human` tool.
    3. If Category is "General" OR Sentiment is "Positive": DO NOT USE ANY TOOLS. Simply write a friendly response.
    4. If you have JUST used a tool in this turn, do not call it again. Draft the final reply to the customer.
    
    Draft your final response to the user based on these rules.
    """
    
    messages = [SystemMessage(content=sys_prompt)] + state["messages"]
    
    # Check if tools have already been executed in the conversation history
    tools_already_used = any(m.type == "tool" for m in state["messages"])
    
    try:
        # Deterministic Tool Routing to bypass small LLM reasoning limits
        if not tools_already_used:
            if state['sentiment'] == "Negative" and state['category'] == "Billing":
                # Forcing a tool call can be tricky with some models. 
                # If tool_choice fails, we will fallback to a very strict prompt.
                response = llm_with_tools.invoke(messages) 
            elif state['sentiment'] == "Negative" and state['category'] == "Technical":
                response = llm_with_tools.invoke(messages)
            else:
                response = llm.invoke(messages)
        else:
            response = llm.invoke(messages)
            
        return {"messages": [response], "draft_reply": response.content}
    except Exception as e:
        import traceback
        print(f"ERROR in process_action: {e}")
        traceback.print_exc()
        raise e

# Build Graph
builder = StateGraph(TicketState)
builder.add_node("analyze_ticket", analyze_ticket)
builder.add_node("retrieve_context", retrieve_context)
builder.add_node("process_action", process_action)

# Add the special ToolNode to execute Python functions
tool_node = ToolNode(tools)
builder.add_node("tools", tool_node)

builder.add_edge(START, "analyze_ticket")
builder.add_edge("analyze_ticket", "retrieve_context")
builder.add_edge("retrieve_context", "process_action")

# Conditional Router: After processing action, did the LLM ask to use a tool?
builder.add_conditional_edges(
    "process_action",
    tools_condition,
    {
        "tools": "tools",
        END: END,
    }
)

# Loop back from tools to processing action to finish drafting the reply
builder.add_edge("tools", "process_action")

agent = builder.compile()

# --- 2. Define Kafka Consumer ---

def start_kafka_consumer():
    consumer_config = {
        "bootstrap.servers": "localhost:9092",
        "group.id": "support-agent-group-v3",
        "auto.offset.reset": "earliest"
    }
    
    producer_config = {
        "bootstrap.servers": "localhost:9092"
    }
    
    consumer = Consumer(consumer_config)
    producer = Producer(producer_config)
    consumer.subscribe(["support-tickets"])
    
    print("Agent is running and waiting for support tickets...")
    
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print("Kafka Error:", msg.error())
                continue
            
            value = msg.value().decode("utf-8")
            ticket = json.loads(value)
            
            print(f"\n[RECEIVED] Ticket from {ticket.get('customer_name')}: {ticket.get('issue_text')}")
            print("[STATUS] Agent is thinking...")
            
            # --- 3. Run Agent Workflow ---
            initial_state = {
                "messages": [HumanMessage(content=ticket.get("issue_text"))],
                "ticket_id": ticket.get("ticket_id"),
                "customer_name": ticket.get("customer_name"),
                "issue_text": ticket.get("issue_text"),
                "context": "",
                "sentiment": "",
                "category": "",
                "draft_reply": ""
            }
            
            final_state = agent.invoke(initial_state)
            
            print(f"[ANALYSIS] Sentiment=[{final_state['sentiment']}], Category=[{final_state['category']}]")
            print(f"[AUTO-REPLY] {final_state['draft_reply']}")
            print("-" * 50)
            
            # Extract just the last generated message payload, filtering out all the complex input history
            tools_called = False
            for m in final_state["messages"]:
                if m.type == "tool":
                    tools_called = True
            
            processed_payload = {
                "ticket_id": ticket.get("ticket_id"),
                "customer_name": ticket.get("customer_name"),
                "issue_text": ticket.get("issue_text"),
                "sentiment": final_state["sentiment"],
                "category": final_state["category"],
                "draft_reply": final_state["draft_reply"],
                "tools_executed": tools_called
            }
            producer.produce("processed-tickets", value=json.dumps(processed_payload).encode("utf-8"))
            producer.flush()
            
    except KeyboardInterrupt:
        print("\n[STOP] Stopping agent")
    finally:
        consumer.close()

if __name__ == "__main__":
    start_kafka_consumer()
