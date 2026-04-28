import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="srv1252.hstgr.io",
        user="u691930942_natal_espetos",
        password="M!z!nho252589",
        database="u691930942_natal_espetos"
    )
