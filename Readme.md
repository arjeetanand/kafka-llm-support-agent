# Kafka LLM Support Agent

This repository contains a real-time, event-driven Customer Support AI Agent. It uses **Kafka** for message streaming and **LangGraph** (powered by local **Ollama** models) to analyze, categorize, and auto-reply to customer support tickets.

## Architecture

1. **Producer (`producer.py`)**: Simulates a customer support portal. Streams custom JSON support tickets (e.g., billing disputes, technical issues, praise) into a Kafka `support-tickets` topic.
2. **Consumer / Agent (`support_agent.py`)**: A LangGraph application that subscribes to the Kafka topic. 
3. **LLM Engine**: When a ticket arrives, the LangGraph node uses a local `llama3` model via Ollama to determine the Sentiment and Category of the ticket, and drafts a categorized, context-aware auto-reply.

## Prerequisites
* Python 3.10+
* Local Kafka Broker running (`localhost:9092`)
* [Ollama](https://ollama.com/) installed and running locally.

## Setup Instructions

1. **Start Ollama & Pull the Model**:
   ```bash
   ollama serve
   ollama pull llama3
   ```

2. **Run the Consumer (Agent)**:
   In one terminal, start the LangGraph agent to listen for tickets:
   ```bash
   python support_agent.py
   ```

3. **Run the Producer**:
   In a separate terminal, stream mock tickets into Kafka:
   ```bash
   python producer.py
   ```

---

## 📚 Step-By-Step Learning Log
*A version history of how this project was built for learning reference.*

### Version 1: Defining the Business Use Case
* **Goal**: Upgrade the generic "order" stream into a real-world scenario.
* **Code**: Modified `producer.py`.
* **What I Did**: Changed the topic from `orders` to `support-tickets`. Updated the payload to JSON dictionaries containing a `ticket_id`, `customer_name`, and complex `issue_text`. Simulated a variety of ticket types (angry billing, broken tech, happy reviews).

### Version 2: Integrating the LLM (LangGraph + Ollama)
* **Goal**: Dynamically process the text inside the Kafka stream using AI.
* **Code**: Created `support_agent.py`.
* **What I Did**: 
  1. Built a LangGraph state machine with an `analyze_ticket` node and a `process_action` node.
  2. Integrated `langchain_ollama` to securely and locally use LLMs without paying API fees.
  3. Replaced the generic consumer logic with code that feeds the Kafka message payload directly into the LangGraph state. 
  4. Prompt-engineered the LLM to strictly return only the Sentiment and Category, which the second node uses to generate a mock response.
