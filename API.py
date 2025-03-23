import hashlib

from fastapi import FastAPI

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
import mysql.connector
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler

from leaguepedia import *
from Bets import *

app = FastAPI()
scheduler = BackgroundScheduler()


def update_matches():
    mydb = mysql.connector.connect(
        host="localhost",
        user="modo",
        password="",
        database="pronosmodo"
    )
    mycursor = mydb.cursor()

    mycursor.execute("SELECT team1, team2, date, status FROM matches")
    saved_matches = {(team1, team2, date.strftime("%Y-%m-%d %H:%M:%S")):status for team1, team2, date, status in mycursor.fetchall()} #2025-03-17 16:00:00
    competitions = get_competitions()
    for competition in competitions:
        schedule = get_schedule(competition["Name"])
        for match in schedule:
            tournament = match['Name']
            team1 = match["Short1"] if match["Short1"] is not None else "TBD"
            score1 = match["Team1Score"]
            team2 = match["Short2"] if match["Short2"] is not None else "TBD"
            score2 = match["Team2Score"]
            date = match["Date"]
            status = match["Status"]
            if (team1, team2, date) in saved_matches:
                if saved_matches[(team1, team2, date)] == status and status == "Done":
                    continue
                # Match exists, update it
                sql = """
                            UPDATE matches 
                            SET score1 = %s, score2 = %s, status = %s
                            WHERE team1 = %s AND team2 = %s AND date = %s
                        """
                mycursor.execute(sql, (score1, score2, status, team1, team2, date))
            else:
                # Match does not exist, insert it
                sql = """
                                    INSERT INTO matches (tournament, team1, team2, score1, score2, date, status) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """
                mycursor.execute(sql, (tournament, team1, team2, score1 if score1 is not None else 0, score2 if score2 is not None else 0, date, status))
    mydb.commit()

    date = datetime.now(timezone.utc)
    sql = "SELECT name FROM tournaments WHERE start < %s AND end > %s;"
    mycursor.execute(sql, (date, date-timedelta(days=1)))
    saved_competitions = [n[0] for n in mycursor.fetchall()]
    for competition in competitions:
        if competition["Name"] not in saved_competitions:
            sql = "INSERT INTO tournaments (name, start, end) VALUES (%s, %s, %s)"
            mycursor.execute(sql, (competition["Name"], competition["Start"], competition["End"]))
        else:
            continue
    mydb.commit()


    mycursor.execute("SELECT id, team1, team2, tournament, score1, score2 FROM matches WHERE status = 'Done'")
    matches = mycursor.fetchall()
    mycursor.execute(f"SELECT modo, matchid, team1bet, team2bet FROM bets")
    bets_ = mycursor.fetchall()
    bets = dict()
    for bet in bets_:
        if bet[1] not in bets:
            bets[bet[1]] = [(bet[0], Bet("", "", bet[2], bet[3]))]
        else:
            bets[bet[1]].append((bet[0], Bet("", "", bet[2], bet[3])))
    results = dict()
    for match in matches:
        if match[0] not in results:
            results[match[0]] = (match[3], Result(match[1], match[2], match[4], match[5]))

    modos = dict()
    for r_ in results:
        for b_ in bets:
            if r_!=b_:
                continue
            r = results[r_]
            for b in bets[b_]:
                if not b[0] in modos:
                    modos[b[0]] = dict()
                if not r[0] in modos[b[0]]:
                    modos[b[0]][r[0]] = (b[1] + r[1], 1, b[1] + r[1] == b[1].bo)
                else:
                    s = b[1] + r[1]
                    modos[b[0]][r[0]] = (modos[b[0]][r[0]][0] + s, modos[b[0]][r[0]][1]+1,  modos[b[0]][r[0]][2] + 1 if s==b[1].bo else modos[b[0]][r[0]][2])
    mycursor.execute(f"SELECT modo, tournament FROM scores")
    scores = {(modo, tournament) for modo, tournament in mycursor.fetchall()}
    for m in modos:
        for t in modos[m]:
            if (m, t) in scores:
                sql = """
                            UPDATE scores
                            SET scores.num_bets = %s, score = %s, perfect = %s
                            WHERE modo = %s AND tournament = %s
                """
                mycursor.execute(sql, (modos[m][t][1], modos[m][t][0], modos[m][t][2], m, t))
            else:
                sql = """
                        INSERT INTO scores (modo, tournament, num_bets, score, perfect) 
                        VALUES (%s, %s, %s, %s, %s)
                """
                mycursor.execute(sql, (m, t, modos[m][t][1],modos[m][t][0], modos[m][t][2]))
    mydb.commit()

    mydb.close()

update_matches()
scheduler.add_job(update_matches, 'interval', minutes=1)
scheduler.start()

@app.get("/")
async def root():
    return {"connection":"OK"}

@app.post("/bet")
async def bet(modo:int, gameid:int, score1:int, score2:int):
    mydb = mysql.connector.connect(
        host="localhost",
        user="modo",
        password="",
        database="pronosmodo"
    )
    mycursor = mydb.cursor()
    mycursor.execute(
        "INSERT INTO bets (modo, matchid, team1bet, team2bet, date) VALUES (%s, %s, %s, %s, %s)",
        (modo, gameid, score1, score2, datetime.now(timezone.utc)),
    )
    mydb.commit()
    mydb.close()

@app.post("/signin")
async def signin(modo:str):
    id = hashlib.sha256(modo.encode()).hexdigest()
    mydb = mysql.connector.connect(
        host="localhost",
        user="modo",
        password="",
        database="pronosmodo"
    )
    mycursor = mydb.cursor()
    mycursor.execute("INSERT INTO modos (id, name) VALUES (%s, %s)", (id, modo))
    mydb.commit()
    mydb.close()
    return JSONResponse({"id": id}, status_code=200)

@app.get("/competitions")
async def competitions():
    mydb = mysql.connector.connect(
        host="localhost",
        user="modo",
        password="",
        database="pronosmodo"
    )
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT id, name, start, end FROM tournaments ORDER BY end DESC"
    mycursor.execute(sql)
    results = mycursor.fetchall()  # Fetch all results as dictionaries

    mycursor.close()
    mydb.close()

    return JSONResponse(content=jsonable_encoder(results))

@app.get("/matches")
async def matches(competition:int):
    date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    mydb = mysql.connector.connect(
        host="localhost",
        user="modo",
        password="",
        database="pronosmodo"
    )
    mycursor = mydb.cursor(dictionary=True)
    sql = """SELECT m.id, m.team1, m.team2, m.score1, m.score2, m.date, m.status FROM matches AS m 
             JOIN tournaments AS t ON m.tournament=t.name 
             WHERE m.date >= %s AND t.id = %s"""
    mycursor.execute(sql, (date, competition))
    results = mycursor.fetchall()
    mycursor.close()
    mydb.close()

    return JSONResponse(content=jsonable_encoder(results))

@app.get("/bets")
async def bets(modo:int):
    mydb = mysql.connector.connect(
        host="localhost",
        user="modo",
        password="",
        database="pronosmodo"
    )
    mycursor = mydb.cursor(dictionary=True)
    sql = """SELECT b.id, m.team1, m.team2, b.team1bet, m.score1, b.team2bet, m.score2, m.date FROM bets AS b 
             JOIN matches AS m ON m.id=b.matchid 
             WHERE b.modo = %s
             LIMIT 20"""
    mycursor.execute(sql, (modo,))
    results = mycursor.fetchall()
    mycursor.close()
    mydb.close()

    return JSONResponse(content=jsonable_encoder(results))

@app.get("/ranking")
async def ranking(competition:int):
    mydb = mysql.connector.connect(
        host="localhost",
        user="modo",
        password="",
        database="pronosmodo"
    )
    mycursor = mydb.cursor(dictionary=True)
    sql = """SELECT m.name, s.num_bets, s.score FROM scores AS s
             JOIN modos AS m ON m.id=s.modo
             JOIN tournaments AS t ON s.tournament=t.name 
             WHERE t.id = %s
             ORDER BY s.score DESC"""
    mycursor.execute(sql, (competition,))
    results = mycursor.fetchall()
    mycursor.close()
    mydb.close()

    return JSONResponse(content=jsonable_encoder(results))