import sqlite3

import config

# connection is a static variable that is shared across all instances of DB
# so we reuse the same connection across all users of this class
class Database():
    connection = None
    def _init__(self):
        if Database.connection is None:
            Database.connection = sqlite3.connect(config.settings.db.filename)
        cur = Database.connection.cursor() 
        cur.execute("""CREATE TABLE IF NOT EXISTS runs
            (user TEXT, code TEXT, day INTEGER, part INTEGER, time REAL, answer INTEGER, answer2)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS solutions
            (key TEXT, day INTEGER, part INTEGER, answer INTEGER, answer2)""")
        Database.connection.commit()

    def get(self):
        if not Database.connection:
            self._init__()
        return Database.connection
    