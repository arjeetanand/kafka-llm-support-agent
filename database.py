import sqlite3
from datetime import datetime

DB_NAME = "support_tickets.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE,
            customer_name TEXT,
            issue_text TEXT,
            sentiment TEXT,
            category TEXT,
            draft_reply TEXT,
            tools_executed BOOLEAN,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_ticket(data):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO tickets (ticket_id, customer_name, issue_text, sentiment, category, draft_reply, tools_executed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get("ticket_id"),
            data.get("customer_name"),
            data.get("issue_text"),
            data.get("sentiment"),
            data.get("category"),
            data.get("draft_reply"),
            data.get("tools_executed", False)
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        # Ticket already exists, skipping
        pass
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

def get_all_tickets(limit=50):
    conn = sqlite3.connect(DB_NAME)
    # Return as list of dicts
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tickets ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    tickets = [dict(row) for row in rows]
    conn.close()
    return tickets

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM tickets')
    total = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM tickets WHERE tools_executed = 1')
    actions = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM tickets WHERE sentiment = "Negative"')
    negatives = cursor.fetchone()[0]
    
    conn.close()
    return {"total": total, "actions": actions, "negatives": negatives}

if __name__ == "__main__":
    init_db()
    print(f"Database {DB_NAME} initialized.")
