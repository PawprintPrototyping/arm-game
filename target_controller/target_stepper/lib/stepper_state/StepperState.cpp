#include <StepperState.h>
#include <ezButton.h>

StepperState::StepperState(int pwmPin, int dirPin, int limitSwitchPin) {
    // https://github.com/laurb9/StepperDriver/tree/master
    stepper = new A4988(MOTOR_STEPS, dirPin, pwmPin, MS1, MS2, MS3);
    // accel and decel values. I have no idea what the numbers mean, but they work!
    // comment out to remove acceleration and deceleration 
    stepper->setSpeedProfile(BasicStepperDriver::Mode::LINEAR_SPEED, 2000, 2000);
    stepper->begin(OPERATIONAL_RPM, MICROSTEPS);
    limitSwitch = new ezButton(limitSwitchPin);
    limitSwitch->setDebounceTime(5); // ms
}

void StepperState::move() {
    limitSwitch->loop();
    if (limitSwitch->isPressed()) {
        stepper->stop();
        // Move up a few steps for HOME point.
        stepper->startRotate(5);
        position = HOME;
    }
    isRotating = (stepper->nextAction() > 0);
};

void StepperState::findHome() {
    stepper->setRPM(HOMING_RPM);
    // move backwards a full rotation
    stepper->startRotate(-360);
};

boolean StepperState::setPosition(Position newPos) {
    if ((position == UNKNOWN) || (position == newPos) || isMoving()) return false;
    stepper->setRPM(OPERATIONAL_RPM);
    switch (newPos)
    {
    case HOME:
        // Add a few extra degrees here to account for missed steps when moving fast.
        // It will probably hit the limit switch every time it homes, but it will simply reposition.
        stepper->startRotate(-95);
        position = HOME;
        break;
    case UP:
        stepper->startRotate(90);
        position = UP;
    default:
        break;
    }
    return true;
};

boolean StepperState::isMoving() {
    return isRotating;
};

StepperState::Position StepperState::getPosition() {
    return position;
};
