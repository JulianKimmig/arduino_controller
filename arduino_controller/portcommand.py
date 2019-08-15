import re

import numpy as np

from .portrequest import generate_port_message


class PortCommand:
    def __init__(
        self,
        module,
        name,
        python_receivetype=None,
        python_sendtype=None,
        receivefunction=None,
        sendfunction=None,
        arduino_function=None,
    ):

        self.module = module

        self.sendlength = (
            np.array([], dtype=python_sendtype).itemsize
            if python_sendtype is not None
            else 0
        )
        self.receivelength = (
            np.array([], dtype=python_receivetype).itemsize
            if python_receivetype is not None
            else 0
        )
        # print(name,self.sendlength,self.receivelength)

        self.python_sendtype = python_sendtype
        self.python_receivetype = python_receivetype

        if sendfunction is None:
            sendfunction = self.defaultsendfunction

        self.sendfunction = sendfunction
        self.receivefunction = receivefunction
        self.name = re.sub(r"\s+", "", name, flags=re.UNICODE)
        self.byteid = module.first_free_byte_id

        # print(arduino_function)
        # print(self.byteid, self.name)
        # arduino_function.byte_id=self.byteid
        self.set_arduino_function(arduino_function)

    def set_arduino_function(self, arduino_function):

        if arduino_function is not None:
            self.arduino_function = arduino_function
            self.arduino_function.name = "{}_{}".format(
                self.arduino_function.name, self.byteid
            )
            self.module.byte_ids.add_possibility(self.arduino_function,self.byteid)
        else:
            self.arduino_function = None

    def defaultsendfunction(self, numericaldata=None):
        print(numericaldata)
        if numericaldata is None:
            data = bytearray()
        else:
            data = np.array([numericaldata], dtype=self.python_sendtype).tobytes()
        print(data)
        self.module.serial_port.write(
            bytearray(generate_port_message(self.byteid, self.sendlength, *data))
        )

    def receive(self, nparray):
        # print(self.python_receivetype,nparray)
        #print(nparray,self.python_receivetype)
        self.receivefunction(
            self.module,
            np.frombuffer(nparray, dtype=self.python_receivetype)[0]
            # struct.unpack(self.python_receivetype, bytearray)[0]
        )
