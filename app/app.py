from flask import Flask, render_template, request, redirect, url_for
import threading
import time
from RF24 import RF24, RF24_PA_MIN, RF24_PA_LOW, RF24_PA_HIGH, RF24_PA_MAX, RF24_1MBPS, RF24_250KBPS, RF24_2MBPS

app = Flask(__name__)

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

def setup_radio():
    global radio_status, current_retry_delay, current_retry_count
    if not radio.begin():
        radio_status = "Disconnected"
        raise RuntimeError("Radio hardware is not responding")

    radio.setPALevel(RF24_PA_LOW)
    radio.setDataRate(RF24_1MBPS)
    radio.setChannel(76)
    radio.enableDynamicPayloads()
    radio.setRetries(current_retry_delay, current_retry_count)  # Store retries
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
    trimmed_message = message[:32]  # Limit to 32 bytes
    success = radio.write(trimmed_message.encode('utf-8'))

    if success:
        messages.append(f"Sent: {trimmed_message} [Success]")
    else:
        messages.append(f"Sent: {trimmed_message} [Failed]")
    
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
    # Power Amplifier Level Mapping
    pa_levels = {
        RF24_PA_MIN: "MIN",
        RF24_PA_LOW: "LOW",
        RF24_PA_HIGH: "HIGH",
        RF24_PA_MAX: "MAX"
    }

    # Data Rate Mapping
    data_rates = {
        RF24_1MBPS: "1MBPS",
        RF24_2MBPS: "2MBPS",
        RF24_250KBPS: "250KBPS"
    }

    # Prepare current settings
    current_settings = {
        'pa_level': pa_levels.get(radio.getPALevel(), "LOW"),
        'data_rate': data_rates.get(radio.getDataRate(), "1MBPS"),
        'channel': radio.getChannel(),
        'retry_delay': current_retry_delay,
        'retry_count': current_retry_count,
    }

    return render_template('options.html', settings=current_settings)

@app.route('/update_config', methods=['POST'])
def update_config():
    global current_retry_delay, current_retry_count

    pa_level = request.form.get('pa_level')
    data_rate = request.form.get('data_rate')
    channel = int(request.form.get('channel', 76))
    retry_delay = int(request.form.get('retry_delay', 5))
    retry_count = int(request.form.get('retry_count', 15))

    # Set Power Amplifier Level
    pa_levels = {
        "MIN": RF24_PA_MIN,
        "LOW": RF24_PA_LOW,
        "HIGH": RF24_PA_HIGH,
        "MAX": RF24_PA_MAX
    }
    radio.setPALevel(pa_levels.get(pa_level, RF24_PA_LOW))

    # Set Data Rate
    data_rates = {
        "1MBPS": RF24_1MBPS,
        "2MBPS": RF24_2MBPS,
        "250KBPS": RF24_250KBPS
    }
    radio.setDataRate(data_rates.get(data_rate, RF24_1MBPS))

    # Set Channel
    radio.setChannel(channel)

    # Set Retries and update global values
    radio.setRetries(retry_delay, retry_count)
    current_retry_delay = retry_delay
    current_retry_count = retry_count

    messages.append(f"Updated Config: PA={pa_level}, DataRate={data_rate}, Channel={channel}, Retries=({retry_delay},{retry_count})")

    return redirect(url_for('options'))

def start_receiver():
    threading.Thread(target=receive_messages, daemon=True).start()

if __name__ == '__main__':
    try:
        setup_radio()
    except RuntimeError:
        pass
    start_receiver()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
