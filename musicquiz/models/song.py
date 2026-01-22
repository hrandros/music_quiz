from extensions import db

class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    type = db.Column(db.String(20), default="standard") 
    filename = db.Column(db.String(300), nullable=True)
    image_file = db.Column(db.String(300), nullable=True)
    artist = db.Column(db.String(100), default="?")
    title = db.Column(db.String(100), default="?")
    extra_data = db.Column(db.String(500), default="") 
    start_time = db.Column(db.Float, default=0.0)
    duration = db.Column(db.Float, default=15.0)
    round_number = db.Column(db.Integer, default=1)