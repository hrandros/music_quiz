from extensions import db
import datetime

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    pin = db.Column(db.String(4), nullable=False)
    score = db.Column(db.Float, default=0.0)
    last_active = db.Column(db.DateTime, default=datetime.datetime.utcnow)