from flask import Flask, render_template, request, redirect, url_for
import threading
import time
import socket
import platform
from RF24 import RF24, RF24_PA_MIN, RF24_PA_LOW, RF24_PA_HIGH, RF24_PA_MAX, RF24_1MBPS, RF24_250KBPS, RF24_2MBPS, RF24_CRC_DISABLED, RF24_CRC_8, RF24_CRC_16
import json
import os
import shlex

app = Flask(__name__)


CONFIG_FILE = "radio_config.json"

def save_config(writing_pipe, reading_pipes, allow_remote_control=False):
    """Save the current radio configuration to a JSON file."""
    pa_levels_reverse = {RF24_PA_MIN: "MIN", RF24_PA_LOW: "LOW", RF24_PA_HIGH: "HIGH", RF24_PA_MAX: "MAX"}
    data_rates_reverse = {RF24_1MBPS: "1MBPS", RF24_2MBPS: "2MBPS", RF24_250KBPS: "250KBPS"}

    config = {
        "pa_level": pa_levels_reverse.get(radio.getPALevel(), "LOW"),
        "data_rate": data_rates_reverse.get(radio.getDataRate(), "1MBPS"),
        "channel": radio.getChannel(),
        "retry_delay": current_retry_delay,
        "retry_count": current_retry_count,
        "writing_pipe": writing_pipe,
        "reading_pipes": reading_pipes,
        "allow_remote_control": allow_remote_control  # New toggle setting
    }

    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file)
    print("Configuration saved:", config)


def load_config():
    """Load the saved radio configuration from the JSON file."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as file:
            config = json.load(file)
        print("Configuration loaded:", config)

        reading_pipes = config.get("reading_pipes", ["1Node"] * 6)
        while len(reading_pipes) < 6:
            reading_pipes.append("1Node")

        return {
            "pa_level": config.get("pa_level", "LOW"),
            "data_rate": config.get("data_rate", "1MBPS"),
            "channel": config.get("channel", 76),
            "retry_delay": config.get("retry_delay", 5),
            "retry_count": config.get("retry_count", 15),
            "writing_pipe": config.get("writing_pipe", "2Node"),
            "reading_pipes": reading_pipes,
            "allow_remote_control": config.get("allow_remote_control", False)  # Default OFF
        }
    else:
        print("No configuration file found. Using default settings.")
        return {
            "pa_level": "LOW",
            "data_rate": "1MBPS",
            "channel": 76,
            "retry_delay": 5,
            "retry_count": 15,
            "writing_pipe": "2Node",
            "reading_pipes": ["1Node"] * 6,
            "allow_remote_control": False
        }


# Get local IP address
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


# Detect Raspberry Pi model
def get_pi_model():
    try:
        with open('/proc/device-tree/model') as f:
            model = f.read()
            if 'Raspberry Pi 4' in model:
                return 'Raspberry Pi 4'
            elif 'Raspberry Pi 3' in model:
                return 'Raspberry Pi 3'
    except FileNotFoundError:
        pass
    return platform.machine()


local_ip = get_local_ip()
pi_model = get_pi_model()

# Radio CE and CSN pins
CE_PIN = 22  # GPIO22
CSN_PIN = 1  # CE1

# Addresses for communication
pipes = [b'2Node', b'1Node']

# Initialize RF24 radio
radio = RF24(CE_PIN, CSN_PIN)
messages = []  # Store received messages
radio_status = "Initializing..."

# Global variables for retries
current_retry_delay = 5
current_retry_count = 15
current_crc_length = RF24_CRC_16
current_auto_ack = True
current_dynamic_payloads = True
current_mode = "Active"
multiceiver_enabled = False
pipe_addresses = ["2Node", "1Node"]

def setup_radio():
    global radio_status, current_retry_delay, current_retry_count

    if not radio.begin():
        radio_status = "Disconnected - Radio hardware is not responding"
        print("Error: Radio hardware is not responding.")
        raise RuntimeError("Radio hardware is not responding")
    else:
        time.sleep(1)  # Give the radio time to initialize
        print("Radio initialized successfully.")

    # Load saved configuration
    config = load_config()

    if config:
        # Apply saved configuration
        pa_levels = {"MIN": RF24_PA_MIN, "LOW": RF24_PA_LOW, "HIGH": RF24_PA_HIGH, "MAX": RF24_PA_MAX}
        data_rates = {"1MBPS": RF24_1MBPS, "2MBPS": RF24_2MBPS, "250KBPS": RF24_250KBPS}

        radio.setPALevel(pa_levels.get(config.get("pa_level", "LOW")))
        radio.setDataRate(data_rates.get(config.get("data_rate", "1MBPS")))
        radio.setChannel(config.get("channel", 76))
        radio.setRetries(config.get("retry_delay", 5), config.get("retry_count", 15))

        # Apply saved Writing Pipe
        radio.openWritingPipe(config.get("writing_pipe", "2Node").encode('utf-8'))

        # Apply saved Reading Pipes
        for i, pipe in enumerate(config.get("reading_pipes", ["1Node"] * 6)):
            radio.openReadingPipe(i + 1, pipe.encode('utf-8'))

    else:
        # Default settings if no config is found
        radio.setPALevel(RF24_PA_LOW)
        radio.setDataRate(RF24_1MBPS)
        radio.setChannel(76)
        radio.setRetries(5, 15)
        radio.openWritingPipe(b'2Node')
        for i in range(1, 7):
            radio.openReadingPipe(i, f'{i}Node'.encode('utf-8'))

    radio.enableDynamicPayloads()
    radio.flush_rx()
    radio.flush_tx()
    radio.startListening()
    radio_status = "Connected"


def receive_messages():
    while True:
        if radio.available():
            while radio.available():
                length = radio.getDynamicPayloadSize()
                if length > 0:
                    received_payload = radio.read(length)
                    try:
                        message = received_payload.decode('utf-8').rstrip('\x00')
                        config = load_config()

                        # ✅ Always display the received message
                        messages.append(f"Received: {message}")

                        # ✅ Only process commands if remote control is enabled
                        if config.get("allow_remote_control", False):
                            if message.startswith('/test'):
                                response = message[len('/test'):].strip()
                                send_message(response)
                            elif message.startswith('/c'):
                                channel_param = message[len('/c'):].strip()
                                if channel_param.isdigit():
                                    new_channel = int(channel_param)
                                    if 0 <= new_channel <= 125:
                                        radio.stopListening()
                                        radio.setChannel(new_channel)
                                        radio.startListening()
                                        save_config(config["writing_pipe"], config["reading_pipes"], config["allow_remote_control"])
                                        send_message(f"Channel changed to {new_channel}")
                        else:
                            # ✅ Notify if remote control is disabled but still show the message
                            if message.startswith('/'):
                                messages.append("Remote control is disabled. Command ignored.")
                    except UnicodeDecodeError:
                        messages.append("Received: [Corrupted/Invalid data]")
        time.sleep(0.5)


def send_message(message):
    radio.stopListening()
    radio.flush_tx()
    trimmed_message = message[:32]
    success = radio.write(trimmed_message.encode('utf-8'))

    if success:
        messages.append(f"Sent: {trimmed_message} [Success]")
    else:
        messages.append(f"Sent: {trimmed_message} [Failed]")
    
    radio.startListening()

@app.route('/')
def index():
    return render_template('index.html', messages=messages, status=radio_status, local_ip=local_ip, pi_model=pi_model)

@app.route('/send', methods=['POST'])
def send():
    msg = request.form.get('message')
    if msg:
        send_message(msg)
    return redirect(url_for('index'))

@app.route('/options.html')
def options():
    # Mapping for display
    pa_levels = {RF24_PA_MIN: "MIN", RF24_PA_LOW: "LOW", RF24_PA_HIGH: "HIGH", RF24_PA_MAX: "MAX"}
    data_rates = {RF24_1MBPS: "1MBPS", RF24_2MBPS: "2MBPS", RF24_250KBPS: "250KBPS"}
    
    config = load_config()

    current_settings = {
        'pa_level': config.get('pa_level', "LOW"),
        'data_rate': config.get('data_rate', "1MBPS"),
        'channel': config.get('channel', 76),
        'retry_delay': config.get('retry_delay', 5),
        'retry_count': config.get('retry_count', 15),
        'writing_pipe': config.get('writing_pipe', "2Node"),
        'reading_pipes': config.get('reading_pipes', ["1Node"] * 6),
        'allow_remote_control': config.get('allow_remote_control', False)  # Pass to template
    }

    return render_template('options.html', settings=current_settings)


@app.route('/update_config', methods=['POST'])
def update_config():
    global current_retry_delay, current_retry_count

    try:
        # Get updated settings from the form
        pa_level = request.form.get('pa_level', 'LOW')
        data_rate = request.form.get('data_rate', '1MBPS')
        channel = int(request.form.get('channel', 76))
        retry_delay = int(request.form.get('retry_delay', 5))
        retry_count = int(request.form.get('retry_count', 15))

        # Get Writing Pipe Address
        pipe_0 = request.form.get('pipe_0', '2Node')

        # Get Reading Pipes 1-6 Addresses
        reading_pipes = [request.form.get(f'pipe_{i}', f'{i}Node') for i in range(1, 7)]

        # Get the state of the Allow Remote Control toggle
        allow_remote_control = 'allow_remote_control' in request.form  # Checkbox handling

        # Mapping for Power Amplifier Level and Data Rate
        pa_levels = {"MIN": RF24_PA_MIN, "LOW": RF24_PA_LOW, "HIGH": RF24_PA_HIGH, "MAX": RF24_PA_MAX}
        data_rates = {"1MBPS": RF24_1MBPS, "2MBPS": RF24_2MBPS, "250KBPS": RF24_250KBPS}

        # Apply new configuration to the radio
        radio.setPALevel(pa_levels.get(pa_level, RF24_PA_LOW))
        radio.setDataRate(data_rates.get(data_rate, RF24_1MBPS))
        radio.setChannel(channel)
        radio.setRetries(retry_delay, retry_count)

        radio.openWritingPipe(pipe_0.encode('utf-8'))
        for i, pipe in enumerate(reading_pipes):
            radio.openReadingPipe(i + 1, pipe.encode('utf-8'))

        # Save the updated configuration
        save_config(pipe_0, reading_pipes, allow_remote_control)

        messages.append(f"Settings updated. Remote Control: {'ON' if allow_remote_control else 'OFF'}")

    except Exception as e:
        error_msg = f"Error updating configuration: {str(e)}"
        messages.append(error_msg)
        print(error_msg)

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
