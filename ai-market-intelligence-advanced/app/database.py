from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client["market_db"]

raw_collection = db["raw_data"]
processed_collection = db["processed_data"]
