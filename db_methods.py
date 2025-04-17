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
def get_teams(region = None):
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