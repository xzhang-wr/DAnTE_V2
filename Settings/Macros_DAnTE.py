#!usr/bin/env python
__author__ 		= "Min Sung Ahn"
__email__ 		= "aminsung@gmail.com"
__copyright__ 	= "Copyright 2019 RoMeLa"
__date__ = "January 1, 1999"

__version__ 	= "1.0.0"
__status__ 		= "Prototype"

"""
Script that holds useful macros that can be used to link a joint name to its joint id, for example.
"""

import numpy as np

# ==================================================
# ==================================================
# CONSTANTS
# ==================================================
# ==================================================
GRAV = 9.81
PI = 3.1415926535897932


# ==================================================
# ==================================================
# ROBOT INFO & KINEMATICS
# ==================================================
# ==================================================
# ------------------------------
# JOINT NAMES AND JOINT NO
# ------------------------------
PALM = 0
THUMB = 1
INDEX = 2
INDEX_M = 3


# ==================================================
# ==================================================
# HARDWARE / SIMULATION SETTINGS
# ==================================================
# ==================================================
# ------------------------------
# MOTOR ID
# ------------------------------
BEAR_THUMB = 1
BEAR_INDEX = 2
BEAR_INDEX_M = 3

# ------------------------------
# BEAR MOTOR CHARACTERISTICS
# ------------------------------
KV = 22  # speed constant Kv*Voltage = Speed
KT = 0.4297  # torque constant Kt*Current = Torque
# ------------------------------
# TORQUE LIMITS
# ------------------------------
TORQUE_MAX = 10.0
MAX_IQ = TORQUE_MAX/KT

# ------------------------------
# JOINT LIMITS [rad]
# TODO
# ------------------------------

# ------------------------------
# MOTOR GAINS
# ------------------------------

# UNIVERSAL
IQID_P = 0.02
IQID_I = 0.02
IQID_D = 0

POS_P = 10
POS_I = 0.01
POS_D = 0

VEL_P = 0.4
VEL_I = 0
VEL_D = 0.0

FOR_P = 1.5
FOR_I = 0.0
FOR_D = 0.15

# THUMB
THUMB_POS_P = 0.005
THUMB_POS_I = 0.0000
THUMB_POS_D = 0.005

THUMB_VEL_P = 0.200
THUMB_VEL_I = 0.01
THUMB_VEL_D = 0.0

THUMB_FOR_P = 0.001
THUMB_FOR_I = 0.0
THUMB_FOR_D = 0.001

# INDEX
INDEX_POS_P = 0.005
INDEX_POS_I = 0.0000
INDEX_POS_D = 0.005

INDEX_VEL_P = 0.200
INDEX_VEL_I = 0.01
INDEX_VEL_D = 0.0

INDEX_FOR_P = 0.001
INDEX_FOR_I = 0.0
INDEX_FOR_D = 0.001

# ==================================================
# ==================================================
# MOTION SETTINGS
# ==================================================
# ==================================================
# ------------------------------
# CALIBRATION
# ------------------------------
VEL_CAL = 1.5
# VEL_RESET = 5
IQ_CAL_DETECT = 0.6
VEL_CAL_DETECT = 0.02

# ------------------------------
# INITIALIZATION
# ------------------------------
VEL_MAX_INIT = 2.5
IQ_MAX_INIT = 1.5
TIMEOUT_INIT = 5

# ==================================================
# ==================================================
# MOTION SETTINGS
# ==================================================
# ==================================================

# ------------------------------
# GRAB
# ------------------------------
MA_window = 15  # Window for simple moving average
SMOOTHING = 0.07  # Smoothing factor for exponential moving average

ACC_COMP_FACTOR = 0.006

SPRING_COMP_START = 0.7
SPRING_COMP_BASE = 0.18
SPRING_COMP_FACTOR = 0.06

TIMEOUT_GRAB = 3

default_approach_speed = 1
default_approach_stiffness = 1
default_detect_current = 0.42
default_final_strength = 1.5
default_max_iq = 0.5

approach_speed_min = 0.5

# TODO: This part needs a lot experiment
# detect_current smaller than detect_current_min will generate too much false detection thus not recommended.
# When using a detect_current smaller than confident_detect_current_min, detection must be confirmed for multiple(3) times
# confident_detect_current_min needs no double check, slow or fast.
detect_current_min = 0.35
confident_detect_current = 0.4
detect_confirm = 2  # Times a detect must be confirmed before triggering


approach_stiffness_min = 0.2
approach_p = 0.15
approach_d = 0  # Acceleration is too noisy, DO NOT USE


def approach_i_func(x):
    # approach i is a function of approach_stiffness
    # When approach stiffness is below 0.5, approach_i = 2.5
    # When approach stiffness is above 4.0, approach_i = 5
    # When in between, approach i is a function
    #        3         2
    # 0.119 x - 1.083 x + 3.417 x + 1.048
    # Above is experiment result.
    if x < 0.5:
        return 2.5
    elif x > 4.0:
        return 5
    else:
        return 0.119*x**3 - 1.083*x**2 + 3.417*x + 1.048


approach_command_max = 3

# ------------------------------
# HOLD
# ------------------------------
HOLD_P_FACTOR = 1.5
HOLD_D_FACTOR = 1
delta_position = 0.1  # Move goal_position command inward by this amount at hold for firm contact
grip_confirm = 4  # Times a grip must be confirmed before triggering

# ------------------------------
# GRIP
# ------------------------------
TIMEOUT_GRIP = 3
grip_p = 8
grip_i = 10
grip_d = 0