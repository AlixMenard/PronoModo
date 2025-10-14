from collections import defaultdict

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from teamdbmethods import *
from datetime import datetime, timedelta, timezone

import secrets
import hashlib

from bets import *
from leaguepedia import *
from leaguepedia import _catch_names, _KNOWN_NAMES

import traceback

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

scheduler = BackgroundScheduler()


def get_token():
    return secrets.token_hex(32)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def update_matches():
    mydb = get_session()
    mycursor = mydb.cursor()

    teams = get_teams()
    team_slugs = [x["slug"] for x in teams]

    mycursor.execute("SELECT leaguepediaId, status FROM matches")
    saved_matches = {id : status for id, status in mycursor.fetchall()}  # 2025-03-17 16:00:00
    competitions = get_competitions()
    for competition in competitions:
        schedule = get_schedule(competition["Name"])
        for match in schedule:
            tournament = match['Name']
            if match["Team1Final"] == "Veni Vidi Vici (Spanish Team)" or match["Team2Final"] == "Veni Vidi Vici (Spanish Team)":
                print("\n"*10)
                print(match)
                print(match["Short1"], match["Short2"])
                s1 = _catch_names(match["Team1Final"])
                s2 = _catch_names(match["Team2Final"])
                print(s1, s2)
                print(s1 in team_slugs, s2 in team_slugs)
                print(team_slugs)
                exit
            team1 = match["Short1"] if (match["Short1"] is not None and match["Short1"] != '') else _catch_names(match["Team1Final"])
            if team1 not in team_slugs:
                register_team(match["Team1Final"], team1, tournament)
                team_slugs.append(team1)
            score1 = match["Team1Score"]
            score1 = int(score1) if (score1 is not None and score1 != '') else 0
            team2 = match["Short2"] if (match["Short2"] is not None and match["Short2"] != '') else _catch_names(match["Team2Final"])
            if team2 not in team_slugs:
                register_team(match["Team2Final"], team2, tournament)
                team_slugs.append(team2)
            score2 = match["Team2Score"]
            score2 = int(score2) if (score2 is not None and score2 != '') else 0
            bo = match["BestOf"]
            date = match["Date"] if (match["Date"] is not None and match["Date"] != '') else datetime.now(timezone.utc)
            status = match["Status"]
            id = match["MatchId"]
            tab = match["Tab"]
            if id in saved_matches:
                if saved_matches[id] == status and status == "Done":
                    continue
                if status == "Done": #If match just finished
                    update_power(team1, team2, score1, score2, bo)
                # Match exists, update it
                sql = """
                            UPDATE matches 
                            SET score1 = %s, score2 = %s, status = %s, bo = %s, date = %s, team1 = %s, team2 = %s, tab = %s
                            WHERE leaguepediaId = %s
                        """
                mycursor.execute(sql, (score1, score2, status, bo, date, team1, team2, tab, id))
            else:
                # Match does not exist, insert it
                sql = """
                                    INSERT INTO matches (tournament, team1, team2, score1, score2, bo, date, status, leaguepediaId, tab) 
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """
                mycursor.execute(sql, (tournament, team1, team2, score1, score2, bo, date, status, id, tab))
                saved_matches[id] = status
    mydb.commit()

    date = datetime.now(timezone.utc)
    sql = "SELECT name, competition FROM tournaments;"
    mycursor.execute(sql)
    saved_competitions = {n[0]: n[1] for n in mycursor.fetchall()}
    for competition in competitions:
        try:
            compet_name = competition["League Short"] + " " + (competition["Split"] if competition["Split"] is not None else "") + " " + competition["Year"] if competition["Year"] is not None else f"{datetime.today().year}"
        except:
            print(competition)
            raise Exception("Failed")
        if competition["Name"] not in saved_competitions:
            if competition["End"] is None:
                competition["End"] = datetime.now(timezone.utc) + timedelta(days=100)
            sql = "INSERT INTO tournaments (name, start, end, competition) VALUES (%s, %s, %s, %s)"
            mycursor.execute(sql, (competition["Name"], competition["Start"], competition["End"], compet_name))
        elif saved_competitions[competition["Name"]] is None:
            sql = "UPDATE tournaments SET competition = %s WHERE name = %s"
            mycursor.execute(sql, (compet_name, competition["Name"]))
        else:
            continue
    mydb.commit()

    mycursor.execute("SELECT m.id, m.team1, m.team2, m.tournament, m.score1, m.score2 FROM matches m WHERE status = 'Done'")
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
                    try:
                        s = b[1] + r[1]
                    except:
                        print(b)
                        print(r)
                        print(r_)
                        exit()
                    modos[b[0]][r[0]] = (modos[b[0]][r[0]][0] + s, modos[b[0]][r[0]][1] + 1,
                                         modos[b[0]][r[0]][2] + 1 if s == b[1].bo else modos[b[0]][r[0]][2], modos[b[0]][r[0]][3] + b[1].bo)
    mycursor.execute(f"SELECT modo, tournament FROM scores")
    scores = {(modo, tournament) for modo, tournament in mycursor.fetchall()}
    for m in modos:
        for t in modos[m]:
            if (m, t) in scores:
                sql = """
                            UPDATE scores
                            SET scores.num_bets = %s, score = %s, perfect = %s, rating = %s, accuracy = %s, max_score = %s, perfect_score = %s
                            WHERE modo = %s AND tournament = %s
                """
                mycursor.execute(sql, (modos[m][t][1], modos[m][t][0], modos[m][t][2],
                                       round(modos[m][t][0]/max_points[t],2), round(modos[m][t][0]/modos[m][t][3],2), max_points[t], modos[m][t][3],
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
scheduler.add_job(update_matches, 'interval', minutes=5)
scheduler.start()


@app.get("/health")
async def health():
    return {"status": "HEALTHY"}


#? User routes
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

@app.get("/user")
async def get_user(name:str):
    mydb = get_session()
    mycursor = mydb.cursor()

    sql = """
            SELECT id, name FROM modos WHERE name = %s
        """
    mycursor.execute(sql, (name,))
    modo = mycursor.fetchall()
    if not modo:
        mydb.commit()
        mydb.close()
        return {'status' : "Fail", 'message': "Invalid username"}
    modo = modo[0]
    mydb.commit()
    mydb.close()
    return {'status': "Success", 'name': name, 'id': modo[0]}


#? Action routes
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
        db_modo_aware = db_modo[1].replace(tzinfo=timezone.utc)
    else:
        db_modo_aware = db_modo[1]
    if token != db_modo[0]:
        mydb.commit()
        mydb.close()
        return {'status': 'Incorrect token'}
    """if db_modo_aware < datetime.now(timezone.utc) - timedelta(30):
        mydb.commit()
        mydb.close()
        return {'status': 'Expired token'}"""


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


#? Data routes
@app.get("/competitions/current")
async def current_competitions():
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)
    sql = """SELECT MAX(id) AS id, competition AS name, MIN(start) AS start, MAX(end) AS end 
             FROM tournaments 
             WHERE end > %s
             GROUP BY competition 
             ORDER BY end DESC"""
    mycursor.execute(sql, (week_ago,))
    results = mycursor.fetchall()  # Fetch all results as dictionaries

    mycursor.close()
    mydb.close()

    return JSONResponse(content=jsonable_encoder(results))


@app.get("/competitions/modo")
async def modo_competitions(modo: int):
    one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)

    try:
        sql = """
              SELECT DISTINCT MAX(t.id) AS id, t.competition AS name, MIN(t.start) AS start, MAX(t.end) AS end
              FROM bets b
                       JOIN matches m ON b.matchid = m.id
                       JOIN tournaments t ON m.tournament = t.name
              WHERE b.modo = %s \
                AND t.end > %s
              GROUP BY t.competition
              ORDER BY MAX(t.end) DESC \
              """
        mycursor.execute(sql, (modo, one_year_ago))
        results = mycursor.fetchall()
        return JSONResponse(content=jsonable_encoder(results))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        mycursor.close()
        mydb.close()

@app.get("/matches")
async def matches(competition: int):
    date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)

    # Step 1: Get the competition name from the tournament ID
    mycursor.execute("SELECT competition FROM tournaments WHERE id = %s", (competition,))
    row = mycursor.fetchone()
    if not row or not row["competition"]:
        mycursor.close()
        mydb.close()
        return JSONResponse(content=[], status_code=404)

    competition_name = row["competition"]

    # Step 2: Get matches for all tournaments with the same competition name
    sql = """
        SELECT m.id, m.team1, m.team2, m.score1, m.score2, m.bo, m.date, m.status 
        FROM matches AS m 
        JOIN tournaments AS t ON m.tournament = t.name 
        WHERE m.date >= %s AND t.competition = %s
    """
    mycursor.execute(sql, (date, competition_name))
    results = mycursor.fetchall()

    mycursor.close()
    mydb.close()

    return JSONResponse(content=jsonable_encoder(results))


@app.get("/bets")
async def bets(modo: int, league:str = None, team:str = None):
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)
    sql = f"""SELECT b.id, m.id AS matchId, m.team1, m.team2, b.team1bet, m.score1, b.team2bet, m.score2, m.date FROM bets AS b 
             JOIN matches AS m ON m.id=b.matchid 
             WHERE b.modo = %s{" AND m.tournament = %s" if league is not None else ""}{" AND (m.team1 = %s OR m.team2 = %s)" if team is not None else ""}
             ORDER BY m.date DESC 
             LIMIT 50"""
    if league is None and team is None:
        params = (modo,)
    elif league is None:
        params = (modo, team, team)
    elif team is None:
        params = (modo, league)
    else:
        params = (modo, league, team, team)
    mycursor.execute(sql, params)
    results = mycursor.fetchall()
    mycursor.close()
    mydb.close()

    return JSONResponse(content=jsonable_encoder(results))

@app.get("/ranking")
async def ranking(competition: int):
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)

    try:
        # Step 1: Get the competition name
        mycursor.execute("SELECT competition FROM tournaments WHERE id = %s", (competition,))
        row = mycursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Tournament not found")
        competition_name = row["competition"]

        # Step 2: Fetch raw scores for all tournaments in the same competition
        sql = """
            SELECT m.id AS modo_id, m.name,
                   s.score, s.num_bets, s.max_score, s.perfect_score
            FROM scores AS s
            JOIN modos AS m ON m.id = s.modo
            JOIN tournaments AS t ON s.tournament = t.name
            WHERE t.competition = %s
        """
        mycursor.execute(sql, (competition_name,))
        rows = mycursor.fetchall()

        # Step 3: Aggregate per modo
        modo_stats = {}
        for row in rows:
            modo_id = row["modo_id"]
            if modo_id not in modo_stats:
                modo_stats[modo_id] = {
                    "name": row["name"],
                    "score": 0,
                    "num_bets": 0,
                    "max_score": 0,
                    "perfect_score": 0,
                }
            stats = modo_stats[modo_id]
            stats["score"] += row["score"]
            stats["num_bets"] += row["num_bets"]
            stats["max_score"] += row["max_score"]
            stats["perfect_score"] += row["perfect_score"]

        # Step 4: Compute rating and accuracy
        results = []
        for stats in modo_stats.values():
            score = stats["score"]
            possible = stats["max_score"]
            perfect = stats["perfect_score"]
            rating = score / possible if possible else 0.0
            accuracy = score / perfect if perfect else 0.0
            results.append({
                "name": stats["name"],
                "num_bets": stats["num_bets"],
                "score": score,
                "rating": round(rating, 4),
                "accuracy": round(accuracy, 4),
            })

        # Sort by total score descending
        results.sort(key=lambda x: x["score"], reverse=True)

        return JSONResponse(content=jsonable_encoder(results))

    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"{str(e)}\n\nTraceback:\n{tb}")

    finally:
        mycursor.close()
        mydb.close()




#? Team routes
class LogoResponse(BaseModel):
    url: str
@app.get("/team/logo")
async def logo(team: str):
    url = get_team_logo_url(team)
    if url is None:
        raise HTTPException(status_code=404, detail="Team logo not found")
    return LogoResponse(url=url)


#? Match routes
@app.get("/match/hint")
async def match_hint(id:int):
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT team1, team2, bo, status FROM matches WHERE id = %s"
    mycursor.execute(sql, (id,))
    match_ = mycursor.fetchone()
    mydb.commit()
    mydb.close()
    if match_["status"] != "Waiting":
        return {'status': "Fail", 'message': "Match has already started"}
    exp = bo_expectation(match_["team1"], match_["team2"], match_["bo"])
    return {'status': "Success", 'score': exp[0], 'ratio': exp[1]}
    
@app.get("/match/stats")
async def team_stats(id:int):
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT tournament, team1, team2 FROM matches WHERE id = %s"
    mycursor.execute(sql, (id,))
    m = mycursor.fetchone()
    mydb.close()

    stats1 = get_team_stats(m["team1"], m["tournament"])
    stats2 = get_team_stats(m["team2"], m["tournament"])

    data = {m["team1"]: stats1, m["team2"]: stats2}

    return {'status': "Success", 'data': data}

@app.get("/match/bets")
async def match_results(id:int):
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)
    sql = """SELECT b.id, b.team1bet, b.team2bet, m.name
             FROM bets as b 
             JOIN modos as m ON m.id = b.modo
             WHERE matchid = %s """
    mycursor.execute(sql, (id,))
    bets = mycursor.fetchall()
    mydb.close()
    return bets

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

@app.delete("/admin/competition") #! Outdated, need to compare avery tournament with same "competition" field
async def del_competition(id : int):
    mydb = get_session()
    mycursor = mydb.cursor(dictionary=True)
    sql = "SELECT * FROM tournaments WHERE id = %s"
    mycursor.execute(sql, (id,))
    results = mycursor.fetchall()
    if results:
        sql = "DELETE FROM tournaments WHERE id = %s"
        mycursor.execute(sql, (id,))

        name = results[0]["name"]
        sql = "DELETE FROM matches WHERE tournament = %s"
        mycursor.execute(sql, (name,))

        mydb.commit()
        mydb.close()
        return {"status": "success", "message": f"Tournament {id} deleted"}
    return {"status": "fail", "message": f"Tournament {id} not found"}

@app.delete("/admin/match")
async def del_match(id:int):
    mydb = get_session()
    mycursor = mydb.cursor()
    sql = "DELETE FROM matches WHERE id = %s"
    mycursor.execute(sql, (id,))
    mydb.commit()
    mydb.close()
    return {"status": "success", "message": f"Match {id} deleted"}

#? Schedule route
schedule_cache = {}
@app.get("/schedule/{team}")
async def schedule(team:str):
    team = team.upper() if team.upper() != "IG" else "iG"

    now = datetime.now().replace(tzinfo=ZoneInfo("UTC"))
    if team in schedule_cache and schedule_cache.get(team)[0] > now:
        return schedule_cache[team][1]

    match = next_match(team)

    if match is None:
        return "Aucun match trouvé pour le moment, as-tu bien écrit le tag de l'équipe ?"

    date = match["date"] if type(match) is not list else match[0]["date"]
    if date.tzinfo is None:
        date = date.replace(tzinfo=ZoneInfo("UTC"))

    if type(match) is not list:
        text = verbose_schedule(match, team)
    else:
        text = verbose_schedule_lfl(match, team)

    schedule_cache[team] = (date, text)

    return text