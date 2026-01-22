import re

def clean_filename_to_title(filename: str) -> str:
    """
    Pretvara '01-queen_we-will-rock-you.mp3' → 'queen we will rock you'.
    """
    name = re.sub(r'\.mp3$', '', filename.lower())
    name = re.sub(r'^\d+[ _\.-]+', '', name)
    name = name.replace("_", " ").replace("-", " ")
    return name.strip()