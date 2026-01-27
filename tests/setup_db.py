from app import create_app
from extensions import db
from musicquiz.models.quiz import Quiz
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

    # Create a test song
    s = Song.query.filter_by(title='Test Song').first()
    if not s:
        s = Song(
            quiz_id=q.id,
            type='standard',
            filename=None,
            artist='CorrectArtist',
            title='CorrectTitle',
            start_time=0.0,
            duration=8.0,
            round_number=1
        )
        db.session.add(s)
        db.session.commit()

    print('DB initialized. Quiz id:', q.id, 'Song id:', s.id)
