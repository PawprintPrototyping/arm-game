#include <Arduino.h>
#include <CircularBuffer.hpp>
#include <TimerOne.h>
#include <StepperState.h>

// NOTE ON FLASHING: The Nano only has one UART, so the serial lines connected to USB are also tied to the MAX485 transceiver.
// There's a 2 second delay in setup() that *should* allow flashing, but you may need to remove the arduino from the socket to flash it.
// This also means that the arduino probably won't respond to serial commands sent via the USB adapter.
// The MAX485 is also driving the pin and it's stronger than the USB adapter.
// This ALSO means that, if you flash the arduino via USB, the flashing data might get blasted across the MAX485.

/*
General weaselbrained theory of operation:
We'll receive a signal from the IR receiver when it's hit by the blaster (or other IR sources).
That signal is (for our purposes) 7 bytes long. Each bit is bitDuration microseconds long.
So, let's just set a timer every bitDuration, call an interrupt, and slap the current state of the receive pin into a 56 bool circular receiveBuffer.
Compare the receiveBuffer with the blasterPattern during every timer tick. If they match, we've been hit.
When hit, we'll set lastHit to the current millis().
The main loop will wait for polls and respond with a hit if lastHit is within iframeDuration of the current millis() at polling.
There'll be a few millisecond window every ~49 days of uptime where we might miss a hit due to milis() rolling over. Preeeety sure that won't be a problem though.

It was easier to use the timer to handle the hit indicator output and let the main loop do serial stuff, so that's what I did.

Regarding the MAX485 transceiver, we need to enable the driver for the duration of any transmissions.
Since we can't easily tell when the serial transmission is finished (AFAICT), we'll just use a set max485DriverEnableDuration and cross our fingers.
*/

const int stepperLimitPin = A2;
const int hitIndicatorPin = 5;
const int enableIndicatorPin = 4;
const int stepperPwmPin = 6;
const int stepperDirPin = 7;
const int max485DriverEnablePin = 2;
const int max485ReceiverEnablePin = 3;
const int idPin0 = 8;
const int idPin1 = 9;
const int idPin2 = 10;
const int idPin3 = MOSI;
const int irDataPin = A0;
const int bitDuration = 500; // microseconds.
const int iframeDuration = 1000; // milliseconds.

/* amount of time assumed for a message to to go out of the serial TX buffer.  See Weasel comment above on line 33. */
const int max485DriverEnableDuration = 20; // milliseconds. Increase if decreasing baudrate.
const bool blasterPattern[56] = {
  0,0,0,0,
  0,0,0,0,
  0,0,0,1,
  0,0,0,1,
  0,1,1,1,
  0,0,0,1,
  0,1,1,1,
  0,1,1,1,
  0,0,0,1,
  0,1,1,1,
  0,0,0,1,
  0,0,0,1,
  1,1,1,1,
  1,1,1,1
};
const int blasterPatternLen = 56;
CircularBuffer<bool, 56> receiveBuffer;
StepperState* stepperState;
volatile unsigned long lastHit = 0;
unsigned int id = 0;
volatile int enabled = 0;
volatile int hit = 0;
volatile bool hitStat = false;
volatile long lastTransmitTimeMillis = -1;

// Compact binary framing (see docs/serial_protocol.md). Coexists with the legacy ASCII
// commands below so boards can be reflashed one at a time: the sync byte can't be
// confused with the first character of any ASCII command (those all start with a
// lowercase letter).
const uint8_t syncByte = 0xAA;
const uint8_t responseFlag = 0x80;
const uint8_t opcodePoll = 1;
const uint8_t opcodeEnable = 2;
const uint8_t opcodeDisable = 3;
const uint8_t opcodeClear = 4;
const uint8_t opcodeHome = 5;
const uint8_t opcodeUp = 6;
const uint8_t opcodeDown = 7;

bool binaryFrameActive = false;
int binaryBytesRead = 0;
uint8_t binaryFrameBuf[2]; // header, crc

String inputString;

String pollCmdStr;
String enableCmdStr;
String disableCmdStr;
String clearCmdStr;
String homeCmdStr;
String hideCmdStr;
String showCmdStr;

void setMax485Timestamp() {
  lastTransmitTimeMillis = millis();
}

void enableMax485Driver() {
  digitalWrite(max485DriverEnablePin, HIGH);
  digitalWrite(max485ReceiverEnablePin, HIGH); // Disable receiver when transmitting.
  setMax485Timestamp();
}

void disableMax485Driver() {
  digitalWrite(max485DriverEnablePin, LOW);
  digitalWrite(max485ReceiverEnablePin, LOW); // We're done transmitting, reenable the receiver.
}

bool checkHit() {
  // Don't try to compare until we have a full buffer to work with.
  if (receiveBuffer.isFull() == false) {
    return false;
  }
  for (int i = 0; i < blasterPatternLen; i++) {
    if (receiveBuffer[i] != blasterPattern[i]) {
      return false;
    }
  }
  // Didn't bail out? Everything matches - we're hit!
  return true;
}

void timerHandler() {
  receiveBuffer.push(digitalRead(irDataPin));
  if (hit == 1 && lastHit + iframeDuration < millis()) {
    digitalWrite(hitIndicatorPin, LOW);
    hit = 0;
  }
  if (checkHit()) {
    lastHit = millis();
    if (enabled == 1 && hit == 0) {
      digitalWrite(hitIndicatorPin, HIGH);
      hit = 1;
      hitStat = true;
      stepperState->setPosition(StepperState::Position::HOME);
    }
  }
}

// Expected usage: "poll <int id>"
void cmdPoll() {
  //String enabledMsg = "off";
  String enabledMsg = "0";
  if (enabled) {
    //enabledMsg = "on";
    enabledMsg = "1";
  }
  //String hitMsg = "unhit"; // Is there a better word for this?...
  String hitMsg = "0";
  if (hitStat) {
    //hitMsg = "hit";
    hitMsg = "1";
  }

  String positionMsg;
  switch (stepperState->getPosition()) {
    case StepperState::HOME:
      positionMsg = "1";
      break;
    case StepperState::UP:
      positionMsg = "2";
      break;
    default:
      positionMsg = "0";
      break;
  }
  //String respStr = String(id) + " poll " + enabledMsg + " " + hitMsg + " " + lastHit + " " + millis(); // mmm yess, very efficiency
  String respStr = String(id) + " poll " + enabledMsg + " " + hitMsg + " " + positionMsg;
  enableMax485Driver();
  Serial.println(respStr);
}

void cmdClear() {
  hitStat = false;
  String respStr = String(id) + " clear ok";
  enableMax485Driver();
  Serial.println(respStr);
}

void cmdEnable() {
  enabled = 1;
  digitalWrite(enableIndicatorPin, HIGH);
  String respStr = String(id) + " enable ok";
  enableMax485Driver();
  Serial.println(respStr);
}

void cmdDisable() {
  enabled = 0;
  digitalWrite(enableIndicatorPin, LOW);
  String respStr = String(id) + " disable ok";
  enableMax485Driver();
  Serial.println(respStr);
}

void cmdHome() {
  stepperState->findHome();
  String respStr = String(id) + " home start";
  enableMax485Driver();
  Serial.println(respStr);
}
void cmdHide() {
  stepperState->setPosition(StepperState::Position::HOME);
  String respStr = String(id) + " down start";
  enableMax485Driver();
  Serial.println(respStr);
}

void cmdShow() {
  stepperState->setPosition(StepperState::Position::UP);
  String respStr = String(id) + " up start";
  enableMax485Driver();
  Serial.println(respStr);
}

// Must match TargetScoringSerial._crc8() in motion/target_scoring_serial.py exactly:
// poly 0x07, init 0x00.
uint8_t crc8(const uint8_t* data, size_t len) {
  uint8_t crc = 0;
  for (size_t i = 0; i < len; i++) {
    crc ^= data[i];
    for (int b = 0; b < 8; b++) {
      crc = (crc & 0x80) ? ((crc << 1) ^ 0x07) : (crc << 1);
    }
  }
  return crc;
}

void sendBinaryResponse(uint8_t opcode, uint8_t status) {
  uint8_t frame[4];
  frame[0] = syncByte;
  frame[1] = responseFlag | ((id & 0x0F) << 3) | (opcode & 0x07);
  frame[2] = status;
  frame[3] = crc8(&frame[1], 2);
  enableMax485Driver();
  Serial.write(frame, 4);
}

// Dispatches a binary command frame addressed to our id. Silently ignores anything
// addressed to another board or with an unrecognized opcode - the host will time out
// and retry rather than get a NAK.
void handleBinaryFrame(uint8_t header) {
  uint8_t reqId = (header >> 3) & 0x0F;
  uint8_t opcode = header & 0x07;
  if (reqId != id) {
    return;
  }

  switch (opcode) {
    case opcodePoll: {
      uint8_t status = 0;
      if (enabled) status |= 0x01;
      if (hitStat) status |= 0x02;
      uint8_t posBits;
      switch (stepperState->getPosition()) {
        case StepperState::HOME: posBits = 1; break;
        case StepperState::UP: posBits = 2; break;
        default: posBits = 0; break;
      }
      status |= (posBits & 0x03) << 2;
      sendBinaryResponse(opcodePoll, status);
      break;
    }
    case opcodeEnable:
      enabled = 1;
      digitalWrite(enableIndicatorPin, HIGH);
      sendBinaryResponse(opcodeEnable, 0x00);
      break;
    case opcodeDisable:
      enabled = 0;
      digitalWrite(enableIndicatorPin, LOW);
      sendBinaryResponse(opcodeDisable, 0x00);
      break;
    case opcodeClear:
      hitStat = false;
      sendBinaryResponse(opcodeClear, 0x00);
      break;
    case opcodeHome:
      stepperState->findHome();
      sendBinaryResponse(opcodeHome, 0x00);
      break;
    case opcodeUp:
      stepperState->setPosition(StepperState::Position::UP);
      sendBinaryResponse(opcodeUp, 0x00);
      break;
    case opcodeDown:
      stepperState->setPosition(StepperState::Position::HOME);
      sendBinaryResponse(opcodeDown, 0x00);
      break;
    default:
      break;
  }
}

void setup() {
  stepperState = new StepperState(stepperPwmPin, stepperDirPin, stepperLimitPin);
  pinMode(irDataPin, INPUT);
  pinMode(stepperPwmPin, OUTPUT);
  pinMode(stepperDirPin, OUTPUT);
  pinMode(hitIndicatorPin, OUTPUT);
  pinMode(enableIndicatorPin, OUTPUT);
  pinMode(max485DriverEnablePin, OUTPUT);
  pinMode(max485ReceiverEnablePin, OUTPUT);
  pinMode(idPin0, INPUT_PULLUP);
  pinMode(idPin1, INPUT_PULLUP);
  pinMode(idPin2, INPUT_PULLUP);
  pinMode(idPin3, INPUT_PULLUP);
  pinMode(stepperLimitPin, INPUT_PULLUP);

  // The MAX485 transceiver can make it impossible to flash the arduino without removing it from the circuit.
  // Let's turn the transceiver off (RE is active low) and wait for two seconds to give us a chance to flash.
  digitalWrite(max485ReceiverEnablePin, HIGH);
  delay(2000);
  // Otherweise, we want the receiver to be on unless we're transmitting.
  digitalWrite(max485ReceiverEnablePin, LOW);

  Serial.begin(14400);
  while (!Serial);

  // The ID selection pins are INPUT_PULLUP, so they're HIGH (00000001) when off and LOW (00000000) when on.
  // This makes it a bit funky to bit-shift, so I'm just XORing with 00000001 to flip it before shifting and ORing.
  id = (digitalRead(idPin0) ^ 1);
  id = id | (digitalRead(idPin1) ^ 1) << 1;
  id = id | (digitalRead(idPin2) ^ 1) << 2;
  id = id | (digitalRead(idPin3) ^ 1) << 3;
  
  // Why not just do `String str = "stuff " + id`?
  // Because that causes the beginning of the string to get munched.
  // I'm sure there's a clear and logical reason why, but fuck if I know what it is.
  pollCmdStr = "poll ";
  pollCmdStr += id;
  //Serial.println(pollCmdStr);
  enableCmdStr = "enable ";
  enableCmdStr += id;
  //Serial.println(enableCmdStr);
  disableCmdStr = "disable ";
  disableCmdStr += id;
  //Serial.println(disableCmdStr);
  clearCmdStr = "clear ";
  clearCmdStr += id;
  //Serial.println(clearCmdStr);
  homeCmdStr = "home ";
  homeCmdStr += id;
  hideCmdStr += "down ";
  hideCmdStr += id;
  showCmdStr += "up ";
  showCmdStr += id;
  
  Timer1.initialize(bitDuration);
  Timer1.attachInterrupt(timerHandler);
  
  //enableMax485Driver();
  //Serial.println(String(id) + " henlo");
  disableMax485Driver(); // set to receive
}

void loop() {
  bool wasMoving = stepperState->isMoving();
  stepperState->move();
  bool isMoving = stepperState->isMoving();
  // Do not allow timer interrupts when we are moving to keep the stepper consistent.
  if (!wasMoving && isMoving) {
    Timer1.detachInterrupt();
  }
  if (wasMoving && !isMoving) {
    Timer1.attachInterrupt(timerHandler);
  }

  // Set transmitter to receive after max485DriverEnableDuration has passed since transmit.
  if (lastTransmitTimeMillis >= 0) {
    if ((millis() - lastTransmitTimeMillis) >= max485DriverEnableDuration) {
      disableMax485Driver();
      lastTransmitTimeMillis = -1;
    } else {
      return;
    }
  }

  if (!Serial.available()) return;
  // Only read one character per loop to not disrupt moving the targets for too long.
  int c = Serial.read();

  if (binaryFrameActive) {
    binaryFrameBuf[binaryBytesRead++] = (uint8_t) c;
    if (binaryBytesRead >= 2) {
      binaryFrameActive = false;
      uint8_t header = binaryFrameBuf[0];
      uint8_t crc = binaryFrameBuf[1];
      if (crc8(&header, 1) == crc) {
        handleBinaryFrame(header);
      }
    }
    return;
  }

  // A sync byte only starts a binary frame at a command boundary - mid-ASCII-command
  // stray bytes are just noise absorbed into inputString like any other bad input.
  if (inputString.length() == 0 && (uint8_t) c == syncByte) {
    binaryFrameActive = true;
    binaryBytesRead = 0;
    return;
  }

  if (c != '\n' && c > 0) {
    inputString += (char) c;
    return;
  }

  inputString.trim();
  if (inputString == pollCmdStr) {
    cmdPoll();
  } else if (inputString == clearCmdStr) {
    cmdClear();
  } else if (inputString == enableCmdStr) {
    cmdEnable();
  } else if (inputString == disableCmdStr) {
    cmdDisable();
  } else if(inputString == homeCmdStr) {
    cmdHome();
  }else if(inputString == hideCmdStr) {
    cmdHide();
  } else if(inputString == showCmdStr) {
    cmdShow();
  }// else {
  //  Serial.print("Fucko boingo: ");
  //  Serial.println(inputString);
  //}
  inputString = "";
}
