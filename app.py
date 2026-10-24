import pyaudio
from flask import Flask, render_template
from flask_socketio import SocketIO
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wifispeaker_secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

CHUNK = 4096
FORMAT = pyaudio.paInt16
is_streaming = False

# Global audio settings taaki client kisi bhi waqt sync kar sake
current_config = {
    "rate": 44100,
    "channels": 2
}

def find_stereo_mix_device(p):
    device_count = p.get_device_count()
    for index in range(device_count):
        dev_info = p.get_device_info_by_index(index)
        name = dev_info.get('name', '').lower()
        channels = dev_info.get('maxInputChannels', 0)
        
        if channels > 0 and 'stereo mix' in name:
            return index, dev_info
            
    return None, None

def audio_capture_loop():
    global is_streaming, current_config
    p = pyaudio.PyAudio()

    device_index, dev_info = find_stereo_mix_device(p)

    if device_index is None:
        print("\n[ERROR] 'Stereo Mix' nahi mila! Windows Sound Settings check karo.\n")
        p.terminate()
        is_streaming = False
        return

    channels = int(dev_info['maxInputChannels'])
    sample_rate = int(dev_info['defaultSampleRate'])
    
    current_config["rate"] = sample_rate
    current_config["channels"] = channels

    print(f"\n>> LOCKED: {dev_info['name']}")
    print(f">> Rate: {sample_rate}Hz | Channels: {channels}\n")

    try:
        stream = p.open(
            format=FORMAT,
            channels=channels,
            rate=sample_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK
        )
    except Exception as e:
        print(f"[STREAM ERROR]: {e}")
        p.terminate()
        is_streaming = False
        return

    # Broadcast config to all active clients
    socketio.emit('audio_config', current_config)

    while is_streaming:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            socketio.emit('audio_stream', data)
        except Exception:
            break

    stream.stop_stream()
    stream.close()
    p.terminate()
    print(">> Streaming band ho gayi.")

@app.route("/")
def host():
    return render_template("host.html")

@app.route("/client")
def client():
    return render_template("client.html")

@socketio.on('connect')
def handle_connect():
    # Jaise hi naya phone connect ho, use turant settings bhejo
    socketio.emit('audio_config', current_config)

@socketio.on('start_broadcast')
def handle_start():
    global is_streaming
    if not is_streaming:
        is_streaming = True
        threading.Thread(target=audio_capture_loop, daemon=True).start()

@socketio.on('stop_broadcast')
def handle_stop():
    global is_streaming
    is_streaming = False

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
