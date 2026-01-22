from flask import Blueprint, render_template

public_bp = Blueprint("public", __name__)

@public_bp.route("/")
def index():
    return render_template("index.html")

@public_bp.route("/player")
def player():
    return render_template("player.html")
