import time
import socketio

SERVER = 'http://127.0.0.1:5000'
CONNECT_TIMEOUT = 5

# create three clients
admin = socketio.Client(logger=True, engineio_logger=True)
screen = socketio.Client(logger=True, engineio_logger=True)
player = socketio.Client(logger=True, engineio_logger=True)

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
    print('[PLAYER] unlocked for question', d)
    # submit an answer after a short delay
    time.sleep(1)
    player.emit('player_submit_answer', {
        'player_name': 'TeamA',
        'question_id': d.get('question_id'),
        'artist': 'CorrectArtist',
        'title': 'WrongTitle'
    })
    # second player
    player.emit('player_submit_answer', {
        'player_name': 'TeamB',
        'question_id': d.get('question_id'),
        'artist': 'WrongArtist',
        'title': 'CorrectTitle'
    })

@player.on('player_lock_input')
def on_lock():
    print('[PLAYER] locked')

@admin.event
def connect():
    print('[ADMIN] connected')


@admin.event
def connect_error(data):
    print('[ADMIN] connect_error', data)


@screen.event
def connect_error(data):
    print('[SCREEN] connect_error', data)


@player.event
def connect_error(data):
    print('[PLAYER] connect_error', data)


def connect_client(name, client):
    try:
        client.connect(SERVER, wait=True, wait_timeout=CONNECT_TIMEOUT)
        print(f'{name} connected')
    except Exception as e:
        print(f'{name} connect error', e)


def run():
    print('Connecting clients...')
    connect_client('screen', screen)
    connect_client('player', player)
    connect_client('admin', admin)

    time.sleep(1)

    # find question id via a quick REST call? Instead, request server for questions isn't available.
    # Hardcode id assuming setup_db printed it; use 1 as common case.
    question_id = None
    try:
        # try to fetch via simple socket request to admin_get_players (dummy) then read db not possible
        pass
    except Exception:
        pass

    # fallback: request admin to play seeded question id 3 (created by setup_db)
    question_id = 3
    print(f'Admin emitting admin_play_song for id={question_id}')
    if admin.connected:
        admin.emit('admin_play_song', {'id': question_id})
    else:
        print('Admin client not connected. Skipping admin_play_song emit.')

    # wait long enough for timer, grading and finalization
    time.sleep(20)

    screen.disconnect()
    player.disconnect()
    admin.disconnect()

if __name__ == '__main__':
    run()
