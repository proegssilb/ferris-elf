from sqlite4 import SQLite4

from config import settings

db = SQLite4(settings.db.filename)
db.connect()
cur = db.cursor();

sum = 0
for day in range(1, 26):
    for part in range(1, 3):
        for (time,) in cur.execute("SELECT MIN(time) FROM runs INNER JOIN solutions on runs.answer2 LIKE solutions.answer2 WHERE solutions.day = ? AND solutions.part = ?", (day, part)):
            print(f"Day {day} part {part}: {time or '-'}ns")
            sum += time or 0

print("Total", sum, "ns")

"""
SELECT user, MIN(time) FROM runs
INNER JOIN solutions
        on runs.answer = solutions.answer
WHERE solutions.day = ? AND solutions.part = 1
GROUP BY user
"""
