import pytest
from app import create_app
from extensions import db
from musicquiz.models import (
    Quiz, Question, Song, Video, TextQuestion, TextMultiple, SimultaneousQuestion, Player, Answer
)
from musicquiz.services.grading_service import (
    _fold_accents, _normalize, _sim, calculate_time_bonus,
    grade_multiple_choice, grade_multiple_choice_with_time,
    auto_grade_answer, grade_answer_for_question
)
from musicquiz.services.question_service import (
    get_question_media, get_question_display,
    get_question_unlock_payload, get_question_answer_key
)
from musicquiz.services.quiz_service import get_active_quiz, recompute_scores
from musicquiz.services.utils import clean_filename_to_title


@pytest.fixture
def app_instance():
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


class TestGradingService:
    def test_fold_accents(self):
        assert _fold_accents("Čevapčići") == "Cevapcici"
        assert _fold_accents("München") == "Munchen"
        assert _fold_accents("") == ""

    def test_normalize(self):
        assert _normalize("Queen (Remastered 2011) feat. David Bowie & x") == "queen david bowie"
        assert _normalize("The Beatles - Hey Jude!") == "the beatles hey jude"
        assert _normalize(None) == ""

    def test_sim_exact_and_fuzzy(self):
        assert _sim("Queen", "Queen") == 1.0
        assert _sim("Queen", "queene") > 0.8
        assert _sim("Beatles", "Rolling Stones") < 0.5

    def test_calculate_time_bonus(self):
        # 30s total duration
        assert calculate_time_bonus(2.0, 30.0) == 1.0   # Interval 1 (0-6s)
        assert calculate_time_bonus(8.0, 30.0) == 0.8   # Interval 2 (6-12s)
        assert calculate_time_bonus(15.0, 30.0) == 0.6  # Interval 3 (12-18s)
        assert calculate_time_bonus(20.0, 30.0) == 0.4  # Interval 4 (18-24s)
        assert calculate_time_bonus(28.0, 30.0) == 0.2  # Interval 5 (24-30s)
        assert calculate_time_bonus(31.0, 30.0) == 0.0  # Expired
        assert calculate_time_bonus(-1.0, 30.0) == 1.0  # Invalid fallback

    def test_multiple_choice_grading(self):
        ans = Answer(choice_selected=2, submission_time=5.0)
        assert grade_multiple_choice(ans, 2) == 1.0
        assert grade_multiple_choice(ans, 1) == 0.0

        # With time bonus (submission_time 5.0 in 30s = 1st interval -> 1.0 multiplier)
        assert grade_multiple_choice_with_time(ans, 2, 30.0) == 1.0

        # Submission time 10.0 in 30s = 2nd interval -> 0.8 multiplier
        ans_late = Answer(choice_selected=2, submission_time=10.0)
        assert grade_multiple_choice_with_time(ans_late, 2, 30.0) == 0.8


class TestQuestionService:
    def test_get_question_display_and_payload(self, app_instance):
        quiz = Quiz(title="Test Quiz", is_active=True)
        db.session.add(quiz)
        db.session.commit()

        # Create Audio Question
        q_audio = Question(quiz_id=quiz.id, round_number=1, position=1, type="audio", duration=30.0)
        db.session.add(q_audio)
        db.session.flush()
        song = Song(question_id=q_audio.id, filename="queen.mp3", artist="Queen", title="Bohemian Rhapsody", start_time=10.0)
        db.session.add(song)

        # Create Text Multiple Question
        q_mult = Question(quiz_id=quiz.id, round_number=1, position=2, type="text_multiple", duration=20.0)
        db.session.add(q_mult)
        db.session.flush()
        mult = TextMultiple(question_id=q_mult.id, question_text="Year of release?", correct_index=1)
        mult.set_choices(["1970", "1975", "1980"])
        db.session.add(mult)

        db.session.commit()

        display_audio = get_question_display(q_audio)
        assert display_audio["artist"] == "Queen"
        assert display_audio["title"] == "Bohemian Rhapsody"

        key_audio = get_question_answer_key(q_audio)
        assert key_audio["artist"] == "Queen"
        assert key_audio["title"] == "Bohemian Rhapsody"

        media_audio = get_question_media(q_audio)
        assert media_audio["url"] == "/stream_song/queen.mp3"
        assert media_audio["start"] == 10.0

        unlock_mult = get_question_unlock_payload(q_mult)
        assert unlock_mult["question_text"] == "Year of release?"
        assert unlock_mult["choices"] == ["1970", "1975", "1980"]


class TestQuizServiceAndUtils:
    def test_clean_filename_to_title(self):
        assert clean_filename_to_title("01-queen_we-will-rock-you.mp3") == "queen we will rock you"

    def test_active_quiz_and_recompute_scores(self, app_instance):
        q1 = Quiz(title="Inactive Quiz", is_active=False)
        q2 = Quiz(title="Active Quiz", is_active=True)
        db.session.add_all([q1, q2])
        db.session.commit()

        active = get_active_quiz()
        assert active.id == q2.id

        player = Player(name="Team Alpha", pin="1234", score=0.0)
        db.session.add(player)
        db.session.flush()

        ans1 = Answer(player_name="Team Alpha", question_id=1, artist_points=1.0, title_points=0.5)
        ans2 = Answer(player_name="Team Alpha", question_id=2, artist_points=1.0, title_points=1.0)
        db.session.add_all([ans1, ans2])
        db.session.commit()

        scores = recompute_scores()
        assert scores["Team Alpha"] == 3.5
        assert Player.query.filter_by(name="Team Alpha").first().score == 3.5
