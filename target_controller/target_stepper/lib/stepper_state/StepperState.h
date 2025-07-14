#ifndef stepperState_h
#define stepperState_h

#include <A4988.h>
#include <ezButton.h>

#define MOTOR_STEPS 200
// RPM to use when operating normally using setPosition
#define OPERATIONAL_RPM 200
// RPM to use when homing, we may not want to SLAM into the limit switch.
#define HOMING_RPM 60
// This needs to match the microstep configuration set on the A4988.
#define MICROSTEPS 16

// Sometimes hardware issues happen. Instead of taking the time to fix it properly, lets just fix it here!
// Flipping this will reverse motors.
#define FLIP_DIR true
// Next, use #if to check the value of FLIP_DIR
#if FLIP_DIR
  #define HOME_START_OFFSET -5
#else
  #define HOME_START_OFFSET 5
#endif
#if FLIP_DIR
  #define DOWN_TO_UP_ROTATION -85
#else
  #define DOWN_TO_UP_ROTATION 85
#endif
// For UP to DOWN rotation, overshoot 5 degrees so it resets via the limit switch in case it missed any steps.
#if FLIP_DIR
  #define UP_TO_DOWN_ROTATION 95
#else
  #define UP_TO_DOWN_ROTATION -95
#endif
#if FLIP_DIR
  #define ROTATE_TOWARD_LIMIT 360
#else
  #define ROTATE_TOWARD_LIMIT -360
#endif

// configure the microstep pins as unconnected
#define MS1 PIN_UNCONNECTED
#define MS2 PIN_UNCONNECTED
#define MS3 PIN_UNCONNECTED

/// Tracks the state of a stepper being driven by an A4988.
/// The positions are either
///   - HOME : Set as the "0 degree" point where the stepper limit switch is
///   - UP : 90 degrees from the start point.
class StepperState {
    public:
        enum Position {
            /// The Stepper has not been homed yet.
            /// findHome() must be called before setPosition() can be called.
            UNKNOWN,
            /// 0 degrees position
            HOME,
            /// 90 degrees from HOME
            UP
        };
        /// @brief Initialize the stepper
        /// @param dirPin The uC's PIN associated with the A4988's DIR PIN, should be a digital OUTPUT PIN
        /// @param pwmPin The uC's PIN associated with the A4988's STEP PIN, should be a digital OUTPUT PIN
        /// @param limitSwitchPin The uC's PIN associated with the limit switch, should be an INPUT_PULLUP PIN attached to a NO switch to ground.
        StepperState(int dirPin, int pwmPin, int limitSwitchPin);

        /// Directs the stepper to step if it is time for a step to occur.
        /// This should be called as frequently as possible in the loop() function.
        /// Note: This should not be a problem, but this method will block for a small amount of time (a few uS) when the step pulse is set and
        ///       unset.
        void move();

        /// @brief Moves the stepper to HOME position.
        /// Must be called when the uC is first powered on and can be optionally called to reset home in cases where steps were potentially missed.  
        void findHome();

        /// @brief  Sets the goal position of the stepper motor.
        /// @param position 
        /// @return true if the new goal position was set or false if the position is UNKNOWN and a position can not be set (call findHome() first),
        ///         there is already a setPosition in progress (check with isMoving()), or the target is already in the position.
        boolean setPosition(Position position);

        /// @brief Is the stepper currently moving towards a set goal position
        /// @return True if the stepper is currently in the process of moving towards a goal position, false if it is not.
        boolean isMoving();

        /// @brief Get the current goal position
        /// @return The current goal position that is set, or UNKNOwN if findHome() has not been called yet.
        Position getPosition();

    private:
        A4988* stepper;
        ezButton* limitSwitch;
        Position position = UNKNOWN;
        boolean isRotating = false;
};

#endif