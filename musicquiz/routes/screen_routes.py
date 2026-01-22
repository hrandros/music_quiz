from flask import Blueprint, render_template
from musicquiz.models import Quiz
from musicquiz.services.quiz_service import get_active_quiz

screen_bp = Blueprint("screen", __name__)

@screen_bp.route("/screen")
def screen():
    q = get_active_quiz()
    return render_template(
        "screen.html",
        quiz={"info": {"title": q.title if q else "", "date": ""}}
    )