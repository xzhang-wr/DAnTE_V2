#!usr/bin/env python
__author__ = "Xiaoguang Zhang"
__email__ = "xzhang@westwoodrobotics.net"
__copyright__ = "Copyright 2020 Westwood Robotics"
__date__ = "Jan 8, 2020"
__version__ = "0.1.0"
__status__ = "Beta"

"""
Register Table
"""


class INSTRUCTION:
    """MPS Instruction"""
    read = 0b01000000
    write = 0b10000000


class REG:
    """MPS Registers"""
    Zero_Low_Byte = 0x00
    Zero_High_Byte = 0x01
    BCT = 0x02
    Sensor_Orientation = 0x03  # BCT direction
    Rotation_Direction = 0x09
    


REG_DIC = {'BTC': REG.BCT,
           'sensor_orientation': REG.Sensor_Orientation,
           'zero_low': REG.Zero_Low_Byte,
           'zero_high': REG.Zero_High_Byte,
           'rotation_direction': REG.Rotation_Direction}
