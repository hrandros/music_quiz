from musicquiz.models import Quiz

def get_active_quiz():
    return Quiz.query.filter_by(is_active=True).first()