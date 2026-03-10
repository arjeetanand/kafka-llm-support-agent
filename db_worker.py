import json
import time
from confluent_kafka import Consumer
from database import save_ticket, init_db

def start_db_worker():
    # Ensure DB is initialized
    init_db()
    
    config = {
        'bootstrap.servers': 'localhost:9092',
        'group.id': 'db-persistence-group',
        'auto.offset.reset': 'earliest'
    }
    
    consumer = Consumer(config)
    consumer.subscribe(['processed-tickets'])
    
    print("DB Worker is running and listening for processed tickets...")
    
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue
                
            try:
                val = msg.value().decode('utf-8')
                ticket_data = json.loads(val)
                save_ticket(ticket_data)
                print(f"[DB SAVED] Ticket {ticket_data.get('ticket_id')} for {ticket_data.get('customer_name')}")
            except Exception as e:
                print(f"Error saving to DB: {e}")
                
    except KeyboardInterrupt:
        print("\n[STOP] Stopping DB Worker")
    finally:
        consumer.close()

if __name__ == "__main__":
    start_db_worker()
