from app import create_app
from extensions import db
from musicquiz.models.quiz import Quiz
from musicquiz.models.question import Question
from musicquiz.models.song import Song
from musicquiz.models.player import Player

app = create_app()

with app.app_context():
    db.create_all()

    # Create a test quiz if not exists
    q = Quiz.query.filter_by(title='AutoTest Quiz').first()
    if not q:
        q = Quiz(title='AutoTest Quiz', is_active=True)
        db.session.add(q)
        db.session.commit()

    # Create players
    if not Player.query.filter_by(name='TeamA').first():
        db.session.add(Player(name='TeamA', pin='0000'))
    if not Player.query.filter_by(name='TeamB').first():
        db.session.add(Player(name='TeamB', pin='0001'))

    db.session.commit()

    # Create a test question (audio)
    existing = Question.query.filter_by(quiz_id=q.id).first()
    if not existing:
        question = Question(
            quiz_id=q.id,
            type='audio',
            round_number=1,
            position=1,
            duration=8.0
        )
        db.session.add(question)
        db.session.flush()

        song = Song(
            question_id=question.id,
            filename='test.mp3',
            artist='CorrectArtist',
            title='CorrectTitle',
            start_time=0.0
        )
        db.session.add(song)
        db.session.commit()
    else:
        question = existing

    print('DB initialized. Quiz id:', q.id, 'Question id:', question.id)
