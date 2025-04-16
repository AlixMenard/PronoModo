from collections import defaultdict

import mysql.connector
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mysql.connector.abstracts import MySQLConnectionAbstract
from mysql.connector.pooling import PooledMySQLConnection
from pydantic import BaseModel

import secrets
import hashlib

from bets import *
from leaguepedia import *

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

scheduler = BackgroundScheduler()

def get_session() -> PooledMySQLConnection | MySQLConnectionAbstract:
    return mysql.connector.connect(
        host="db-test",
        port=3306,
        user="root",
        password="azbecbaboevav",
        database="pronosmodo"
    )

def get_token():
    return secrets.token_hex(32)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def update_matches():
    mydb = get_session()
    mycursor = mydb.cursor()

    mycursor.execute("SELECT team1, team2, date, status FROM matches")
    saved_matches = {(team1, team2, date.strftime("%Y-%m-%d %H:%M:%S")): status for team1, team2, date, status in
                     mycursor.fetchall()}  # 2025-03-17 16:00:00
    competitions = get_competitions()
    for competition in competitions:
        schedule = get_schedule(competition["Name"])
        for match in schedule:
            tournament = match['Name']
            team1 = match["Short1"] if match["Short1"] is not None else "TBD"
            score1 = match["Team1Score"]
            score1 = score1 if score1 is not None else 0
            team2 = match["Short2"] if match["Short2"] is not None else "TBD"
            score2 = match["Team2Score"]
            score2 = score2 if score2 is not None else 0
            bo = match["BestOf"]
            date = match["Date"]
            status = match["Status"]
            if (team1, team2, date) in saved_matches:
                if saved_matches[(team1, team2, date)] == status and status == "Done":
                    continue
                # Match exists, update it
                sql = """
                            UPDATE matches 
                            SET score1 = %s, score2 = %s, status = %s, bo = %s
                            WHERE team1 = %s AND team2 = %s AND date = %s
                        """
                mycursor.execute(sql, (score1, score2, status, bo, team1, team2, date))
            else:
                # Match does not exist, insert it
                sql = """
                                    INSERT INTO matches (tournament, team1, team2, score1, score2, bo, date, status) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                """
                mycursor.execute(sql, (tournament, team1, team2, score1, score2, bo, date, status))
    mydb.commit()

    date = datetime.now(timezone.utc)
    sql = "SELECT name FROM tournaments WHERE end > %s;"
    mycursor.execute(sql, (date-timedelta(days=1),))
    saved_competitions = [n[0] for n in mycursor.fetchall()]
    for competition in competitions:
        if competition["Name"] not in saved_competitions:
            if competition["End"] is None:
                competition["End"] = datetime.now(timezone.utc) + timedelta(days=100)
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
    max_points = defaultdict(int)
    for match in matches:
        if match[0] not in results:
            results[match[0]] = (match[3], Result(match[1], match[2], match[4], match[5]))
            max_points[match[3]] += results[match[0]][1].bo

    modos = dict()
    for r_ in results:
        for b_ in bets:
            if r_ != b_:
                continue
            r = results[r_]
            for b in bets[b_]:
                if not b[0] in modos:
                    modos[b[0]] = dict()
                if not r[0] in modos[b[0]]:
                    modos[b[0]][r[0]] = (b[1] + r[1], 1, b[1] + r[1] == b[1].bo, b[1].bo) #score, num_bets, perfect | pts_max (somme .bo)
                else:
                    s = b[1] + r[1]
                    modos[b[0]][r[0]] = (modos[b[0]][r[0]][0] + s, modos[b[0]][r[0]][1] + 1,
                                         modos[b[0]][r[0]][2] + 1 if s == b[1].bo else modos[b[0]][r[0]][2], modos[b[0]][r[0]][3] + b[1].bo)
    mycursor.execute(f"SELECT modo, tournament FROM scores")
    scores = {(modo, tournament) for modo, tournament in mycursor.fetchall()}
    for m in modos:
        for t in modos[m]:
            if (m, t) in scores:
                sql = """
                            UPDATE scores
                            SET scores.num_bets = %s, score = %s, perfect = %s, rating = %s, accuracy = %s
                            WHERE modo = %s AND tournament = %s
                """
                mycursor.execute(sql, (modos[m][t][1], modos[m][t][0], modos[m][t][2],
                                       round(modos[m][t][0]/max_points[t],2), round(modos[m][t][0]/modos[m][t][3],2),
                                       m, t))
            else:
                sql = """
                        INSERT INTO scores (modo, tournament, num_bets, score, perfect) 
                        VALUES (%s, %s, %s, %s, %s)
                """
                mycursor.execute(sql, (m, t, modos[m][t][1], modos[m][t][0], modos[m][t][2]))
    mydb.commit()

    mydb.close()


update_matches()
scheduler.add_job(update_matches, 'interval', minutes=1)
scheduler.start()


@app.get("/health")
async def health():
    return {"status": "HEALTHY"}


@app.post("/bet")
async def bet(modo: int, token:str, gameid: int, score1: int, score2: int):
    mydb = get_session()
    mycursor = mydb.cursor()

    #? ID check
    sql = """
            SELECT token, last_refresh FROM modos WHERE id = %s
          """
    mycursor.execute(sql, (modo,))
    db_modo = mycursor.fetchall()[0]
    if db_modo[1].tzinfo is None:
        db_modo[1] = db_modo[1].replace(tzinfo=timezone.utc)
    else:
        db_modo[1] = db_modo[1]
    if token != db_modo[0]:
        mydb.commit()
        mydb.close()
        return {'status': 'Incorrect token'}
    if db_modo[1] < datetime.now(timezone.utc) - timedelta(30):
        mydb.commit()
        mydb.close()
        return {'status': 'Expired token'}


    mycursor.execute("SELECT * from bets WHERE modo = %s AND matchid = %s", (modo, gameid))
    bets = mycursor.fetchall()
    now = datetime.now(timezone.utc)
    mycursor.execute("SELECT bo FROM matches WHERE id = %s", (gameid,))
    bo = mycursor.fetchone()[0]

    m = max(score1, score2)
    if m*2 -1 != bo or score1+score2 > bo:
        return {"status": "Fail", "message": "Incorrect bet"}

    if bets:
        sql = """
                UPDATE bets 
                SET team1bet = %s, team2bet = %s, date = %s
                WHERE modo = %s AND matchid = %s
                """
        params = (score1, score2, now, modo, gameid)
        action = "Bet modified"
    else:
        sql = """
                INSERT INTO bets (modo, matchid, team1bet, team2bet, date)
                VALUES (%s, %s, %s, %s, %s)
                """
        params = (modo, gameid, score1, score2, now)
        action = "Bet added"

    mycursor.execute(sql, params)
    mydb.commit()
    mydb.close()
    return {"status" : "Success", "action" : action}


@app.post("/signin")
async def signin(modo: str, password: str):
    hash_pwd = hash_password(password)
    mydb = get_session()
    mycursor = mydb.cursor()

    mycursor.execute("SELECT id, name, password FROM modos WHERE name = %s", (modo,))
    modos = mycursor.fetchall()
    if modos:
        if modos[0][2] is None or modos[0][2] == hash_pwd:
            token = get_token()
            sql = """
                    UPDATE modos 
                    SET password = %s, token = %s, last_refresh = %s
                    WHERE name = %s
                """
            mycursor.execute(sql, (hash_pwd, token, datetime.now(timezone.utc), modo))
            mydb.commit()
            mydb.close()
            return {'id': modos[0][0], 'name': modos[0][1], 'token': token}
        else:
            mydb.commit()
            mydb.close()
            return {'status' : "Incorrect password."}

    mycursor.execute("INSERT INTO modos (name) VALUES (%s)", (modo,))
    modo_id = mycursor.lastrowid
    mydb.commit()
    mydb.close()
    return {'id': modo_id, 'name': modo}


@app.get("/competitions")
async def competitions():
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT id, name, start, end FROM tournaments ORDER BY end DESC"
    mycursor.execute(sql)
    results = mycursor.fetchall()  # Fetch all results as dictionaries

    mycursor.close()
    mydb.close()

    return JSONResponse(content=jsonable_encoder(results))


@app.get("/matches")
async def matches(competition: int):
    date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)
    sql = """SELECT m.id, m.team1, m.team2, m.score1, m.score2, m.bo, m.date, m.status FROM matches AS m 
             JOIN tournaments AS t ON m.tournament=t.name 
             WHERE m.date >= %s AND t.id = %s"""
    mycursor.execute(sql, (date, competition))
    results = mycursor.fetchall()
    mycursor.close()
    mydb.close()

    return JSONResponse(content=jsonable_encoder(results))


@app.get("/bets")
async def bets(modo: int):
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)
    sql = """SELECT b.id, m.team1, m.team2, b.team1bet, m.score1, b.team2bet, m.score2, m.date FROM bets AS b 
             JOIN matches AS m ON m.id=b.matchid 
             WHERE b.modo = %s
             ORDER BY m.date DESC 
             LIMIT 50"""
    mycursor.execute(sql, (modo,))
    results = mycursor.fetchall()
    mycursor.close()
    mydb.close()

    return JSONResponse(content=jsonable_encoder(results))


@app.get("/ranking")
async def ranking(competition: int):
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)
    sql = """SELECT m.name, s.num_bets, s.score, s.rating, s.accuracy FROM scores AS s
             JOIN modos AS m ON m.id=s.modo
             JOIN tournaments AS t ON s.tournament=t.name 
             WHERE t.id = %s
             ORDER BY s.score DESC"""
    mycursor.execute(sql, (competition,))
    results = mycursor.fetchall()
    mycursor.close()
    mydb.close()

    return JSONResponse(content=jsonable_encoder(results))

class LogoResponse(BaseModel):
    url: str

@app.get("/logo")
async def logo(team: str):
    url = get_team_logo_url(team.upper())
    if url is None:
        raise HTTPException(status_code=404, detail="Team logo not found")
    return LogoResponse(url=url)

#? admin routes
@app.get("/admin/users")
async def users():
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)

    sql = "SELECT id, name FROM modos"
    mycursor.execute(sql)
    results = mycursor.fetchall()
    mydb.close()
    return results

@app.delete("/admin/user")
async def del_user(id : int):
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)
    sql = "DELETE FROM modos WHERE id = %s"
    mycursor.execute(sql, (id,))
    mydb.commit()
    mydb.close()
    return {"status": "success", "message": f"User {id} deleted"}

@app.delete("/admin/cancel")
async def cancel(id : int):
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)
    sql = "DELETE FROM bets WHERE id = %s"
    mycursor.execute(sql, (id,))
    mydb.commit()
    mydb.close()
    return {"status": "success", "message": f"Bet {id} cancelled"}

@app.delete("/admin/competition")
async def del_competition(id : int):
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT * FROM tournaments WHERE id = %s"
    mycursor.execute(sql, (id,))
    results = mycursor.fetchall()
    if results:
        sql = "DELETE FROM tournaments WHERE id = %s"
        mycursor.execute(sql, (id,))
        mydb.commit()
        mydb.close()
        return {"status": "success", "message": f"Tournament {id} deleted"}
    return {"status": "fail", "message": f"Tournament {id} not found"}

