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

def save_config():
    config = {
        "pa_level": radio.getPALevel(),
        "data_rate": radio.getDataRate(),
        "channel": radio.getChannel(),
        "retry_delay": current_retry_delay,
        "retry_count": current_retry_count
    }
    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as file:
            config = json.load(file)
        return config
    return None


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
        print("Radio initialized successfully.")

    # Load saved configuration if exists
    config = load_config()
    if config:
        radio.setPALevel(config.get("pa_level", RF24_PA_LOW))
        radio.setDataRate(config.get("data_rate", RF24_1MBPS))
        radio.setChannel(config.get("channel", 76))
        radio.setRetries(config.get("retry_delay", 5), config.get("retry_count", 15))
    else:
        radio.setPALevel(RF24_PA_LOW)
        radio.setDataRate(RF24_1MBPS)
        radio.setChannel(76)
        radio.setRetries(5, 15)

    radio.enableDynamicPayloads()
    radio.flush_rx()
    radio.flush_tx()
    radio.openWritingPipe(pipes[0])
    radio.openReadingPipe(1, pipes[1])
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
                        messages.append(f"Received: {message}")
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
    pa_levels = {RF24_PA_MIN: "MIN", RF24_PA_LOW: "LOW", RF24_PA_HIGH: "HIGH", RF24_PA_MAX: "MAX"}
    data_rates = {RF24_1MBPS: "1MBPS", RF24_2MBPS: "2MBPS", RF24_250KBPS: "250KBPS"}
    crc_lengths = {RF24_CRC_DISABLED: "Disabled", RF24_CRC_8: "8-bit", RF24_CRC_16: "16-bit"}

    current_settings = {
        'pa_level': pa_levels.get(radio.getPALevel(), "LOW"),
        'data_rate': data_rates.get(radio.getDataRate(), "1MBPS"),
        'channel': radio.getChannel(),
        'retry_delay': current_retry_delay,
        'retry_count': current_retry_count,
        'crc_length': crc_lengths.get(current_crc_length, "16-bit"),
        'auto_ack': current_auto_ack,
        'dynamic_payloads': current_dynamic_payloads,
        'mode': current_mode,
        'multiceiver': multiceiver_enabled,
        'pipe_addresses': pipe_addresses
    }

    return render_template('options.html', settings=current_settings)

@app.route('/update_config', methods=['POST'])
def update_config():
    global current_retry_delay, current_retry_count

    # Get new settings from the form
    pa_level = request.form.get('pa_level')
    data_rate = request.form.get('data_rate')
    channel = int(request.form.get('channel', 76))
    retry_delay = int(request.form.get('retry_delay', 5))
    retry_count = int(request.form.get('retry_count', 15))

    # Power Amplifier and Data Rate Mapping
    pa_levels = {"MIN": RF24_PA_MIN, "LOW": RF24_PA_LOW, "HIGH": RF24_PA_HIGH, "MAX": RF24_PA_MAX}
    data_rates = {"1MBPS": RF24_1MBPS, "2MBPS": RF24_2MBPS, "250KBPS": RF24_250KBPS}

    # Apply new settings
    radio.setPALevel(pa_levels.get(pa_level, RF24_PA_LOW))
    radio.setDataRate(data_rates.get(data_rate, RF24_1MBPS))
    radio.setChannel(channel)
    radio.setRetries(retry_delay, retry_count)

    # Update global variables
    current_retry_delay = retry_delay
    current_retry_count = retry_count

    # Save configuration
    save_config()

    # Restart the radio with new configuration
    radio.stopListening()
    setup_radio()

    messages.append(f"Updated Config: PA={pa_level}, DataRate={data_rate}, Channel={channel}, Retries=({retry_delay},{retry_count})")

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
