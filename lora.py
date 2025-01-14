from RF24 import RF24, RF24_PA_LOW, RF24_1MBPS, RF24_2MBPS, RF24_250KBPS
import RPi.GPIO as GPIO
import time

import atexit


def cleanup():
    radio.powerDown()
    GPIO.cleanup()

atexit.register(cleanup)

# Radio CE and CSN pins
CE_PIN = 22  # GPIO22
CSN_PIN = 1  # CE0

# Addresses for communication
pipes = [b'2Node', b'1Node']

# Initialize RF24 radio
radio = RF24(CE_PIN, CSN_PIN)

def setup_radio():
    print("Initializing radio...")
    if not radio.begin():
        print("Radio begin failed")
        raise RuntimeError("Radio hardware is not responding")
    print("Radio begin successful")

    time.sleep(0.5)
    radio.setPALevel(RF24_PA_LOW)
    print("Power level set")

    radio.setDataRate(RF24_1MBPS)
    print("Data rate set")

    radio.setChannel(76)
    print("Channel set")

    radio.enableDynamicPayloads()
    print("Dynamic payloads enabled")

    radio.enableAckPayload()
    print("Ack payload enabled")

    radio.openWritingPipe(pipes[0])
    radio.openReadingPipe(1, pipes[1])
    radio.startListening()
    print("Radio setup complete")

def send_message(message):
    radio.stopListening()
    if radio.write(message.encode('utf-8')):
        print(f"Sent: {message}")
    else:
        print("Send failed")
    radio.startListening()

def receive_message():
    if radio.available():
        received_payload = radio.read(radio.getDynamicPayloadSize())
        print(f"Received: {received_payload.decode('utf-8')}")

def main():
    setup_radio()
    print("Radio initialized. Ready to send/receive messages.")
    try:
        while True:
            choice = input("Send (s) or Wait for message (r): ").lower()
            if choice == 's':
                msg = input("Enter message to send: ")
                send_message(msg)
            elif choice == 'r':
                print("Waiting for message...")
                time.sleep(1)
                receive_message()
            else:
                print("Invalid option.")
    except KeyboardInterrupt:
        print("\nExiting...")
        GPIO.cleanup()

if __name__ == "__main__":
    main()


