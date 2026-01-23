from extensions import db

class PlayerQuiz(db.Model):
    __tablename__ = "player_quiz"
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.id"), nullable=False)
    player_name = db.Column(db.String(100), nullable=False)
    pin = db.Column(db.String(4), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("quiz_id", "player_name", name="uq_quiz_player"),
        db.Index("ix_player_quiz_quiz", "quiz_id"),
    )
