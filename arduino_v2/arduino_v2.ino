#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>
#include <EEPROM.h>

// CE and CSN pins for nRF24L01
#define CE_PIN 7
#define CSN_PIN 8

RF24 radio(CE_PIN, CSN_PIN);

// EEPROM addresses for pipe names, channel, and magic number
#define EEPROM_MAGIC_ADDR 0
#define EEPROM_LISTENING_PIPE_ADDR 1
#define EEPROM_WRITING_PIPE_ADDR 7
#define EEPROM_CHANNEL_ADDR 13

// Magic number to check EEPROM validity
#define EEPROM_MAGIC_NUMBER 0x42

// Buffers to hold the pipe names and channel
char listeningPipe[6] = {0};
char writingPipe[6] = {0};
uint8_t channel;

void setDefaults() {
  // Default pipe names and channel
  const char defaultListeningPipe[] = "2Node";
  const char defaultWritingPipe[] = "1Node";
  uint8_t defaultChannel = 77;

  // Save defaults to EEPROM
  EEPROM.update(EEPROM_MAGIC_ADDR, EEPROM_MAGIC_NUMBER);
  EEPROM.put(EEPROM_LISTENING_PIPE_ADDR, defaultListeningPipe);
  EEPROM.put(EEPROM_WRITING_PIPE_ADDR, defaultWritingPipe);
  EEPROM.update(EEPROM_CHANNEL_ADDR, defaultChannel);

  Serial.println("Defaults set in EEPROM.");
}

bool isEEPROMValid() {
  // Check if the magic number is set
  return EEPROM.read(EEPROM_MAGIC_ADDR) == EEPROM_MAGIC_NUMBER;
}

void loadSettings() {
  if (!isEEPROMValid()) {
    Serial.println("EEPROM is not valid, setting defaults.");
    setDefaults();
  }

  // Load pipe names and channel from EEPROM
  EEPROM.get(EEPROM_LISTENING_PIPE_ADDR, listeningPipe);
  EEPROM.get(EEPROM_WRITING_PIPE_ADDR, writingPipe);
  channel = EEPROM.read(EEPROM_CHANNEL_ADDR);

  // Ensure null termination for strings
  listeningPipe[5] = '\0';
  writingPipe[5] = '\0';
}

void setup() {
  Serial.begin(9600);

  // Load settings from EEPROM
  loadSettings();

  Serial.print("Listening Pipe: ");
  Serial.println(listeningPipe);
  Serial.print("Writing Pipe: ");
  Serial.println(writingPipe);
  Serial.print("Channel: ");
  Serial.println(channel);

  radio.begin();
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_1MBPS);
  radio.setChannel(channel);

  // Convert pipe names to uint64_t
  uint64_t listeningPipeAddr = *(uint64_t*)listeningPipe;
  uint64_t writingPipeAddr = *(uint64_t*)writingPipe;

  radio.openWritingPipe(writingPipeAddr);  // Send to Raspberry Pi
  radio.openReadingPipe(1, listeningPipeAddr);  // Listen to Raspberry Pi

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
