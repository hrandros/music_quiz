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

@file_bp.route("/stream_video/<path:filename>")
def stream_video(filename):
    """Stream video files (MP4, WebM, etc.) with proper content-type."""
    videos_dir = os.path.join(Config.BASE_DIR, "videos")

    # Security: prevent directory traversal
    if ".." in filename or filename.startswith("/"):
        return "Invalid filename", 400

    file_path = os.path.join(videos_dir, filename)
    if not os.path.exists(file_path):
        return "Video not found", 404

    return send_from_directory(videos_dir, filename)