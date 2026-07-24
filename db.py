import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

def insert_uploaded_file(file_name, file_type, parse_status="pending"):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        INSERT INTO uploaded_files (file_name, file_type, parse_status)
        VALUES (%s, %s, %s)
    """
    cursor.execute(query, (file_name, file_type, parse_status))
    conn.commit()

    file_id = cursor.lastrowid

    cursor.close()
    conn.close()
    return file_id

def get_event_type_id(type_name):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT event_type_id FROM event_types WHERE type_name = %s"
    cursor.execute(query, (type_name,))
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    if result:
        return result[0]
    return None

def insert_parsed_events(file_id, events):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        INSERT INTO parsed_events
        (file_id, event_type_id, title, event_date, confidence_score, status)
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    for event in events:
        event_type_id = get_event_type_id(event["event_type"])
        if event_type_id is None:
            other_id = get_event_type_id("Other")
            event_type_id = other_id

        cursor.execute(query, (
            file_id,
            event_type_id,
            event["title"],
            event["event_date"],
            event.get("confidence_score", 0.80),
            event.get("status", "draft")
        ))

    conn.commit()
    cursor.close()
    conn.close()


def update_file_status(file_id, status):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "UPDATE uploaded_files SET parse_status = %s WHERE file_id = %s"
    cursor.execute(query, (status, file_id))

    conn.commit()
    cursor.close()
    conn.close()

def save_session(raw_json):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_session")
    cursor.execute("INSERT INTO active_session (raw_json) VALUES (%s)", (raw_json,))
    conn.commit()
    cursor.close()
    conn.close()

def load_session():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT raw_json FROM active_session ORDER BY session_id DESC LIMIT 1")
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else None

def clear_session():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM active_session")
    conn.commit()
    cursor.close()
    conn.close()