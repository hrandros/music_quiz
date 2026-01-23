from difflib import SequenceMatcher
from extensions import db
import re
import unicodedata
from difflib import SequenceMatcher

def _fold_accents(s):
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))

def _normalize(s):
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"\(.*?\)", "", s)              # ukloni zagrade i sadržaj
    s = re.sub(r"\b(feat|ft)\.?\b", "", s)     # feat./ft.
    s = re.sub(r"[&x∙•]", " ", s)              # spajanja izvođača
    s = re.sub(r"[^a-z0-9\s]", " ", s)        # interpunkcija -> space
    s = re.sub(r"\s+", " ", s)                 # višestruke razmake
    s = _fold_accents(s)                       # dijakritika -> base
    return s.strip()

def _sim(a, b):
    a, b = _normalize(a), _normalize(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()

def _substring_bonus(a, b):
    a, b = _normalize(a), _normalize(b)
    return 0.5 if a and b and (a in b or b in a) else 0.0

def auto_grade_answer(ans, song):
    artist_sim = 0.0
    title_sim = 0.0

    # artist: lagano splitaj moguće kolaboracije
    gold_artists = re.split(r"[,&/]", song.artist or "")
    gold_artists = [x.strip() for x in gold_artists if x.strip()]

    if ans.artist_guess:
        best = 0.0
        for ga in gold_artists or [""]:
            sc = _sim(ans.artist_guess, ga)
            if sc > best:
                best = sc
        artist_sim = best

    if ans.title_guess:
        title_sim = _sim(ans.title_guess, song.title)
        if title_sim < 0.5:
            title_sim = max(title_sim, _substring_bonus(ans.title_guess, song.title))

    ans.artist_points = 1.0 if artist_sim >= 0.82 else (0.5 if artist_sim >= 0.55 else 0.0)
    ans.title_points  = 1.0 if title_sim  >= 0.84 else (0.5 if title_sim  >= 0.58 else 0.0)

