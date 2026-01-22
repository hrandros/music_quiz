live_player_status = {}

def get_all_players_data():
    from musicquiz.models import Player

    players = Player.query.all()
    data = []

    for p in players:
        data.append({
            "name": p.name,
            "score": p.score,
            "status": live_player_status.get(p.name, "offline")
        })

    return data
