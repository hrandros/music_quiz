import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "rocknroll2026")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///kviz.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Optional engine options for better PostgreSQL behavior under concurrency
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 5))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", 10))
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_size": DB_POOL_SIZE,
        "max_overflow": DB_MAX_OVERFLOW,
    }

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SONGS_DIR = os.path.join(BASE_DIR, "songs")
    IMAGES_DIR = os.path.join(BASE_DIR, "images")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
