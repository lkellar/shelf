import sqlite3
import json
import random

from datetime import datetime, timedelta

class DBManager:

    def __init__(self, db_path: str, word_path: str):

        with sqlite3.connect(db_path) as conn:
            # connecting to the database and creating the shelf table if
            # it doesn't exist
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS shelf 
            (id text PRIMARY KEY UNIQUE, data text, private BOOLEAN, visits INTEGER DEFAULT 0, max_visits INTEGER DEFAULT 1, insert_date TIMESTAMP, expiry_date TIMESTAMP)''')

        with open(word_path, 'r') as f:
            self.words = json.load(f)


    def insert(self, id: str, data: str, private: bool, ttl_days: int, max_visits: int, c: sqlite3.Cursor):
        # gets the current time (in utc)
        utc_date = datetime.utcnow()

        # calculates the day the note should expire
        expiry_date = utc_date + timedelta(days=ttl_days)

        c.execute('INSERT INTO shelf (id, data, private, insert_date, expiry_date, max_visits) VALUES (?, ?, ?, ?, ?, ?)',
                  (id, data, private, utc_date, expiry_date, max_visits))
        c.connection.commit()

    def fetchOne(self, id: str, c: sqlite3.Cursor):
        c.execute('SELECT * FROM shelf WHERE id = ?', (id,))
        return c.fetchone()

    def generateID(self, c: sqlite3.Cursor) -> str:
        # generates a word id from simple word list
        id = f'{random.choice(self.words)}-{random.choice(self.words)}'

        # checks if ID already exists. The chances of two identical IDs are
        # one in a million, but just to be safe, it checks.

        c.execute('SELECT EXISTS(SELECT 1 FROM shelf WHERE id=? LIMIT 1)', (id,))

        # if another ID happens to exist, just grab a new one
        if c.fetchone()[0] == 1:
            return self.generateID(c)

        return id
