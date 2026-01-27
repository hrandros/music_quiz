import time
import socketio

SERVER='http://127.0.0.1:5000'
cli=socketio.Client(logger=True, engineio_logger=True)

@cli.event
def connect():
    print('connected')

@cli.event
def connect_error(e):
    print('connect_error', e)

@cli.event
def disconnect():
    print('disconnected')

@cli.on('screen_update_status')
def on_status(d):
    print('screen_update_status', d)

print('connecting')
try:
    cli.connect(SERVER)
    print('connected ok')
    time.sleep(1)
    print('emit admin_play_song id=3')
    cli.emit('admin_play_song', {'id':3})
    time.sleep(10)
    cli.disconnect()
except Exception as e:
    print('error', e)
