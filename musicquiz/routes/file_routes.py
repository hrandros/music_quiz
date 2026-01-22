import os
from flask import Blueprint, send_from_directory
from config import Config

file_bp = Blueprint("file", __name__)

@file_bp.route("/images/<filename>")
def serve_image(filename):
    return send_from_directory(Config.IMAGES_DIR, filename)

@file_bp.route("/stream_song/<path:filename>")
def stream_song(filename):
    return send_from_directory(Config.SONGS_DIR, filename)