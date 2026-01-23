import os
import shutil
from werkzeug.utils import secure_filename
from config import Config
import hashlib


def file_md5(path, block_size=65536):
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(block_size), b""):
            md5.update(chunk)
    return md5.hexdigest()

def scan_mp3_folder(folder_path: str) -> list:
    """
    Rekurzivno skenira folder i vraća listu relativnih putanja .mp3 datoteka.
    """
    mp3_files = []

    for root, dirs, files in os.walk(folder_path):
        for f in files:
            if f.lower().endswith(".mp3"):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, folder_path)
                mp3_files.append(rel.replace("\\", "/"))

    mp3_files.sort()
    return mp3_files

def import_song_file(source_path: str, filename: str) -> str:
    """
    Kopira MP3 u lokalni SONGS_DIR i vraća sigurno ime kopirane datoteke.
    """
    safe_name = secure_filename(filename)
    destination = os.path.join(Config.SONGS_DIR, safe_name)
    shutil.copy2(source_path, destination)
    return safe_name