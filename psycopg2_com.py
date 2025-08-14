import psycopg2
import json

def conn_db():
     # Încarcă datele din config.json
    with open("config.json") as f:
        config = json.load(f)

    conn = psycopg2.connect(
        dbname=config['db']["db_name"],
        user=config['db']["db_user"],
        password=config['db']["db_pass"],
        host=config['db']["db_host"],
        port="5432"
    )
    return conn

def get_comment_sync(cnt_comm):
    conn = conn_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM comment_sync WHERE id > %s ORDER BY id ASC;",
        (cnt_comm,) 
    )
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return rows

def get_jira_key(comment_id):
    conn = conn_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT jira_issue_key FROM comment_sync WHERE jira_comment_id = %s;",
        (comment_id,)
    )

    result = cursor.fetchone()

    cursor.close()
    conn.close()

    if result:
        return result[0]  # jira_issue_key
    else:
        return None

def get_webhook_body(comment_id):
    conn = conn_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT comment_body FROM comment_sync WHERE jira_comment_id = %s;",
        (comment_id,)
    )
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    if result:
        return result[0]  # jira_issue_key
    else:
        return None

def drop_sync_tables():
    conn = conn_db()
    cursor = conn.cursor()

    # Șterge tabelele dacă există
    tables = ["comment_sync", "ticket_sync", "status_sync", "counter_sync", 'note_sync', 'issue_sync', 'status_sync_to_jira']
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table};")
        print(f"[✔] Tabelul '{table}' a fost șters (dacă exista).")

    conn.commit()
    cursor.close()
    conn.close()

def insert_id_ticket_sync(sdp_id, key):
    conn = conn_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE ticket_sync
        SET sdp_id = %s
        WHERE jira_issue_key = %s;
    """, (sdp_id, key))

    conn.commit()
    cursor.close()
    conn.close()

def get_sdp_id(key):
    conn = conn_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sdp_id FROM ticket_sync WHERE jira_issue_key = %s;",
        (key,)
    )

    result = cursor.fetchone()

    cursor.close()
    conn.close()

    if result:
        return result[0]  # sdp_id
    else:
        return None

def get_ticket_sync(cnt_ticket):
    conn = conn_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ticket_sync  WHERE id > %s ORDER BY id ASC;",
        (cnt_ticket,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return rows

def get_status_sync(cnt_status):
    conn = conn_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM status_sync  WHERE id > %s ORDER BY id ASC;",
        (cnt_status,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return rows

def counter_db(cnt_ticket, cnt_comm, cnt_status):
    conn = conn_db()
    cursor = conn.cursor()

    # Creează tabelul dacă nu există
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS counter_sync(
            id SERIAL PRIMARY KEY,
            last_ticket VARCHAR(50),
            last_comment VARCHAR(50),
            last_status_update VARCHAR(50)    
        );
    """)
    conn.commit()

    # Inserează datele
    cursor.execute("""
        INSERT INTO counter_sync (last_ticket, last_comment, last_status_update)
        VALUES (%s, %s, %s);
    """, (cnt_ticket, cnt_comm, cnt_status))

    conn.commit()
    cursor.close()
    conn.close()

def get_counter():
    conn = conn_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM counter_sync ORDER BY id DESC LIMIT 1;")
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return rows


#sdp to jira
def get_issue_sync(cnt_issue):
    conn = conn_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM issue_sync  WHERE id > %s ORDER BY id ASC;",
        (cnt_issue,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return rows

def get_note_sync(cnt_note):
    conn = conn_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM note_sync WHERE id > %s ORDER BY id ASC;",
        (cnt_note,) 
    )
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return rows

def get_status_sync_to_jira(cnt_status):
    conn = conn_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM status_sync_to_jira  WHERE id > %s ORDER BY id ASC;",
        (cnt_status,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return rows

def insert_key_issue_sync(key, sdp_id):
    conn = conn_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE issue_sync
        SET jira_issue_key = %s
        WHERE sdp_id= %s;
    """, (key, sdp_id))

    conn.commit()
    cursor.close()
    conn.close()

def counter_sdp(cnt_issue, cnt_note, cnt_status):
    conn = conn_db()
    cursor = conn.cursor()

    # Creează tabelul dacă nu există
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS counter_sync_sdp(
            id SERIAL PRIMARY KEY,
            last_issue VARCHAR(50),
            last_note VARCHAR(50),
            last_status_sdp VARCHAR(50)    
        );
    """)
    conn.commit()

    # Inserează datele
    cursor.execute("""
        INSERT INTO counter_sync_sdp (last_issue, last_note, last_status_sdp)
        VALUES (%s, %s, %s);
    """, (cnt_issue, cnt_note, cnt_status))

    conn.commit()
    cursor.close()
    conn.close()

def get_counter_sdp():
    conn = conn_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM counter_sync_sdp ORDER BY id DESC LIMIT 1;")
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return rows

def get_issue_key(sdp_id):
    conn = conn_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT jira_issue_key FROM issue_sync WHERE sdp_id = %s;",
        (sdp_id,)
    )

    result = cursor.fetchone()

    cursor.close()
    conn.close()

    if result:
        return result[0]  # jira_issue_key
    else:
        return None