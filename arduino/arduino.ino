#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

// CE and CSN pins for nRF24L01
#define CE_PIN 7
#define CSN_PIN 8

RF24 radio(CE_PIN, CSN_PIN);

// Communication addresses (pipes)
const byte pipes[][6] = {"2Node", "1Node"};

void setup() {
  Serial.begin(9600);
  radio.begin();
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_1MBPS);
  radio.setChannel(77);

  radio.openWritingPipe(pipes[1]);  // Send to Raspberry Pi
  radio.openReadingPipe(1, pipes[0]);  // Listen to Raspberry Pi
  
  radio.setAutoAck(true);             // Enable acknowledgment
  radio.enableDynamicPayloads();      // Allow varying payload size
  radio.startListening();             // Always start in listening mode

  Serial.println("Arduino is now always listening.");
}

void loop() {
  if (radio.available()) {
    char receivedMessage[32] = {0};  // Buffer to store the received message

    // Get the size of the incoming message
    uint8_t length = radio.getDynamicPayloadSize();

    // Read the incoming message
    radio.read(&receivedMessage, length);
    receivedMessage[length] = '\0';  // Null-terminate the string

    Serial.print("Received message: ");
    Serial.println(receivedMessage);

    // Prepare the response: "arduino sending back: " + receivedMessage
    const char* prefix = "arduino sending back: ";
    char responseMessage[50] = {0};  // Buffer to hold the full response

    // Combine prefix and received message safely
    snprintf(responseMessage, sizeof(responseMessage), "%s%s", prefix, receivedMessage);

    // Send the response back
    radio.stopListening();  // Stop listening to send
    delay(10);              // Small delay for reliability

    if (radio.write(&responseMessage, strlen(responseMessage))) {
      Serial.print("Sent back: ");
      Serial.println(responseMessage);
    } else {
      Serial.println("Failed to send the response.");
    }

    radio.startListening();  // Resume listening for new messages
  }
}
