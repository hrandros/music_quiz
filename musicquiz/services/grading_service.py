from difflib import SequenceMatcher
from extensions import db

def calculate_similarity(user_input: str, correct: str) -> float:
    if not user_input or not correct:
        return 0.0

    u = user_input.strip().lower()
    c = correct.strip().lower()

    if u == c:
        return 1.0

    score = SequenceMatcher(None, u, c).ratio()
    return score

def auto_grade_answer(ans, song):
    """
    Automatsko ocjenjivanje temeljem similarity algoritma.
    Modificira Answer objekt direktno.
    """
    artist_sim = calculate_similarity(ans.artist_guess, song.artist)
    title_sim = calculate_similarity(ans.title_guess, song.title)

    ans.artist_points = 1.0 if artist_sim >= 0.8 else 0.0
    ans.title_points = 1.0 if title_sim >= 0.8 else 0.0

    if ans.artist_points == 0 and artist_sim >= 0.5:
        ans.artist_points = 0.5
    if ans.title_points == 0 and title_sim >= 0.5:
        ans.title_points = 0.5