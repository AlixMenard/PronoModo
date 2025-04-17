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