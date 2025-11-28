import fdb
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PATH = os.getenv("DB_PATH") 
DB_PORT = os.getenv("DB_PORT")

def get_connection():
    return fdb.connect(
        host=DB_HOST,
        database=DB_PATH,
        user=DB_USER,
        password=DB_PASS,
        port=int(DB_PORT),
        charset="WIN1252"
    )
