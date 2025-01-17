from flask import Flask, render_template, request, redirect, url_for
import threading
import time
import socket
import platform
from RF24 import RF24, RF24_PA_MIN, RF24_PA_LOW, RF24_PA_HIGH, RF24_PA_MAX, RF24_1MBPS, RF24_250KBPS, RF24_2MBPS, RF24_CRC_DISABLED, RF24_CRC_8, RF24_CRC_16
import json
import os

app = Flask(__name__)
CONFIG_FILE = "radio_config.json"

# Radio CE and CSN pins
CE_PIN = 22  # GPIO22
CSN_PIN = 1  # CE1

# Initialize RF24 radio
radio = RF24(CE_PIN, CSN_PIN)
messages = []
radio_status = "Initializing..."

# Global variables
current_retry_delay = 5
current_retry_count = 15

def save_config(writing_pipe, reading_pipes):
    pa_levels_reverse = {RF24_PA_MIN: "MIN", RF24_PA_LOW: "LOW", RF24_PA_HIGH: "HIGH", RF24_PA_MAX: "MAX"}
    data_rates_reverse = {RF24_1MBPS: "1MBPS", RF24_2MBPS: "2MBPS", RF24_250KBPS: "250KBPS"}

    config = {
        "pa_level": pa_levels_reverse.get(radio.getPALevel(), "LOW"),
        "data_rate": data_rates_reverse.get(radio.getDataRate(), "1MBPS"),
        "channel": radio.getChannel(),
        "retry_delay": current_retry_delay,
        "retry_count": current_retry_count,
        "writing_pipe": writing_pipe,
        "reading_pipes": reading_pipes
    }

    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file)
    print("Configuration saved:", config)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as file:
            config = json.load(file)
        print("Configuration loaded:", config)

        reading_pipes = config.get("reading_pipes", ["1Node"] * 6)
        while len(reading_pipes) < 6:
            reading_pipes.append("1Node")

        return config
    else:
        print("No configuration file found. Using default settings.")
        return {
            "pa_level": "LOW",
            "data_rate": "1MBPS",
            "channel": 76,
            "retry_delay": 5,
            "retry_count": 15,
            "writing_pipe": "2Node",
            "reading_pipes": ["1Node"] * 6
        }

def setup_radio():
    global radio_status

    if not radio.begin():
        radio_status = "Disconnected - Radio hardware is not responding"
        raise RuntimeError("Radio hardware is not responding")

    config = load_config()
    pa_levels = {"MIN": RF24_PA_MIN, "LOW": RF24_PA_LOW, "HIGH": RF24_PA_HIGH, "MAX": RF24_PA_MAX}
    data_rates = {"1MBPS": RF24_1MBPS, "2MBPS": RF24_2MBPS, "250KBPS": RF24_250KBPS}

    radio.setPALevel(pa_levels.get(config.get("pa_level", "LOW")))
    radio.setDataRate(data_rates.get(config.get("data_rate", "1MBPS")))
    radio.setChannel(config.get("channel", 76))
    radio.setRetries(config.get("retry_delay", 5), config.get("retry_count", 15))

    # Apply Writing Pipe
    radio.openWritingPipe(config.get("writing_pipe").encode('utf-8'))

    # Apply all 6 Reading Pipes
    for i, pipe in enumerate(config.get("reading_pipes")):
        radio.openReadingPipe(i + 1, pipe.encode('utf-8'))

    radio.enableDynamicPayloads()
    radio.flush_rx()
    radio.flush_tx()
    radio.startListening()
    radio_status = "Connected"
    print("Radio setup complete.")

def receive_messages():
    while True:
        if radio.available():
            while radio.available():
                length = radio.getDynamicPayloadSize()
                if length > 0:
                    received_payload = radio.read(length)
                    try:
                        message = received_payload.decode('utf-8').rstrip('\x00')
                        messages.append(f"Received: {message}")
                    except UnicodeDecodeError:
                        messages.append("Received: [Corrupted/Invalid data]")
        time.sleep(0.5)

def send_message(message):
    radio.stopListening()
    radio.flush_tx()
    success = radio.write(message[:32].encode('utf-8'))
    messages.append(f"Sent: {message} [{'Success' if success else 'Failed'}]")
    radio.startListening()

@app.route('/')
def index():
    return render_template('index.html', messages=messages, status=radio_status)

@app.route('/send', methods=['POST'])
def send():
    msg = request.form.get('message')
    if msg:
        send_message(msg)
    return redirect(url_for('index'))

@app.route('/options.html')
def options():
    config = load_config()
    return render_template('options.html', settings=config)

@app.route('/update_config', methods=['POST'])
def update_config():
    global current_retry_delay, current_retry_count

    pa_level = request.form.get('pa_level')
    data_rate = request.form.get('data_rate')
    channel = int(request.form.get('channel', 76))
    retry_delay = int(request.form.get('retry_delay', 5))
    retry_count = int(request.form.get('retry_count', 15))
    writing_pipe = request.form.get('pipe_0', '2Node')
    reading_pipes = [request.form.get(f'pipe_{i}', f'{i}Node') for i in range(1, 7)]

    pa_levels = {"MIN": RF24_PA_MIN, "LOW": RF24_PA_LOW, "HIGH": RF24_PA_HIGH, "MAX": RF24_PA_MAX}
    data_rates = {"1MBPS": RF24_1MBPS, "2MBPS": RF24_2MBPS, "250KBPS": RF24_250KBPS}

    radio.stopListening()
    radio.setPALevel(pa_levels.get(pa_level, RF24_PA_LOW))
    radio.setDataRate(data_rates.get(data_rate, RF24_1MBPS))
    radio.setChannel(channel)
    radio.setRetries(retry_delay, retry_count)
    radio.openWritingPipe(writing_pipe.encode('utf-8'))

    for i, pipe in enumerate(reading_pipes):
        radio.openReadingPipe(i + 1, pipe.encode('utf-8'))

    save_config(writing_pipe, reading_pipes)
    radio.startListening()

    messages.append(f"Updated Config: PA={pa_level}, DataRate={data_rate}, Channel={channel}, Pipes={writing_pipe}, {reading_pipes}")
    return redirect(url_for('index'))

def start_receiver():
    threading.Thread(target=receive_messages, daemon=True).start()

if __name__ == '__main__':
    try:
        setup_radio()
    except RuntimeError:
        pass
    start_receiver()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
