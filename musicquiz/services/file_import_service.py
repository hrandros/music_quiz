import os
import shutil
from werkzeug.utils import secure_filename
from config import Config

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