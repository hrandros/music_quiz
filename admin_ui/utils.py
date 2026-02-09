import os
import re
import socket

from config import Config


def get_local_ip():
    ip = "127.0.0.1"
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
    except OSError:
        pass
    return ip


def ensure_videos_dir():
    videos_dir = os.path.join(Config.BASE_DIR, "videos")
    os.makedirs(videos_dir, exist_ok=True)
    return videos_dir


def import_video_file(source_path: str, filename: str) -> str:
    safe_name = os.path.basename(filename)
    videos_dir = ensure_videos_dir()
    destination = os.path.join(videos_dir, safe_name)
    if os.path.abspath(source_path) != os.path.abspath(destination):
        with open(source_path, "rb") as src, open(destination, "wb") as dst:
            dst.write(src.read())
    return safe_name


def guess_artist_title(filename):
    name = os.path.splitext(os.path.basename(filename))[0]
    name = re.sub(r"^\d+[\s._-]+", "", name).strip()
    if " - " in name:
        artist, title = name.split(" - ", 1)
        return artist.strip() or "?", title.strip() or "?"
    clean = name.replace("_", " ").replace("-", " ").strip()
    return "?", clean or "?"
