import time
import socketio

SERVER = 'http://localhost:5001'

# create three clients
admin = socketio.Client()
screen = socketio.Client()
player = socketio.Client()

@screen.event
def connect():
    print('[SCREEN] connected')

@screen.on('tv_start_timer')
def on_tv_start(d):
    print('[SCREEN] tv_start_timer', d)

@screen.on('screen_show_answers')
def on_answers(d):
    print('[SCREEN] screen_show_answers', d)

@screen.on('update_leaderboard')
def on_lb(d):
    print('[SCREEN] leaderboard', d)

@player.event
def connect():
    print('[PLAYER] connected')

@player.on('player_unlock_input')
def on_unlock(d):
    print('[PLAYER] unlocked for song', d)
    # submit an answer after a short delay
    time.sleep(1)
    player.emit('player_submit_answer', {
        'player_name': 'TeamA',
        'song_id': d.get('song_id'),
        'artist': 'CorrectArtist',
        'title': 'WrongTitle'
    })
    # second player
    player.emit('player_submit_answer', {
        'player_name': 'TeamB',
        'song_id': d.get('song_id'),
        'artist': 'WrongArtist',
        'title': 'CorrectTitle'
    })

@player.on('player_lock_input')
def on_lock():
    print('[PLAYER] locked')

@admin.event
def connect():
    print('[ADMIN] connected')


def run():
    print('Connecting clients...')
    try:
        screen.connect(SERVER)
        print('screen connected')
    except Exception as e:
        print('screen connect error', e)
    try:
        player.connect(SERVER)
        print('player connected')
    except Exception as e:
        print('player connect error', e)
    try:
        admin.connect(SERVER)
        print('admin connected')
    except Exception as e:
        print('admin connect error', e)

    time.sleep(1)

    # find song id via a quick REST call? Instead, request server for songs isn't available.
    # Hardcode id assuming setup_db printed it; use 1 as common case.
    song_id = None
    try:
        # try to fetch via simple socket request to admin_get_players (dummy) then read db not possible
        pass
    except Exception:
        pass

    # fallback: request admin to play seeded song id 3 (created by setup_db)
    song_id = 3
    print(f'Admin emitting admin_play_song for id={song_id}')
    admin.emit('admin_play_song', {'id': song_id})

    # wait long enough for timer, grading and finalization
    time.sleep(20)

    screen.disconnect()
    player.disconnect()
    admin.disconnect()

if __name__ == '__main__':
    run()
