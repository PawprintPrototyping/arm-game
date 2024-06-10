import os
import sqlite3

DATABASE = os.getenv("DATABASE", "/home/pi/scores.db")
def init_db():
    db = sqlite3.connect(DATABASE, isolation_level=None)
    db.execute("CREATE TABLE IF NOT EXISTS scores(id INTEGER PRIMARY KEY, name TEXT, score INTEGER);")
    return db

def get_high_scores(db):
    sth = db.execute("SELECT * FROM scores ORDER BY score DESC LIMIT 10")
    return sth.fetchall()

if __name__ == "__main__":
    db = init_db()
    high_scores = get_high_scores(db)

    print("""
     _   _ ___ ____ _   _   ____   ____ ___  ____  _____ ____  
    | | | |_ _/ ___| | | | / ___| / ___/ _ \|  _ \| ____/ ___| 
    | |_| || | |  _| |_| | \___ \| |  | | | | |_) |  _| \___ \ 
    |  _  || | |_| |  _  |  ___) | |__| |_| |  _ <| |___ ___) |
    |_| |_|___\____|_| |_| |____/ \____\___/|_| \_\_____|____/ 
                                                               
    """)

    for idx, row in enumerate(high_scores):
        print(f"                   {idx+1:2}: {row[2]}  {row[1]}")
