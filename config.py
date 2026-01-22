import os

class Config:
    SECRET_KEY = "rocknroll2026"
    SQLALCHEMY_DATABASE_URI = "sqlite:///kviz.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SONGS_DIR = os.path.join(BASE_DIR, "songs")
    IMAGES_DIR = os.path.join(BASE_DIR, "images")
