from extensions import db

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    round_number = db.Column(db.Integer, default=1)
    song_position = db.Column(db.Integer, default=0)
    type = db.Column(db.String(20), default="standard")
    question = db.Column(db.String(500), default="")
    answer = db.Column(db.String(500), default="")
