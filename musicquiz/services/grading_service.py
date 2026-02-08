from difflib import SequenceMatcher
import re
import unicodedata


class _GradeTarget:
    def __init__(self, artist, title, duration, extra=""):
        self.artist = artist
        self.title = title
        self.duration = duration
        self.extra = extra

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
    s = re.sub(r"[^a-z0-9\s]", "", s)        # interpunkcija -> space
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
    """Original text-based grading (no time bonus)."""
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


def calculate_time_bonus(submission_time, total_duration):
    """
    Calculate time-based bonus points.

    Specification: For a 30-second clip, points scale based on submission timing:
    - First 1/5 of time (0-6s): 1.0 multiplier
    - Second 1/5 (6-12s): 0.8 multiplier
    - Third 1/5 (12-18s): 0.6 multiplier
    - Fourth 1/5 (18-24s): 0.4 multiplier
    - Fifth 1/5 (24-30s): 0.2 multiplier

    Args:
        submission_time: Seconds into the question when answer was submitted
        total_duration: Total duration of the question in seconds

    Returns:
        Multiplier (0.0 to 1.0) to apply to base points
    """
    if submission_time < 0 or total_duration <= 0:
        return 1.0  # Default if invalid

    if submission_time >= total_duration:
        return 0.0  # After timer expires = no bonus

    # Calculate which fifth of the duration
    interval = total_duration / 5.0
    intervals_passed = int(submission_time / interval)

    # Clamp to valid range
    intervals_passed = min(intervals_passed, 4)

    multipliers = [1.0, 0.8, 0.6, 0.4, 0.2]
    return multipliers[intervals_passed]


def grade_multiple_choice(ans, correct_choice_index):
    """
    Grade a multiple choice answer.

    Args:
        ans: Answer object
        correct_choice_index: Index of the correct choice (0-based)

    Returns:
        Points (0.0 or 1.0)
    """
    if ans.choice_selected == correct_choice_index:
        return 1.0
    return 0.0
 

def grade_multiple_choice_with_time(ans, correct_choice_index, duration):
    """Grade multiple choice with time bonus."""
    base_points = grade_multiple_choice(ans, correct_choice_index)

    if base_points == 1.0 and ans.submission_time >= 0:
        multiplier = calculate_time_bonus(ans.submission_time, duration)
        return base_points * multiplier

    return base_points


def grade_answer_for_question(ans, question):
    if question.type == "text_multiple" and question.text_multiple:
        correct_idx = int(question.text_multiple.correct_index or 0)
        points = grade_multiple_choice_with_time(ans, correct_idx, float(question.duration or 0))
        ans.artist_points = 0.0
        ans.title_points = points
        return

    if question.type == "text" and question.text:
        answer_text = question.text.answer_text or question.text.question_text
        target = _GradeTarget("", answer_text, float(question.duration or 0))
        auto_grade_answer(ans, target)
        return

    if question.type == "video" and question.video:
        target = _GradeTarget(question.video.artist, question.video.title, float(question.duration or 0))
        auto_grade_answer(ans, target)
        return

    if question.type == "simultaneous" and question.simultaneous:
        targets = _GradeTarget(
            question.simultaneous.artist,
            question.simultaneous.title,
            float(question.duration or 0),
            extra=question.simultaneous.extra_answer,
        )
        auto_grade_answer(ans, targets)
        if targets.extra:
            extra_sim = _sim(ans.extra_guess or "", targets.extra)
            if extra_sim < 0.5:
                extra_sim = max(extra_sim, _substring_bonus(ans.extra_guess or "", targets.extra))
            ans.extra_points = 1.0 if extra_sim >= 0.84 else (0.5 if extra_sim >= 0.58 else 0.0)
        return

    if question.type == "audio" and question.song:
        target = _GradeTarget(question.song.artist, question.song.title, float(question.duration or 0))
        auto_grade_answer(ans, target)

