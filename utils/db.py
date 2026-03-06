from pymongo import MongoClient
import redis

mongo_client = None
db = None
redis_client = None


def init_db(app):
    global mongo_client, db, redis_client

    mongo_client = MongoClient(app.config["MONGO_URI"])
    db = mongo_client.get_default_database()

    # Create indexes
    db.users.create_index("email", unique=True)
    db.servers.create_index("user_id")
    db.servers.create_index("vm_id", unique=True, sparse=True)
    db.tickets.create_index("user_id")
    db.payments.create_index("user_id")
    db.payments.create_index("invoice_id", unique=True, sparse=True)

    redis_client = redis.from_url(app.config["REDIS_URL"], decode_responses=True)

    return db, redis_client


def get_db():
    return db


def get_redis():
    return redis_client
