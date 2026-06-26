import sqlite3
import json

def inspect():
    conn = sqlite3.connect("db.sqlite3")
    cursor = conn.cursor()
    
    print("--- TABLES ---")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(tables)
    
    print("\n--- AGNIVEER STATUS COUNTS ---")
    cursor.execute("SELECT status, COUNT(*) FROM departments_agniveer GROUP BY status;")
    print(cursor.fetchall())
    
    print("\n--- AGNIVEER TRADE COUNTS ---")
    cursor.execute("SELECT trade, COUNT(*) FROM departments_agniveer GROUP BY trade;")
    print(cursor.fetchall())
    
    print("\n--- AGNIVEER BN_DESP COUNTS ---")
    cursor.execute("SELECT bn_desp, COUNT(*) FROM departments_agniveer GROUP BY bn_desp;")
    print(cursor.fetchall())

    print("\n--- EVALUATION SHEET DEPARTMENTS ---")
    cursor.execute("SELECT department, COUNT(*) FROM evaluation_evaluationsheet GROUP BY department;")
    print(cursor.fetchall())

    print("\n--- EVALUATION SHEET TEST TYPES ---")
    cursor.execute("SELECT test_type, COUNT(*) FROM evaluation_evaluationsheet GROUP BY test_type;")
    print(cursor.fetchall())

    print("\n--- SAMPLE AGNIVEER RECORDS ---")
    cursor.execute("SELECT name, trade, bn_desp, status FROM departments_agniveer LIMIT 10;")
    print(cursor.fetchall())
    
    conn.close()

if __name__ == "__main__":
    inspect()
