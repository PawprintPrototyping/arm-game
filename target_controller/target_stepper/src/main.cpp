#include <Arduino.h>
#include <CircularBuffer.h>
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

const int stepperLimitPin = 8;
const int hitIndicatorPin = 7;
const int enableIndicatorPin = 6;
const int stepperPwmPin = 5;
const int stepperDirPin = 4;
const int max485DriverEnablePin = 2;
const int max485ReceiverEnablePin = 3;
const int idPin0 = 9;
const int idPin1 = 10;
const int idPin2 = 11;
const int idPin3 = 12;
const int irDataPin = A5;
const int bitDuration = 500; // microseconds.
const int iframeDuration = 1000; // milliseconds.
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

String inputString;

String pollCmdStr;
String enableCmdStr;
String disableCmdStr;
String clearCmdStr;
String homeCmdStr;
String hideCmdStr;
String showCmdStr;

void enableMax485Driver() {
  digitalWrite(max485DriverEnablePin, HIGH);
  digitalWrite(max485ReceiverEnablePin, HIGH); // Disable receiver when transmitting.
}

void disableMax485Driver() {
  delay(max485DriverEnableDuration);
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
    }
  }
  //Serial.println(receiveBuffer.last());
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
  disableMax485Driver();
}

void cmdClear() {
  hitStat = false;
  String respStr = String(id) + " clear ok";
  enableMax485Driver();
  Serial.println(respStr);
  disableMax485Driver();
}

void cmdEnable() {
  enabled = 1;
  digitalWrite(enableIndicatorPin, HIGH);
  String respStr = String(id) + " enable ok";
  enableMax485Driver();
  Serial.println(respStr);
  disableMax485Driver();
}

void cmdDisable() {
  enabled = 0;
  digitalWrite(enableIndicatorPin, LOW);
  String respStr = String(id) + " disable ok";
  enableMax485Driver();
  Serial.println(respStr);
  disableMax485Driver();
}

void cmdHome() {
  stepperState->findHome();
  String respStr = String(id) + " home start";
  enableMax485Driver();
  Serial.println(respStr);
  disableMax485Driver();
}
void cmdHide() {
  stepperState->setPosition(StepperState::Position::HOME);
  String respStr = String(id) + " hide start";
  enableMax485Driver();
  Serial.println(respStr);
  disableMax485Driver();
}

void cmdShow() {
  stepperState->setPosition(StepperState::Position::UP);
  String respStr = String(id) + " show start";
  enableMax485Driver();
  Serial.println(respStr);
  disableMax485Driver();
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

  Serial.begin(9600);
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

  //digitalWrite(max485DriverEnablePin, HIGH);
  
  enableMax485Driver();
  Serial.println(String(id) + " henlo");
  disableMax485Driver();
}

void loop() {
  stepperState->move();
  if (!Serial.available()) return;
  int c;
  while ((c = Serial.read()) > 0) {
    if (c != '\n') {
      inputString += (char) c;
      return;
    }
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
