import sqlite3
import os
import sys
from datetime import datetime

def get_database_path():
    """Return the correct path to data.db, whether frozen or not."""
    if getattr(sys, 'frozen', False):  # 빌드된 exe 파일일 경우
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")  # 개발 중: 현재 경로 기준

    return os.path.join(base_path, "data.db")

DB_PATH = get_database_path()

def get_connection():
    """Return a new connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initialize the database and create tables if they do not exist."""
    conn = get_connection()
    cursor = conn.cursor()
    # Create inventory table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            item_code TEXT UNIQUE NOT NULL,
            category TEXT,
            total_stock INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    # Create request_log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS request_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_code TEXT NOT NULL,
            item_name TEXT NOT NULL,
            quantity_requested INTEGER NOT NULL,
            request_date TEXT NOT NULL,
            requester TEXT
        )
    """)
    conn.commit()
    conn.close()