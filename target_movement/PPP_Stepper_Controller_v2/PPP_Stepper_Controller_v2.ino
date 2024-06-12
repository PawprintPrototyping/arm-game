#include <TimerOne.h>
#include <TimerThree.h>

static int aPulsePin = 7;
static int aDirectionPin = 6;
static int aEnablePin = 5;
static int aLimitTopPin = 18;
static int aLimitBottomPin = 19;
static int bLimitTopPin = 20;
static int bLimitBottomPin = 21;
static int bPulsePin = 4;
static int bDirectionPin = 3;
static int bEnablePin = 2;
static int calPulseDelay = 500; // microseconds.
static long calBufferPulses = 500; // Pulses of buffer to avoid at each end.
static long calSmidgePulses = 32; // Pulses to scootch off of (or in to)- the endstop during initial startup
static long minDualTravelPulses = 0;
static long bufferedDualTravelPulses = 0;

static long pulsesPerMeter = 8000;

long aCalPulses = 0;
long bCalPulses = 0;

bool flail = false;

volatile bool aLimitTopState = HIGH;
volatile bool aLimitBottomState = HIGH;
volatile bool bLimitTopState = HIGH;
volatile bool bLimitBottomState = HIGH;
volatile bool calDone = false;
volatile bool limitOverrun = false;

void fail(String message) {
  Serial.println("Entered fail state: " + message);
  while (1) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(500);
    digitalWrite(LED_BUILTIN, LOW);
    delay(500);
  }
}

// Should be executed when any limit switch interrupt is triggered.
void limitInterruptHandler() {
  aLimitTopState = digitalRead(aLimitTopPin);
  aLimitBottomState = digitalRead(aLimitBottomPin);
  bLimitTopState = digitalRead(bLimitTopPin);
  bLimitBottomState = digitalRead(bLimitBottomPin);
  // If a limit switch it hit after the calibration sequence, something has gone very wrong.
  // We need to stop movement and bail to prevent the steppers from blasting past the end stops.
  if (calDone) {
    if (aLimitTopState || aLimitBottomState || bLimitTopState || bLimitBottomState) {
      Timer1.stop();
      Timer3.stop();
      // We can't call fail() normally here, since we're inside an interrupt.
      limitOverrun = true;
    }
  }
}

// There is absolutely a better way of doing this but I'm lazy and dum.
bool checkALimitTop() {
  return(aLimitTopState);
}

bool checkALimitBottom() {
  return(aLimitBottomState);
}

bool checkBLimitTop() {
  return(bLimitTopState);
}

bool checkBLimitBottom() {
  return(bLimitBottomState);
}

void aPulse(int pulseDelay, bool pulseDirection) {
  digitalWrite(aDirectionPin, pulseDirection);
  digitalWrite(aEnablePin,HIGH);
  digitalWrite(aPulsePin,HIGH);
  delayMicroseconds(pulseDelay);
  digitalWrite(aPulsePin,LOW);
  delayMicroseconds(pulseDelay);
}

void aPulsePos(int pulseDelay) {
  aPulse(pulseDelay, true);
}

void aPulseNeg(int pulseDelay) {
  aPulse(pulseDelay, false);
}

void bPulse(int pulseDelay, bool pulseDirection) {
  digitalWrite(bDirectionPin, pulseDirection);
  digitalWrite(bEnablePin,HIGH);
  digitalWrite(bPulsePin,HIGH);
  delayMicroseconds(pulseDelay);
  digitalWrite(bPulsePin,LOW);
  delayMicroseconds(pulseDelay);
}

void bPulsePos(int pulseDelay) {
  bPulse(pulseDelay, true);
}

void bPulseNeg(int pulseDelay) {
  bPulse(pulseDelay, false);
}


void setup() {
  Serial.begin(9600);
  Serial.println("Henlo! Running startup cal...");
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(aPulsePin, OUTPUT);
  pinMode(aDirectionPin, OUTPUT);
  pinMode(aEnablePin, OUTPUT);
  pinMode(aLimitTopPin, INPUT_PULLUP);
  pinMode(aLimitBottomPin, INPUT_PULLUP);
  pinMode(bPulsePin, OUTPUT);
  pinMode(bDirectionPin, OUTPUT);
  pinMode(bEnablePin, OUTPUT);
  pinMode(bLimitTopPin, INPUT_PULLUP);
  pinMode(bLimitBottomPin, INPUT_PULLUP);

  // Prime the limit switch pin states.
  limitInterruptHandler();

  attachInterrupt(digitalPinToInterrupt(aLimitTopPin), limitInterruptHandler, CHANGE);
  attachInterrupt(digitalPinToInterrupt(aLimitBottomPin), limitInterruptHandler, CHANGE);
  attachInterrupt(digitalPinToInterrupt(bLimitTopPin), limitInterruptHandler, CHANGE);
  attachInterrupt(digitalPinToInterrupt(bLimitBottomPin), limitInterruptHandler, CHANGE);

  Timer1.initialize(1000000);
  Timer3.initialize(1000000);

  int i = 0;
  bool done = false;

  // Move the gantrys away from endstops a smidge before cal.
  if (checkALimitTop() || checkALimitBottom()) {
    Serial.println("Target A started at limit.");
    for (i=0;i<calSmidgePulses;i++) {
      aPulsePos(calPulseDelay);
    }
    if (checkALimitTop() || checkALimitBottom()) { // Still on the switch? Might have gone the wrong direction.
      Serial.println("Target A is still at limit. Trying opposite direction.");
      for (i=0;i<calSmidgePulses;i++) {
        aPulseNeg(calPulseDelay);
      }
      if (checkALimitTop() || checkALimitBottom()) {
        fail("Target A is stuck at a limit. Make sure the switch is wired up using the normally closed contacts.");
      }
    }
  }

  // Move the gantrys away from endstops a smidge before cal.
  if (checkBLimitTop() || checkBLimitBottom()) {
    Serial.println("Target B started at limit.");
    for (i=0;i<calSmidgePulses;i++) {
      bPulsePos(calPulseDelay);
    }
    if (checkBLimitTop() || checkBLimitBottom()) { // Still on the switch? Might have gone the wrong direction.
      Serial.println("Target B is still at limit. Trying opposite direction.");
      for (i=0;i<calSmidgePulses;i++) {
        bPulseNeg(calPulseDelay);
      }
      if (checkBLimitTop() || checkBLimitBottom()) {
        fail("Target B is stuck at a limit. Make sure the switch is wired up using the normally closed contacts.");
      }
    }
  }
  
  //// Check for any limit switch wiring faults.
  //if (checkALimitTop() || checkALimitBottom()) {
  //  fail("Target A is stuck at a limit. Make sure the switch is wired up using the normally closed contacts.");
  //}
  //if (checkBLimitTop() || checkBLimitBottom()) {
  //  fail("Target B is stuck at a limit. Make sure the switch is wired up using the normally closed contacts.");
  //}


  // Move the target to the top limit switch so we know where we are.
  while (done == false) {
    if (checkALimitBottom()) {
      fail("Target A traveled in the wrong direction. Its coils are probably wired in reverse.");
    } else if (checkALimitTop()) {
      done = true;
    } else {
      aPulsePos(calPulseDelay);
    }
  }
  // Move the target to the bottom limit switch and count pulses to determine max travel.
  i = 0;
  done = false;
  while (done == false) {
    if (checkALimitBottom()) {
      done = true;
    } else {
      i++;
      aPulseNeg(calPulseDelay);
    }
  }
  aCalPulses = i;
  Serial.println(aCalPulses);
  if (aCalPulses <= calBufferPulses * 2) {
    fail("Total travel pulses for target A are lower than the buffers.");
  }
  // Back away from the limit switch.
  for (i=0;i<calBufferPulses;i++) {
    aPulsePos(calPulseDelay);
  }
  delay(500); // Hacky way of preventing the limit overrun detection from firing as we're finishing the cal.

  i = 0;
  done = false;
  while (done == false) {
    if (checkBLimitBottom()) {
      fail("Target B traveled in the wrong direction. Its coils are probably wired in reverse.");
    } else if (checkBLimitTop()) {
      done = true;
    } else {
      bPulsePos(calPulseDelay);
    }
  }
  // Move the target to the bottom limit switch and count pulses to determine max travel.
  i = 0;
  done = false;
  while (done == false) {
    if (checkBLimitBottom()) {
      done = true;
    } else {
      i++;
      bPulseNeg(calPulseDelay);
    }
  }
  bCalPulses = i;
  Serial.println(bCalPulses);
  if (bCalPulses <= calBufferPulses * 2) {
    fail("Total travel pulses for target B are lower than the buffers.");
  }
  // Back away from the limit switch.
  for (i=0;i<calBufferPulses;i++) {
    bPulsePos(calPulseDelay);
  }
  delay(500); // Hacky way of preventing the limit overrun detection from firing as we're finishing the cal.
  calDone = true;
  Serial.println("Cal done.");

  minDualTravelPulses = aCalPulses;
  if (minDualTravelPulses > bCalPulses) {
    minDualTravelPulses = bCalPulses;
  }

  bufferedDualTravelPulses = minDualTravelPulses - calBufferPulses * 2;
  
  // temp!
  //for (int i=0; i<500; i++) {
  //  aPulsePos(200);
  //  bPulsePos(200);
  //}
}

void loop() {
  //Serial.println(flail);
  if (limitOverrun) {
    fail("Limit switch hit during normal operation! Bailing to prevent hardware damage.");
  }
  //Serial.println(flail);

  if (Serial.available() > 0) {
    //while (Serial.available() == 0) {}
    String cmdStr = Serial.readStringUntil('\n');
    cmdStr.trim();
    if (cmdStr == "flail") {
      flail = true;
      Serial.println("flail ok");
    } else if (cmdStr == "stop") {
      flail = false;
      Serial.println("stop ok");
    } else {
      Serial.print("Fucko boingo: ");
      Serial.println(cmdStr);
    }
  }

  if ( flail == true ) {
    //for (int i=0; i<aCalPulses; i++) {
    for (int i=0; i<bufferedDualTravelPulses; i++) {
      aPulsePos(100);
      bPulsePos(100);
    }
    delay(50);
    //for (int i=0; i<aCalPulses; i++) {
    for (int i=0; i<bufferedDualTravelPulses; i++) {
      aPulseNeg(100);
      bPulseNeg(100);
    }
    delay(50);
  }

}
