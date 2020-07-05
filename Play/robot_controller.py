#!usr/bin/env python3
__author__ = "Xiaoguang Zhang"
__email__ = "xzhang@westwoodrobotics.net"
__copyright__ = "Copyright 2020 Westwood Robotics"
__date__ = "Jan 8, 2020"
__version__ = "0.0.1"
__status__ = "Prototype"

import time
import os
import numpy as nmp
from pathlib import Path
from Play.motor_controller import MotorController
from Settings.Robot import *
import matplotlib.pyplot as plt
from pybear import Manager
import pdb


# -----------------------------
# Functions for basic robot motions
# Enable all before sending commands
# TODO: Create ideal function, putting all motors into damping mode


def read_initials():
    # Read initals file
    filename = 'Settings/initials.txt'
    filepath = os.path.join(str(Path(os.getcwd())), filename)
    # filepath = os.path.join(str(Path(os.getcwd()).parent), filename)
    initials = open(filepath, 'r')
    data = initials.read()
    # String to num
    # Get rid of \n if any
    if data[-1] == '\n':
        data = data[:-1]
    # Convert to list of int and float
    init_data = []
    data = list(data.split("\n"))
    for data_string in data:
        data_list = list(data_string.split(","))
        data_list[0] = data_list[0][1:-1]
        data_list[1] = int(data_list[1])
        data_list[2:] = [float(i) for i in data_list[2:]]
        init_data.append(data_list)
    return init_data


class RobotController(object):

    def __init__(self, robot=None, bypass_DXL=False):
        if robot is None:
            print("Robot set to DAnTE by default")
            self.robot = RobotDataStructure("DAnTE", 8000000, "/dev/ttyUSB0", [INDEX, INDEX_M, THUMB])
        else:
            self.robot = robot
        self.MC = MotorController(self.robot.baudrate, self.robot.port)

        self.gesture = None
        self.mode = None

        self.approach_speed = None
        self.approach_stiffness = None
        self.detect_current = None
        self.final_strength = None
        self.max_iq = None
        self.logging = False
        self.contact_position = [0, 0, 0]
        self.balance_factor = [1, 1, 1]  # Factor for force balance between fingers, update when change gesture

        # When debug, you might want to bypass Dynamixel
        self.bypass_DXL = bypass_DXL

        self.ascii_art = True
        self.welcome_msg()

        # self.start_robot()

    def welcome_msg(self):
        if self.ascii_art:
            print("=========== DAnTE version 2.0.0 -- Last Updated 2020.06.24 ===")
            print("==============================================================")

    # ------------------------
    # INITIALIZATION FUNCTIONS
    # ------------------------
    # Functions for initialization of finger(s)
    # Read initials.txt and check settings
    # Move finger(s) through range of motion according to initials.txt and check for mobility and interference
    def start_robot(self):

        error = 0b000  # 3 bit respectively for INDEX, INDEX_M, THUMB

        # Ping all motors
        for idx, f in enumerate(self.robot.fingerlist):
            if not bool(self.MC.pbm.ping(f.motor_id)):
                print("%s offline." % f.name)
                error = error | (1 << idx)
        if error:
            print("Failed to start robot.")
            return error

        # Read initials, fact check and populate robot object
        init_data = read_initials()  # init_data = [['FINGER', motor_id, homing_offset, travel]...]

        for idx, f in enumerate(self.robot.fingerlist):
            if f.name != init_data[idx][0]:
                print("init_data.name does not match for %s." % f.name)
                error = error | (1 << idx)
            elif f.motor_id != init_data[idx][1]:
                print("init_data.motor_id does not match for %s." % f.name)
                error = error | (1 << idx)
            else:
                f.homing_offset = init_data[idx][2]
                f.travel = init_data[idx][3]

        # Set Current, Velocity and Position PID as well as safe iq_max and velocity_max, and clear Direct Force PID.
        self.MC.init_driver_all()

        if error:
            print("Failed to start robot.")
        else:
            self.robot.booted = True
            print("Welcome aboard, Captain.")

        return error

    def get_robot_enable(self):
        """
        See if all motors are enabled
        :return: bool
        """
        enable = sum(self.MC.get_enable_all()) == 3
        return enable

    # TODO: def set_position_limits() and use in grab

    def initialization_full(self):

        # Full hand initialization.

        # Check if booted
        if self.robot.booted:
            pass
        else:
            print("Run start_robot first.")
            return False

        # TODO: Turn Index fingers to parallel gesture
        usr = input("Turn index fingers to parallel gesture then press enter.")
        self.MC.init_driver_all()

        abnormal = [0, 0, 0]
        enabled = [False, False, False]
        running = [False, False, False]
        # 1000 Failed to travel to home
        # 0100 Failed to close
        # 0010 Boot with position out of range
        # 0001 home_offset abnormal

        # 1. Compare home_offset
        for i in range(3):
            if round(self.robot.fingerlist[i].homing_offset, 2) != round(
                    self.MC.pbm.get_homing_offset(self.robot.finger_ids[i])[0][0], 2):
                abnormal[i] = abnormal[i] | 0b0001
                print("%s home_offset abnormal." % self.robot.fingerlist[i].name)
        # 2. Current position with in range
        present_pos = self.MC.pbm.get_present_position(BEAR_INDEX, BEAR_INDEX_M, BEAR_THUMB)
        for i, pos in enumerate(present_pos):
            if self.robot.fingerlist[i].mirrored:
                if pos[0] < -0.1 or pos[0] > self.robot.fingerlist[i].travel + 0.1:
                    abnormal[i] = abnormal[i] | 0b0010
                    print("%s present_pos out of range." % self.robot.fingerlist[i].name)
                    print(pos[0])
            else:
                if pos[0] > 0.1 or pos[0] < self.robot.fingerlist[i].travel - 0.1:
                    abnormal[i] = abnormal[i] | 0b0010
                    print("%s present_pos out of range." % self.robot.fingerlist[i].name)
                    print(pos[0])
        # # 3. Check for position Limit
        # limit_min = self.MC.pbm.get_limit_position_min(m_id)[0]
        # limit_max = self.MC.pbm.get_limit_position_max(m_id)[0]
        # if limit_min != end_pos or limit_max != 0:
        #     abnormal = True
        #     print("Position limit abnoraml")

        # Ask user if abnoraml
        if sum(abnormal):
            usr = input("Fingers seem to need calibration. Do you want to continue anyway?(y/n)")
            if usr == "n" or usr == "N":
                return False
            else:
                pass

        # Set motor mode and PID
        # Set mode and limits
        self.MC.set_mode_all('position')

        # 4. Move to End -> complete
        running = [True, True, True]
        enabled = self.MC.torque_enable_all(1)
        self.MC.pbm.set_goal_position((BEAR_INDEX, self.robot.fingerlist[0].travel),
                                      (BEAR_INDEX_M, self.robot.fingerlist[1].travel),
                                      (BEAR_THUMB, self.robot.fingerlist[0].travel))
        start_time = time.time()
        while sum(running):
            try:
                status = self.MC.pbm.get_bulk_status((INDEX.motor_id, 'present_position', 'present_velocity'),
                                                     (INDEX_M.motor_id, 'present_position', 'present_velocity'),
                                                     (THUMB.motor_id, 'present_position', 'present_velocity'))
                err = [data[1] for data in status]
                position = [data[0][0] for data in status]
                velocity = [data[0][1] for data in status]
                elapsed_time = time.time() - start_time
                if elapsed_time < TIMEOUT_INIT:
                    for i in range(3):
                        if running[i] and abs(position[i] - self.robot.fingerlist[i].travel) < 0.015:
                            running[i] = False
                            self.MC.damping_mode(self.robot.finger_ids[i])
                            print("%s end travel complete." % self.robot.fingerlist[i].name)
                        else:
                            self.MC.pbm.set_goal_position((self.robot.finger_ids[i], self.robot.fingerlist[i].travel))
                        if err[i] != 128 and err[i] != 144:
                            print("%s error, code:" % self.robot.fingerlist[i].name, bin(err[i]))
                else:
                    print("Timeout while moving to end. Is there something blocking the finger(s)?")
                    print("Abnormal:")
                    for i in range(3):
                        if running[i]:
                            abnormal[i] = abnormal[i] | 0b0100
                            print(self.robot.fingerlist[i].name)
                    self.MC.damping_mode_all()
                    running = [False, False, False]
            except KeyboardInterrupt:
                running = [0]
                print("User interrupted.")
        time.sleep(0.5)

        # 5. Move to Home -> complete
        print("Fingers resetting...")
        # # Set Mode and Limit
        # self.MC.set_mode_all('position')
        running = [True, True, True]
        # Enable torque and go to Home
        self.MC.damping_release_all()
        enabled = self.MC.torque_enable_all(1)
        self.MC.pbm.set_goal_position((THUMB.motor_id, 0),
                                      (INDEX.motor_id, 0),
                                      (INDEX_M.motor_id, 0))
        time.sleep(1)
        # pdb.set_trace()
        start_time = time.time()
        while sum(running):
            try:
                status = self.MC.pbm.get_bulk_status((INDEX.motor_id, 'present_position', 'present_velocity'),
                                                     (INDEX_M.motor_id, 'present_position', 'present_velocity'),
                                                     (THUMB.motor_id, 'present_position', 'present_velocity'))
                err = [data[1] for data in status]
                position = [data[0][0] for data in status]
                velocity = [data[0][1] for data in status]
                elapsed_time = time.time() - start_time
                if elapsed_time < TIMEOUT_INIT:
                    for i in range(3):
                        if abs(position[i]) < 0.015:
                            running[i] = False
                            enabled[i] = self.MC.torque_enable(self.robot.finger_ids[i], 0)
                        else:
                            self.MC.pbm.set_goal_position((self.robot.finger_ids[i], 0))
                        if err[i] != 128:
                            print("%s error, code:" % self.robot.fingerlist[i].name, bin(err[i]))
                else:
                    print("Timeout while resetting. Is there something blocking the finger(s)?")
                    print("Abnormal:")
                    for i in range(3):
                        if running[i]:
                            abnormal[i] = abnormal[i] | 0b1000
                            print(self.robot.fingerlist[i].name)
                            enabled[i] = self.MC.torque_enable(self.robot.finger_ids[i], 0)
                    running = [False, False, False]
            except KeyboardInterrupt:
                running = [0]
                print("User interrupted.")

        # 6. Finger initialization complete
        # Disable and finish
        enabled = self.MC.torque_enable_all(0)
        if sum(abnormal):
            print("Initialization failed.")
            for count, code in enumerate(abnormal):
                if code:
                    print("%s abnormal, error code: %d" % (self.robot.fingerlist[count].name, code))
            return False
        else:
            print("Initialization Complete.")
            for f in self.robot.fingerlist:
                f.initialized = True
            self.robot.initialized = True
            return True

    # ------------------------
    # MOTION FUNCTIONS
    # ------------------------
    # Functions for DAnTE motions
    # Change gesture
    # Control grab and release motion of self.robot

    def change_gesture(self, new_gesture):
        # Change the gesture of DAnTE

        # Check enable first
        if self.get_robot_enable():
            pass
        else:
            print("WARNING: Robot not enabled, enabling now.")
            self.MC.torque_enable_all(1)

        if self.gesture == new_gesture:
            # No need to change
            print('Already in gesture %s.' % new_gesture)
        if new_gesture not in ['Y', 'I', 'P']:
            # Check for invalid input
            print("Invalid input.")  # TODO: Throw an exception

        else:
            # change the new_gesture of self.robot to: tripod(Y), pinch(I) or parallel(P)
            # TODO: read below and complete
            # Start with setting all fingers to position mode with initialization PID
            self.MC.set_mode_all('position')
            # Reset all fingers under present gesture before changing gesture
            # TODO: self.release(present_gesture, 'F')

            # Gesture change operations
            if new_gesture == 'Y':
                # Change to tripod
                print("Changing to Tripod.")
                self.gesture = 'Y'
                # Update balance_factor
                self.balance_factor = [1, 1, 1]
                print("Dynamixel offline.")
            elif new_gesture == 'I':
                # Change to pinch
                print("Changing to Pinch.")
                self.gesture = 'I'
                # Update balance_factor
                self.balance_factor = [1, 1, 1]
                # TODO: set THUMB in position mode with stiff damping and some P and a small I
                print("Dynamixel offline.")
            else:
                # Change to parallel
                print("Changing to Parallel.")
                self.gesture = 'P'
                # Update balance_factor
                self.balance_factor = [1, 1, 2]
                print("Dynamixel offline.")

    def set_approach_stiffness(self):
        # Set the P,D gains for Direct Force mode according to approach_stiffness

        force_p = self.approach_stiffness
        force_d = 0.1 * force_p

        if self.gesture == 'I':
            # Leave THUMB along if in pinch mode
            # Change the force PID of INDEX fingers
            self.MC.pbm.set_p_gain_force((BEAR_INDEX, force_p), (BEAR_INDEX_M, force_p))
            self.MC.pbm.set_d_gain_force((BEAR_INDEX, force_d), (BEAR_INDEX_M, force_d))
        elif self.gesture == 'Y' or self.gesture == 'P':
            # Change the force PID of all fingers
            self.MC.pbm.set_p_gain_force((BEAR_THUMB, force_p), (BEAR_INDEX, force_p), (BEAR_INDEX_M, force_p))
            self.MC.pbm.set_d_gain_force((BEAR_THUMB, force_d), (BEAR_INDEX, force_d), (BEAR_INDEX_M, force_d))
        else:
            print("Invalid input.")  # TODO: Throw exception
            return False
        print("Approach Stiffness set.")
        return True

    def grab(self, gesture, mode, **options):
        # Control grab motion of self.robot
        # Start with a new_gesture, tripod(Y), pinch(I) or parallel(P)
        # Specify a grab mode: (H)old or (G)rip
        # Optional kwargs: (if not specified, go with a default value)
        # - Approach speed (approach_speed)
        # - Approach stiffness (approach_stiffness)
        # - Detection current (detect_current)
        # - Grip force/Hold stiffness (final_strength)
        # - Maximum torque current (max_iq)
        # - Data log function (logging)

        error = 0  # 1 for timeout, 2 for user interruption, 3 for initialization, 9 for Invalid input

        # Check initialization
        if not self.robot.initialized:
            error = 3
            print("Robot not initialized. Exit.")
            return error

        # Check enable and enable system if not.
        if not self.get_robot_enable():
            self.MC.torque_enable_all(1)

        # 0. Prep
        # Check input
        if gesture not in ['Y', 'I', 'P']:
            print("Invalid gesture input.")
            error = 9
            return error
        elif mode not in ['H', 'G']:
            print("Invalid mode input.")
            error = 9
            return error
        else:
            # Sort out all function input data.
            self.mode = mode
            # Options:
            self.approach_speed = max(options.get("approach_speed", default_approach_speed), approach_speed_min)
            self.approach_stiffness = max(options.get("approach_stiffness", default_approach_stiffness),
                                          approach_stiffness_min)
            self.detect_current = max(options.get("detect_current", default_detect_current), detect_current_min)
            self.final_strength = options.get("final_strength", default_final_strength)
            self.max_iq = max(options.get("max_iq", default_max_iq), self.detect_current, default_max_iq)
            self.logging = options.get("logging", False)

        # Calculate approach_i from approach_stiffness
        approach_i = approach_i_func(self.approach_stiffness)
        # Set detect_count if detect_current is below confident value
        if self.detect_current < confident_detect_current:
            detect_count = [detect_confirm, detect_confirm, detect_confirm]
        else:
            detect_count = [0, 0, 0]

        contact_count = 0

        # Calculate goal_approach_speed
        goal_approach_speed = [-self.approach_speed + 2 * self.approach_speed * f.mirrored for f in
                               self.robot.fingerlist]

        # Start with change into gesture
        self.change_gesture(gesture)
        # Set fingers' Direct Force PID according to Stiffness
        self.set_approach_stiffness()

        # Set into Direct Force Mode
        self.MC.set_mode_all('force')

        # Set iq_max
        for f_id in self.robot.finger_ids:
            self.MC.pbm.set_limit_iq_max((f_id, self.max_iq))
        if self.gesture == 'P':
            # Double THUMB iq_limit in Parallel mode
            self.MC.pbm.set_limit_iq_max((THUMB.motor_id, 2 * self.max_iq))
            # Enforce writing
            check = False
            while not check:
                if round(self.MC.pbm.get_limit_iq_max(THUMB.motor_id)[0][0], 4) == round(2 * self.max_iq, 4):
                    check = True

        usr = input("Press enter to grab...")

        # 3. Fingers close tracking approach_speed, switch to final grip/hold upon object detection
        if self.robot.contact:
            print("Please release contact first.")
            return
        else:
            print("Approaching...")
            # Get start_time
            # Python Version 3.7 or above
            # start_time = time.time_ns()/1000000000  # In ns unit
            start_time = time.time()
            present_time = start_time

            # Initialize status variables
            finger_count = 0
            velocity = [0, 0, 0]
            prev_velocity = [0, 0, 0]
            velocity_error = [0, 0, 0]
            velocity_error_int = [0, 0, 0]
            acceleration = [0, 0, 0]
            iq = [0, 0, 0]
            iq_comp = [0, 0, 0]
            goal_iq = [0, 0, 0]
            position = [0, 0, 0]
            approach_command = [0, 0, 0]

            # Status logging
            velocity_log = []
            position_log = []
            time_log = []
            delta_time_log = []
            iq_log = []
            iq_comp_log = []
            acceleration_log = []

            while not (error or self.robot.contact):
                try:
                    previous_time = present_time

                    # Collect status
                    if self.gesture == 'I':
                        status = self.MC.get_present_status_index()
                        finger_count = 2
                    else:
                        status = self.MC.get_present_status_all()
                        finger_count = 3

                    # Get time stamp
                    present_time = time.time()
                    delta_time = present_time - previous_time

                    # Process data
                    # Motor Error
                    motor_err = [i[1] for i in status]
                    # Position
                    position = [i[0][0] for i in status]
                    # iq
                    iq = [SMOOTHING * status[i][0][2] + (1 - SMOOTHING) * iq[i] for i in range(finger_count)]
                    # Velocity
                    prev_velocity = velocity
                    velocity = [SMOOTHING * status[i][0][1] + (1 - SMOOTHING) * velocity[i] for i in
                                range(finger_count)]
                    # Acceleration
                    acceleration = [
                        SMOOTHING * (velocity[i] - prev_velocity[i]) / delta_time + (1 - SMOOTHING) * acceleration[i]
                        for i in range(finger_count)]

                    # Get compensated iq
                    iq_comp = [abs(abs(iq[i] - acceleration[i] * ACC_COMP_FACTOR)
                                   - (abs(position[i]) < SPRING_COMP_START) * 0.2
                                   - (abs(position[i]) > SPRING_COMP_START) * (
                                               0.18 + 0.06 * (abs(position[i]) - SPRING_COMP_START)))
                               for i in range(finger_count)]

                    # Approach motion
                    # Calculate approach_command
                    # RobotController PID generating position command so that finger tracks approach_speed
                    # Build approach commands
                    velocity_error = [goal_approach_speed[i] - velocity[i] for i in range(finger_count)]
                    velocity_error_int = [velocity_error[i] * delta_time + velocity_error_int[i] for i in range(finger_count)]

                    # Determine if contact and Switch to torque mode and maintain iq upon contact
                    for idx in range(finger_count):
                        if not self.robot.fingerlist[idx].contact:
                            if iq_comp[idx] > self.detect_current:
                                if detect_count[idx]:
                                    detect_count[idx] -= 1
                                    # Build command
                                    approach_command[idx] = position[idx] + approach_p * velocity_error[idx] + approach_i * velocity_error_int[idx] - approach_d * acceleration[idx]
                                    self.MC.pbm.set_goal_position((self.robot.finger_ids[idx], approach_command[idx]))

                                else:
                                    self.robot.fingerlist[idx].contact = True
                                    print('Finger contact:', self.robot.fingerlist[idx].name, position[idx])
                                    self.contact_position[idx] = position[idx]
                                    # Calculate iq to maintain
                                    # Get sign and balance factor for the finger
                                    iq_sign_balance = (self.robot.fingerlist[idx].mirrored - (not self.robot.fingerlist[idx].mirrored))*self.balance_factor[idx]
                                    goal_iq[idx] = iq_sign_balance*(self.detect_current + (abs(position[idx]) > SPRING_COMP_START) * (0.18 + 0.06 * (abs(position[idx]) - SPRING_COMP_START)))
                                    # approach_command[idx] = position[idx]
                                    # Send goal_iq
                                    print(goal_iq[idx])
                                    # Set into torque mode
                                    self.MC.set_mode(self.robot.finger_ids[idx], 'torque')
                                    self.MC.pbm.set_goal_iq((self.robot.finger_ids[idx], goal_iq[idx]))
                                    contact_count += 1
                            else:
                                # Build command
                                approach_command[idx] = position[idx] + approach_p * velocity_error[idx] + approach_i * velocity_error_int[idx] - approach_d * acceleration[idx]
                                self.MC.pbm.set_goal_position((self.robot.finger_ids[idx], approach_command[idx]))
                        else:
                            # This finger has contacted
                            # Keep sending iq command
                            self.MC.pbm.set_goal_iq((self.robot.finger_ids[idx], goal_iq[idx]))

                    self.robot.contact = contact_count == finger_count

                    # # Clamp approach_command
                    # approach_command = [max(min(i, approach_command_max), -approach_command_max) for i in approach_command]

                    # Data logging
                    if self.logging:
                        delta_time_log.append(delta_time)
                        time_log.append(present_time - start_time)
                        velocity_log.append(velocity)
                        position_log.append(position)
                        iq_log.append(iq)
                        iq_comp_log.append(iq_comp)
                        acceleration_log.append(acceleration)

                    # Check for timeout
                    if present_time - start_time > TIMEOUT_GRAB:
                        print("Grab motion timeout")
                        self.MC.torque_enable_all(0)
                        error = 1
                except KeyboardInterrupt:
                    print("User interrupted.")
                    running = False
                    error = 2

            # Out of while loop -> error or contact
            if error:
                self.MC.torque_enable_all(0)
                print("Grab error. System disabled.")
            else:
                # Switch to final grip/hold upon object detection
                # pdb.set_trace()
                self.grab_end()

            # Data processing -logging
            if self.logging:
                # Format all data so that it is in this formation:
                # data_log_all = [[INDEX data], [INDEX_M data], [THUMB data]]
                velocity_log_all = []
                position_log_all = []
                iq_log_all = []
                iq_comp_log_all = []
                acceleration_log_all = []

                for i in range(3):
                    velocity_log_all.append([data[i] for data in velocity_log])
                    position_log_all.append([data[i] for data in position_log])
                    iq_log_all.append([data[i] for data in iq_log])
                    iq_comp_log_all.append([data[i] for data in iq_comp_log])
                    acceleration_log_all.append([data[i] for data in acceleration_log])

                # Plot here
                id = 0
                # plt.plot(time_log, iq_comp_log_all[0], 'r-', time_log, iq_comp_log_all[1], 'k-', time_log, iq_comp_log_all[2], 'b-')
                plt.plot(time_log, delta_time_log)
                plt.grid(True)
                plt.show()

        return error

    def grab_end(self):

        error = 0

        # Check mode:
        if self.mode == 'H':
            # Hold mode, change to big D with small P
            # Enforced writing

            # Calculate HOLD_D according to final_strength
            hold_p = HOLD_P_FACTOR * self.final_strength
            hold_d = HOLD_D_FACTOR * self.final_strength
            if self.gesture == 'I':
                # Pinch mode, use only index fingers
                finger_count = 2
            else:
                # Use all three fingers
                finger_count = 3

            # Set D gain first
            for i in range(finger_count):
                self.MC.pbm.set_d_gain_force((self.robot.finger_ids[i], hold_d))
            # Enforce writing
            check = 0
            while check < finger_count:
                for i in range(finger_count):
                    if self.MC.pbm.get_d_gain_force(self.robot.finger_ids[i])[0][0] != hold_d:
                        self.MC.pbm.set_d_gain_force((self.robot.finger_ids[i], hold_d))
                    else:
                        check += 1
            # Then set P gain
            for i in range(finger_count):
                self.MC.pbm.set_p_gain_force((self.robot.finger_ids[i], hold_p))
            # Enforce writing
            check = 0
            while check < finger_count:
                for i in range(finger_count):
                    if self.MC.pbm.get_p_gain_force(self.robot.finger_ids[i])[0][0] != hold_p:
                        self.MC.pbm.set_p_gain_force((self.robot.finger_ids[i], hold_p))
                    else:
                        check += 1
            # Move goal_position forward for a bit more grabbing
            # Calculate goal_position
            goal_position = [
                round(self.contact_position[i] +
                      (self.robot.fingerlist[i].mirrored - (not self.robot.fingerlist[i].mirrored)) * delta_position, 4)
                for i in range(finger_count)]

            # Send command
            for i in range(finger_count):
                self.MC.pbm.set_goal_position((self.robot.finger_ids[i], goal_position[i]))
            # Enforce writing
            check = 0
            while check < finger_count:
                for i in range(finger_count):
                    if round(self.MC.pbm.get_goal_position(self.robot.finger_ids[i])[0][0], 4) != goal_position[i]:
                        self.MC.pbm.set_goal_position((self.robot.finger_ids[i], goal_position[i]))
                    else:
                        check += 1
            # Switch into Direct Force mode
            for i in range(finger_count):
                self.MC.set_mode(self.robot.finger_ids[i], 'force')

        else:
            # Grab mode, grab to final_strength
            detect_count = [grip_confirm, grip_confirm, grip_confirm]
            iq_comp_goal = self.final_strength
            # Collect status
            if self.gesture == 'I':
                # Pinch mode, use only index fingers
                status = self.MC.get_present_status_index()
                finger_count = 2
            else:
                # Use all three fingers
                status = self.MC.get_present_status_all()
                finger_count = 3

            # Get goal_iq
            goal_iq = [
                (self.robot.fingerlist[i].mirrored - (not self.robot.fingerlist[i].mirrored)) *
                (iq_comp_goal + (abs(self.contact_position[i]) < SPRING_COMP_START) * 0.2 +
                 (abs(self.contact_position[i]) > SPRING_COMP_START) * (0.18 + 0.06 * (abs(self.contact_position[i]) - SPRING_COMP_START)))
                for i in range(finger_count)]
            # Clamp goal_iq with max_iq and balance force
            goal_iq = [min(max(goal_iq[i], -self.max_iq), self.max_iq)*self.balance_factor[i] for i in range(finger_count)]
            iq = [0, 0, 0]
            iq_error_int = [0, 0, 0]

            goal_reached = False
            goal_reached_count = 0
            finger_goal_reached = [False, False, False]
            start_time = time.time()
            present_time = time.time()

            first_cyc = True

            # Logging initialize
            time_log = []
            iq_log = []
            position_log = []
            grip_command_log = []
            iq_error_log = []

            # Track goal_iq
            while not (error or goal_reached):
                try:
                    previous_time = present_time

                    # Collect status
                    if self.gesture == 'I':
                        status = self.MC.get_present_status_index()
                    else:
                        status = self.MC.get_present_status_all()

                    # Get time stamp
                    present_time = time.time()
                    delta_time = present_time - previous_time

                    # Process data
                    # Motor Error
                    motor_err = [i[1] for i in status]
                    # iq
                    iq = [SMOOTHING * status[i][0][2] + (1 - SMOOTHING) * iq[i] for i in range(finger_count)]

                    iq_error = [goal_iq[i] - iq[i] for i in range(finger_count)]

                    # Determine if goal_reached
                    for idx in range(finger_count):
                        if finger_goal_reached[idx]:
                            pass
                        else:
                            if abs(iq_error[idx]) < 0.1:
                                if detect_count[idx]:
                                    detect_count[idx] -= 1
                                else:
                                    finger_goal_reached[idx] = True
                                    goal_reached_count += 1
                    goal_reached = goal_reached_count == finger_count

                    # Grip motion
                    # Calculate goal_position
                    # RobotController PID generating position command so that finger tracks goal_iq
                    iq_error_int = [iq_error[i] * delta_time + iq_error_int[i] for i in range(finger_count)]

                    # Build command, stop finger upon contact
                    grip_command = [self.contact_position[i] +
                                    (grip_p * iq_error[i] + grip_i * iq_error_int[i])
                                    for i in range(finger_count)]

                    if finger_count == 2:
                        # Pinch mode, only use INDEX fingers
                        self.MC.pbm.set_goal_position((BEAR_INDEX, grip_command[0]),
                                                      (BEAR_INDEX_M, grip_command[1]))

                    else:
                        # Use all fingers
                        self.MC.pbm.set_goal_position((BEAR_INDEX, grip_command[0]),
                                                      (BEAR_INDEX_M, grip_command[1]),
                                                      (BEAR_THUMB, grip_command[2]))
                    if first_cyc:
                        # Switch into Direct Force mode
                        for i in range(finger_count):
                            self.MC.set_mode(self.robot.finger_ids[i], 'force')
                        first_cyc = False

                    # Data logging
                    time_log.append(present_time-start_time)
                    iq_log.append(iq)
                    grip_command_log.append(grip_command)
                    iq_error_log.append(iq_error)

                    # Check for timeout
                    if present_time - start_time > TIMEOUT_GRIP:
                        print("GRIP motion timeout, final_strength can not be reached")
                        # self.MC.torque_enable_all(0)
                        error = 1
                except KeyboardInterrupt:
                    print("User interrupted.")
                    running = False
                    error = 2

            # Out of while loop, final_strength reached or error

            # Plot functions
            # iq_log_all = []
            # grip_command_log_all = []
            # iq_error_log_all = []
            #
            # for i in range(finger_count):
            #     iq_log_all.append([data[i] for data in iq_log])
            #     iq_error_log_all.append([data[i] for data in iq_error_log])
            #     grip_command_log_all.append([data[i] for data in grip_command_log])

            # # Plot here
            # id = 2
            # # plt.plot(time_log, iq_comp_log_all[0], 'r-', time_log, iq_comp_log_all[1], 'k-', time_log, iq_comp_log_all[2], 'b-')
            # plt.plot(time_log, iq_error_log_all[id], 'r-',
            #          time_log, iq_log_all[id], 'b-')
            # plt.grid(True)
            # plt.show()

        # TODO: Check error

    def release(self, gesture, mode, *hold_stiffness):
        # TODO: Check enable first
        # Release motion of self.robot
        # All fingers run in position mode
        # Three release mode:
        # - change-to-(H)old = damping according to hold_stiffness,
        # - (L)et-go = release a little ,
        # - (F)ully-release = fingers reset
        let_go_amount = 0.15  # Angular displacement to release in let-go mode

        self.MC.init_driver_all()
        self.MC.set_mode_all('position')  # Motor will NOT disable after changing mode

        # Reset finger.contact
        for f in self.robot.fingerlist:
            f.contact = False

        if mode == 'H':
            # Change to hold with damping according to hold_stiffness
            if hold_stiffness:
                # Calculate a D gain from hold_stiffness
                D = 0  # TODO
            else:
                # Use a default D gain
                D = 0
            # Change PID setting
            if gesture == 'I':
                # Pinch mode, do not use Thumb
                # Velocity PID
                self.MC.pbm.set_p_gain_velocity((INDEX.motor_id, VEL_P), (INDEX_M.motor_id, VEL_P))
                self.MC.pbm.set_i_gain_velocity((INDEX.motor_id, VEL_I), (INDEX_M.motor_id, VEL_I))
                self.MC.pbm.set_d_gain_velocity((INDEX.motor_id, VEL_D), (INDEX_M.motor_id, VEL_D))
                # Position PID
                self.MC.pbm.set_p_gain_position((INDEX.motor_id, 0), (INDEX_M.motor_id, 0))
                self.MC.pbm.set_i_gain_position((INDEX.motor_id, 0), (INDEX_M.motor_id, 0))
                self.MC.pbm.set_d_gain_position((INDEX.motor_id, D), (INDEX_M.motor_id, D))
            else:
                # Velocity PID
                self.MC.pbm.set_p_gain_velocity((THUMB.motor_id, VEL_P), (INDEX.motor_id, VEL_P),
                                                (INDEX_M.motor_id, VEL_P))
                self.MC.pbm.set_i_gain_velocity((THUMB.motor_id, VEL_I), (INDEX.motor_id, VEL_I),
                                                (INDEX_M.motor_id, VEL_I))
                self.MC.pbm.set_d_gain_velocity((THUMB.motor_id, VEL_D), (INDEX.motor_id, VEL_D),
                                                (INDEX_M.motor_id, VEL_D))
                # Position PID
                self.MC.pbm.set_p_gain_position((THUMB.motor_id, 0), (INDEX.motor_id, 0), (INDEX_M.motor_id, 0))
                self.MC.pbm.set_i_gain_position((THUMB.motor_id, 0), (INDEX.motor_id, 0), (INDEX_M.motor_id, 0))
                self.MC.pbm.set_d_gain_position((THUMB.motor_id, D), (INDEX.motor_id, D), (INDEX_M.motor_id, D))

        elif mode == 'L':
            # Let-go mode, release a little
            goal_position = [0, 0, 0]
            if gesture == 'I':
                # Pinch mode, do not use Thumb
                # Change PID setting
                self.set_init_PID_index()
                # Get present position
                present_position = self.MC.pbm.get_present_position(INDEX.motor_id, INDEX_M.motor_id)
                if present_position[0][0] < -let_go_amount:
                    goal_position[0] = present_position[0][0] + let_go_amount
                if present_position[1][0] > let_go_amount:
                    goal_position[1] = present_position[1][0] - let_go_amount
                # Set goal position
                self.MC.pbm.set_goal_position((INDEX.motor_id, goal_position[0]), (INDEX_M.motor_id, goal_position[1]))

            else:
                # Change PID setting
                self.set_init_PID_all()
                # Get present position
                present_position = self.MC.pbm.get_present_position(THUMB.motor_id, INDEX.motor_id, INDEX_M.motor_id)
                if present_position[0][0] < -let_go_amount:
                    goal_position[0] = present_position[0][0] + let_go_amount
                if present_position[1][0] < -let_go_amount:
                    goal_position[1] = present_position[1][0] + let_go_amount
                if present_position[2][0] > let_go_amount:
                    goal_position[2] = present_position[2][0] - let_go_amount
                # Set goal position
                self.MC.pbm.set_goal_position((THUMB.motor_id, goal_position[0]),
                                              (INDEX.motor_id, goal_position[1]),
                                              (INDEX_M.motor_id, goal_position[2]))

        elif mode == 'F':
            # Fully reset
            if gesture == 'I':
                # Pinch mode, do not use Thumb
                # Change PID setting
                self.set_init_PID_index()
                # Set goal position
                self.MC.pbm.set_goal_position((INDEX.motor_id, -0.05), (INDEX_M.motor_id, 0.05))
            else:
                # Change PID setting
                self.set_init_PID_all()
                # Set goal position
                self.MC.pbm.set_goal_position((THUMB.motor_id, -0.05),
                                              (INDEX.motor_id, -0.05),
                                              (INDEX_M.motor_id, 0.05))
        else:
            print("Invalid input for mode.")  # TODO: Throw an exception


if __name__ == '__main__':
    rc = RobotController(robot=DAnTE)
    rc.start_robot()
    rc.initialization_full()
    rc.grab('P', 'H', approach_speed=1.8, approach_stiffness=0.35, detect_current=0.3, max_iq=0.25, final_strength=2)