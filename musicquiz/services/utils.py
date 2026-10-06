import re
import socket

def get_local_ip():
    """Returns outbound local LAN IP address."""
    ip = "127.0.0.1"
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
    except OSError:
        pass
    return ip

def clean_filename_to_title(filename: str) -> str:
    """
    Pretvara '01-queen_we-will-rock-you.mp3' → 'queen we will rock you'.
    """
    name = re.sub(r'\.mp3$', '', filename.lower())
    name = re.sub(r'^\d+[ _\.-]+', '', name)
    name = name.replace("_", " ").replace("-", " ")
    return name.strip()