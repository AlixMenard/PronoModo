import mysql.connector
from mysql.connector.abstracts import MySQLConnectionAbstract
from mysql.connector.pooling import PooledMySQLConnection

def get_session() -> PooledMySQLConnection | MySQLConnectionAbstract:
    return mysql.connector.connect(
        host="db-test",
        port=3306,
        user="root",
        password="azbecbaboevav",
        database="pronosmodo"
    )

# Team stats
def get_teams(region:str|None = None):
    mydb = get_session()
    mycursor = mydb.cursor(dictionnary=True)
    sql = "SELECT slug, name, region, power FROM teams"
    if region is not None:
        sql += " WHERE region = %s"
        mycursor.execute(sql, (region,))
    else:
        mycursor.execute(sql)
    teams = mycursor.fetchall()
    return teams

def bo_expectation(team1:str, team2:str, bo:int = 1):
    mydb = get_session()
    mycursor = mydb.cursor()
    sql = "SELECT power FROM teams WHERE slug = %s"
    mycursor.execute(sql, (team1,))
    power1 = mycursor.fetchone()[0]
    mycursor.execute(sql, (team2,))
    power2 = mycursor.fetchone()[0]
    mydb.commit()
    mydb.close()

    elo_diff = power1 - power2
    expected = 1 / (1 + 10 ** (-elo_diff / 400))
    
    match bo:
        case 1:
            return (1, 0) if expected > 0.5 else (0, 1)
        case 3:
            outs = [(2, 0), (2, 1), (1, 2), (0, 2)]
            return outs[min(3, int((1 - expected) * 4))]
        case 5:
            outs = [(3, 0), (3, 1), (3, 2), (2, 3), (1, 3), (0, 3)]
            return outs[min(5, int((1 - expected) * 6))]
    
    return expected

def update_power(team1:str, team2:str, score1:int, score2:int, bo:int=1):
    expected = bo_expectation(team1, team2)
    result = int(score1>score2)
    modifier = {1: 1, 3: 1.5, 5: 2.25}
    
    delta = 32 * (result - expected)**modifier[bo]

    mydb = get_session()
    mycursor = mydb.cursor()
    sql = "SELECT power FROM teams WHERE slug = %s"
    mycursor.execute(sql, (team1,))
    power1 = mycursor.fetchone()[0]
    mycursor.execute(sql, (team2,))
    power2 = mycursor.fetchone()[0]
    
    # Update powers
    power1 += delta
    power2 -= delta
    
    sql = "UPDATE teams SET power = %s WHERE slug = %s"
    mycursor.execute(sql, (power1, team1))
    mycursor.execute(sql, (power2, team2))
    mydb.commit()
    mydb.close()

def get_league_power(region:str):
    if region == "TBD":
        return 800
    mydb = get_session()
    mycursor = mydb.cursor()

    sql = "SELECT AVG(power) FROM teams WHERE region = %s"
    mycursor.execute(sql, (region,))
    power = mycursor.fetchone()
    return power if power is not None else 800

def register_team(name:str, slug:str, competition:str):
    comp_dic = {"LEC":"EMEA", "LPL":"CN", "LCK":"KR", "LFL":"ERL", "":"TBD"}
    for key in comp_dic:
        if key in competition:
            region = comp_dic[key]
            break
    power = get_league_power(region)

    mydb = get_session()
    mycursor = mydb.cursor()
    sql = "INSERT INTO teams (name, slug, region, power) VALUES (%s, %s, %s, %s)"
    mycursor.execute(sql, (name, slug, region, power))
    mydb.commit()
    mydb.close()