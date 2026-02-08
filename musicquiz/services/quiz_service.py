from musicquiz.models import Quiz, Answer, Player
from extensions import db

def recompute_scores():
    totals = {}
    for a in Answer.query.all():
        pts = (a.artist_points or 0.0) + (a.title_points or 0.0) + (a.extra_points or 0.0)
        totals[a.player_name] = totals.get(a.player_name, 0.0) + pts
    for p in Player.query.all():
        p.score = totals.get(p.name, 0.0)
    db.session.commit()
    return {p.name: p.score for p in Player.query.all()}

def get_active_quiz():
    return Quiz.query.filter_by(is_active=True).first()