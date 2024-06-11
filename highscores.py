import os
import serial
import sqlite3
import pprint

DATABASE = os.getenv("DATABASE", "/home/pi/scores.db")
KAYDISPLAY_TTY = '/dev/ttyKayDisplay'
KAYDISPLAY_BAUD = 115200

def init_db():
    db = sqlite3.connect(DATABASE, isolation_level=None)
    db.execute("CREATE TABLE IF NOT EXISTS scores(id INTEGER PRIMARY KEY, name TEXT, score INTEGER);")
    return db

def get_high_scores(db):
    sth = db.execute("SELECT * FROM scores ORDER BY score DESC LIMIT 10")
    return sth.fetchall()

def get_last_score(db):
    sth = db.execute("SELECT * FROM scores ORDER BY id DESC LIMIT 1")
    return sth.fetchall()

def send_kay_scores(high_scores, last_score):
    '''
    Kay Scoreboard:
    - 115200 8N1.
    - Expects 8 ASCII numbers followed by a single newline.
    - Interprets 0xff as an off digit.
    - Scoreboard is currently broken up with first 4 digits as "HIGH SCORE" and last 4 as "YOUR SCORE"
    '''
    bare_high_score = high_scores[0][2]
    bare_last_score = last_score[0][2]
    payload = (str(bare_high_score).rjust(4, ' ') + str(bare_last_score).rjust(4, ' ') + '\n').encode('latin1').replace(b' ', b'\\xff')
    #ser.write(payload)
    #ser.close()
    # OK - SO - There's a reason.
    # It's not a good reason.
    # But it's a reason.
    # Despite our best efforts, pyserial always diddles the DTR line, causing the arduino to reset and rake 3 seconds to reboot.
    # We can use stty's -hupcl option to kinda help with this, but pyserial is too smart - it'll undo this when it exists.
    # ...so, we're shelling out. Because I'm out of braincells and fucks to give.
    # Update: guess what, it got worse.
    # Shelling out isn't enough.
    # We need a full bash instance, because our ancestors thought it would be funny to make sand think.
    # Something about builtins.
    # GLHF
    os.system("stty -crtscts -hupcl -F /dev/ttyKayDisplay 115200")
    cmd = '/bin/bash -c \'echo -en "{}" > /dev/ttyKayDisplay\''.format(payload.decode('latin1'))
    os.system(cmd)

if __name__ == "__main__":
    db = init_db()
    high_scores = get_high_scores(db)
    last_score = get_last_score(db)
    send_kay_scores(high_scores, last_score)


    print("""
     _   _ ___ ____ _   _   ____   ____ ___  ____  _____ ____  
    | | | |_ _/ ___| | | | / ___| / ___/ _ \|  _ \| ____/ ___| 
    | |_| || | |  _| |_| | \___ \| |  | | | | |_) |  _| \___ \ 
    |  _  || | |_| |  _  |  ___) | |__| |_| |  _ <| |___ ___) |
    |_| |_|___\____|_| |_| |____/ \____\___/|_| \_\_____|____/ 
                                                               
    """)

    for idx, row in enumerate(high_scores):
        print(f"                   {idx+1:2}: {row[2]}  {row[1]}")
