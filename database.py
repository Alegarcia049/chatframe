import sqlite3
import os

DB_PATH = "business.db"

def get_connection():
    """Returns a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initializes the database schema if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Sales Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            region TEXT,
            channel TEXT
        )
    ''')
    
    # Expenses Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL
        )
    ''')
    
    # Customers Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            segment TEXT,
            active BOOLEAN DEFAULT 1
        )
    ''')

    # Nueva tabla de Auditoría
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            user_message TEXT,
            ai_response TEXT,
            thread_id TEXT,
            tokens_estimate INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

def log_interaction(user_msg: str, ai_msg: str, thread_id: str):
    """Guarda la interacción en la base de datos."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO audit_logs (user_message, ai_response, thread_id) VALUES (?, ?, ?)",
            (user_msg, ai_msg, thread_id)
        )
        conn.commit()
    finally:
        conn.close()