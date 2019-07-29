import re
import struct

import numpy as np

from .portrequest import generate_port_message


class PortCommand:
    def __init__(
        self,
        module,
        name,
        receivetype=None,
        sendtype=None,
        receivefunction=None,
        sendfunction=None,
        arduino_function=None,
    ):

        self.module = module

        self.sendlength = np.array([sendtype]).itemsize
        self.receivelength = np.array([receivetype]).itemsize

        self.sendtype = sendtype
        self.receivetype = receivetype

        if sendfunction is None:
            sendfunction = self.defaultsendfunction

        self.sendfunction = sendfunction
        self.receivefunction = receivefunction
        self.name = re.sub(r"\s+", "", name, flags=re.UNICODE)
        self.byteid =  module.first_free_byte_id
        print(arduino_function)
        arduino_function.byte_id=self.byteid
        self.set_arduino_function(arduino_function)

    def set_arduino_function(self, arduino_function):
        if arduino_function is not None:
            self.arduino_function = arduino_function
        else:
            self.arduino_function = ""

    def defaultsendfunction(self, numericaldata=None):
        if numericaldata is None:
            data = bytearray()
        else:
            data = struct.pack(self.sendtype, numericaldata)
        self.module.serial_port.write(
            bytearray(generate_port_message(self.byteid, self.sendlength, *data))
        )

    def receive(self, bytearray):
        #print(self.receivetype,bytearray)
        self.receivefunction(self.module,struct.unpack(self.receivetype, bytearray)[0])
