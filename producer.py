import json
import uuid

from confluent_kafka import Producer

producer_config = {
    "bootstrap.servers": "localhost:9092"
}

producer = Producer(producer_config)

def delivery_report(err, msg):
    if err:
        print(f"❌ Delivery failed: {err}")
    else:
        print(f"✅ Delivered {msg.value().decode("utf-8")}")
        print(f"✅ Delivered to {msg.topic()} : partition {msg.partition()} : at offset {msg.offset()}")

import random
import time

tickets = [
    {
        "ticket_id": str(uuid.uuid4()),
        "customer_name": "Alice",
        "issue_text": "I was charged twice for my subscription this month. I want a refund for the extra charge.",
    },
    {
        "ticket_id": str(uuid.uuid4()),
        "customer_name": "Bob",
        "issue_text": "The new update completely broke the app on my phone. When will this be fixed?",
    },
    {
        "ticket_id": str(uuid.uuid4()),
        "customer_name": "Charlie",
        "issue_text": "Just wanted to say the support agent yesterday was amazing! Great service.",
    }
]

for ticket in tickets:
    value = json.dumps(ticket).encode("utf-8")
    
    producer.produce(
        topic="support-tickets",
        value=value,
        callback=delivery_report
    )
    
    print(f"Sent ticket: {ticket['issue_text'][:50]}...")
    producer.flush()
    time.sleep(2)
