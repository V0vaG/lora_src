from flask import Flask, render_template, request, redirect, url_for
import threading
import time
from RF24 import RF24, RF24_PA_LOW, RF24_1MBPS

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

def setup_radio():
    global radio_status
    if not radio.begin():
        radio_status = "Disconnected"
        raise RuntimeError("Radio hardware is not responding")
    radio.setPALevel(RF24_PA_LOW)
    radio.setDataRate(RF24_1MBPS)
    radio.setChannel(76)
    radio.enableDynamicPayloads()
    radio.enableAckPayload()
    radio.openWritingPipe(pipes[0])
    radio.openReadingPipe(1, pipes[1])
    radio.startListening()
    radio_status = "Connected"

def receive_messages():
    while True:
        if radio.available():
            received_payload = radio.read(radio.getDynamicPayloadSize())
            message = received_payload.decode('utf-8')
            messages.append(f"Received: {message}")
        time.sleep(1)

def send_message(message):
    radio.stopListening()
    if radio.write(message.encode('utf-8')):
        messages.append(f"Sent: {message}")
    else:
        messages.append("Send failed")
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

def start_receiver():
    threading.Thread(target=receive_messages, daemon=True).start()

if __name__ == '__main__':
    try:
        setup_radio()
    except RuntimeError:
        pass  # The status will show "Disconnected"
    start_receiver()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

