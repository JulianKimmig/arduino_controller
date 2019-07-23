import logging
import time
from collections import OrderedDict

import numpy as np

# from multi_purpose_arduino_controller.arduino_controller.arduino_variable import arduio_variable
# from multi_purpose_arduino_controller.arduino_controller.basicboard import arduino_data
# from multi_purpose_arduino_controller.arduino_controller.basicboard.ino_creator import InoCreator
# from multi_purpose_arduino_controller.arduino_controller.basicboard.pin import Pin
# from multi_purpose_arduino_controller.arduino_controller.portcommand import PortCommand
import inspect

from arduino_controller.modul_variable import ModuleVariable
from arduino_controller.python_variable import python_variable
from arduino_controller.arduino_variable import arduio_variable
from arduino_controller.basicboard import arduino_data

from arduino_controller.basicboard.ino_creator import InoCreator
from arduino_controller.basicboard.pin import Pin
from arduino_controller.portcommand import PortCommand
from arduino_controller.portrequest import DATABYTEPOSITION

MAXATTEMPTS = 3
IDENTIFYTIME = 2
_GET_PREFIX = "get_"
_SET_PREFIX = "set_"

# noinspection PyBroadException
class ArduinoBasicBoard:
    FIRMWARE = 0
    FIRSTFREEBYTEID = 0
    BAUD = 9600
    CLASSNAME = None

    def get_first_free_byte_id(self):
        ffbid = self.FIRSTFREEBYTEID
        self.FIRSTFREEBYTEID += 1
        return ffbid

    first_free_byte_id = property(get_first_free_byte_id)

    firmware = arduio_variable(name='firmware', type='uint64_t', arduino_setter=False, default=-1,save=False)
    data_rate = arduio_variable(name='data_rate', type='uint32_t', default=200, minimum=1, eeprom=True)

    def create_ino(self):
        import inspect
        import os
        self.firmware = self.FIRMWARE
        ino = self.inocreator.create()
        dir = os.path.dirname(inspect.getfile(self.__class__))
        name = os.path.basename(dir)
        with open(os.path.join(dir, name + ".ino"), "w+") as f:
            f.write(ino)

    def __init__(self):
        self.inocreator = InoCreator(self)
        self.inocreator.add_creator(ArduinoBasicBoardArduinoData)

        if self.CLASSNAME is None:
            self.CLASSNAME = self.__class__.__name__

        self._serial_port = None
        self._port = None
        self._logger = logging.getLogger("Unidentified " + self.__class__.__name__)

        # self._pins = dict()
        # self.save_attributes = OrderedDict()
        # self.static_attributes = set()
        # self.free_digital_pins = list(range(2, 12))
        self.name = None

        self._last_data = None
        self._update_time = 2
        self._identify_attempts = 0

        # self.save_attributes.update(
        #     {
        #         "firmware": "int+",
        #         "port": "string",
        #         "id": "int+",
        #         "name": "string",
        #         "updatetime": "double+",
        #         "pins": "int+0",
        #     }
        # )

        # self.static_attributes.update(["firmware", "id", "port"])

        self.identified = False
        self.id = None
        self.port_commands = []

        def _receive_id(self,data):
            self.id = int(np.uint64(data))

        self.add_port_command(
            PortCommand(
                module=self,
                name="identify",
                receivetype="Q",
                sendtype="?",
                receivefunction=_receive_id,
                byteid=self.first_free_byte_id,
                arduino_code="identified=data[0];uint64_t id = get_id();write_data(id,{BYTEID});",
            )
        )

        for attr, ard_var in self.get_arduino_vars().items():
            if ard_var.arduino_setter is not None:
                self.add_port_command(
                    PortCommand(
                        module=self,
                        name=_SET_PREFIX + ard_var.name,
                        sendtype=ard_var.sendtype,
                        receivetype=None,
                        receivefunction=ard_var.set_without_sending_to_board,
                        arduino_code=ard_var.arduino_setter,
                    )
                )
            if ard_var.arduino_getter is not None:
                self.add_port_command(
                    PortCommand(
                        module=self,
                        name=_GET_PREFIX + ard_var.name,
                        sendtype=None,
                        receivetype=ard_var.receivetype,
                        receivefunction=ard_var.set_without_sending_to_board,
                        arduino_code=ard_var.arduino_getter,
                    )
                )

    def get_arduino_vars(self):
        ardvars = {}
        for attr, ard_var in  self.get_module_vars().items():
            if isinstance(ard_var, arduio_variable):
                ardvars[attr] = ard_var
        return ardvars

    def get_python_vars(self):
        pyvars = {}
        for attr, pyvar in self.get_module_vars().items():
            if isinstance(pyvar, python_variable):
                pyvars[attr] = pyvar
        return pyvars

    def get_module_vars(self):
        mod_vars = {}
        classes = inspect.getmro(self.__class__)
        for cls in reversed(classes):
            for attr, mod_var in cls.__dict__.items():
                if isinstance(mod_var, ModuleVariable):
                    mod_vars[attr] = mod_var
        return mod_vars

    def set_serial_port(self, serialport):
        self._serial_port = serialport
        self._logger = serialport.logger

        if self.name is None or self.name == self._port:
            self.name = serialport.port
        self._port = serialport.port

    def get_serial_port(self):
        return self._serial_port

    def get_port(self):
        return self._port

    serial_port = property(get_serial_port, set_serial_port)
    port = property(get_port)

    def identify(self):
        from arduino_controller.serialport import BAUDRATES
        for b in set([self._serial_port.baudrate] + list(BAUDRATES)):
            self._identify_attempts = 0
            self._logger.info("intentify with baud " + str(b) + " and firmware " + str(self.FIRMWARE))
            try:
                self._serial_port.baudrate = b
                while self.id is None and self._identify_attempts < MAXATTEMPTS:
                    self.get_portcommand_by_name("identify").sendfunction(0)
                    self._identify_attempts += 1
                    time.sleep(IDENTIFYTIME)
                if self.id is not None:
                    self.identified = True
                    break
            except Exception as e:
                self._logger.exception(e)
        if not self.identified:
            return False

        self.identified = False
        self._identify_attempts = 0
        while self.firmware == -1 and self._identify_attempts < MAXATTEMPTS:
            self.get_portcommand_by_name(_GET_PREFIX + "firmware").sendfunction()
            self._identify_attempts += 1
            time.sleep(IDENTIFYTIME)
        if self.firmware > -1:
            self.identified = True
        return self.identified

    def receive_from_port(self, cmd, data):
        self._logger.debug("receive from port cmd: " + str(cmd) + " " + str([i for i in data]))
        portcommand = self.get_portcommand_by_cmd(cmd)
        if portcommand is not None:
            portcommand.receive(data)
        else:
            self._logger.debug("cmd " + str(cmd) + " not defined")

    def add_port_command(self, port_command):
        if (
                self.get_portcommand_by_cmd(port_command.byteid) is None
                and self.get_portcommand_by_name(port_command.name) is None
        ):
            self.port_commands.append(port_command)
        else:
            self._logger.error(
                "byteid of "
                + str(port_command)
                + " "
                + port_command.name
                + " already defined"
            )

    def get_portcommand_by_cmd(self, byteid):
        for p in self.port_commands:
            if p.byteid == byteid:
                return p
        return None

    def get_portcommand_by_name(self, command_name):
        for p in self.port_commands:
            if p.name == command_name:
                return p
        return None

    # def add_pin(self, pinname, defaultposition, pintype=Pin.DIGITAL_OUT):
    #     portcommand = PortCommand(
    #         module=self,
    #         name=pinname,
    #         receivetype="B",
    #         sendtype="B",
    #         receivefunction=lambda data: (ArduinoBasicBoard.set_pin(pinname, data, to_board=False)),
    #         byteid=self.first_free_byte_id,
    #     )
    #     pin = Pin(
    #         name=pinname,
    #         defaultposition=defaultposition,
    #         portcommand=portcommand,
    #         pintype=pintype,
    #     )
    #     self.set_pin(pinname, pin, to_board=False)
    #     self.add_port_command(portcommand)

    # def get_first_free_digitalpin(self, catch=True):
    #    fp = self.free_digital_pins[0]
    #   if catch:
    #        self.free_digital_pins.remove(fp)
    #   return fp

    # def specific_identification(self):
    #    self.identified = False
    #    self.identify_attempts = 0
    #    while self._datarate <= 0 and self.identify_attempts < MAXATTEMPTS:
    #        self.get_portcommand_by_name("datarate").sendfunction(0)
    #        self.identify_attempts += 1
    #        time.sleep(IDENTIFYTIME)
    #    if self._datarate > 0:
    #        self.identified = True
    #    if not self.identified:
    #        return False

    #   return self.identified

    def data_point(self, name, data):
        self._last_data = data
        if self.identified:
            self._serial_port.add_data_point(self, str(name), y=data, x=None)

    def restore(self, data):
        #for key, value in data.items():
            #if key not in self.static_attributes:
                #if getattr(self, key, None) != value:
                    #setattr(self, key, value)

        for attr, ard_var in self.get_module_vars().items():
            if ard_var.save and attr in data:
                setattr(self, attr, data[attr])
        for attr, py_var in self.get_python_vars().items():
            if py_var.save and attr in data:
                setattr(self, attr, data[attr])

    # def set_pins(self, pindict):
    #    for pin_name, pin in pindict.items():
    #        self.set_pin(pin_name, pin)

    # def get_pins(self):
    #   return self._pins

    # pins = property(get_pins, set_pins)

    # def set_pin(self, pin_name, pin, to_board=True):
    #     if isinstance(pin, Pin):
    #         if self._pins.get(pin_name, None) == pin:
    #             return
    #         elif self._pins.get(pin_name, None) is not None:
    #             if self._pins[pin_name].position == pin.position:
    #                 self._pins[pin_name] = pin
    #                 return
    #         else:
    #             self._pins[pin_name] = pin
    #     else:
    #         if pin_name in self._pins:
    #             if self._pins[pin_name].position == pin:
    #                 return
    #             else:
    #                 self._pins[pin_name].position = pin
    #         else:
    #             return
    #     try:
    #         self.serialport.logger.info(
    #             "set Pin " + pin_name + " to " + str(self._pins[pin_name].position)
    #         )
    #     except Exception as e:
    #         pass
    #     if to_board:
    #         self._pins[pin_name].portcommand.sendfunction(pin)
    # 
    # def get_pin(self, pin_name):
    #     return self._pins.get(pin_name, None)

    #def serialize_attribute(self, value):
        #try:
        #    return value.to_json()
        #except Exception as e:
        #    pass

        #if isinstance(value, dict):
        #    return {key: self.serialize_attribute(val) for key, val in value.items()}
        #if isinstance(value, list):
        #    return [self.serialize_attribute(val) for val in value]
        #return value

    def save(self):
        data = {}
        # for attribute in self.save_attributes:
        #    val = getattr(self, attribute, None)
        #    val = self.serialize_attribute(val)
        #    data[attribute] = val
        for attr, py_var in self.get_module_vars().items():
            if py_var.save:
                data[attr] = py_var.value
        return data

    def get_board(self):
        board = {
            'module_variables': {},
        }
        for attr, ard_var in self.get_module_vars().items():
            form = ard_var.html_input.replace("{{value}}", str(getattr(self, attr, '')))
            board['module_variables'][attr] = {
                'form': form
            }
        return board

    def set_update_time(self,update_time):
        self._update_time = update_time

    def get_update_time(self):
        return self._update_time

    update_time = property(get_update_time,set_update_time)


from arduino_controller.basicboard.arduino_data import ArduinoData

class ArduinoBasicBoardArduinoData(ArduinoData):

    def definitions(self):

        return {
            "STARTANALOG": 0,
            "ENDANALOG": 100,
            "STARTBYTE": 2,
            "STARTBYTEPOSITION": 0,
            "COMMANDBYTEPOSITION": 1,
            "LENBYTEPOSITION": 2,
            "DATABYTEPOSITION": 3,
            "MAXFUNCTIONS": len(self.board_instance.port_commands),
            "SERIALARRAYSIZE":
                DATABYTEPOSITION
                + max(
                    *[
                        max(portcommand.receivelength, portcommand.sendlength)
                        for portcommand in self.board_instance.port_commands
                    ]
                )
                + 2
            ,
            "BAUD": self.board_instance.BAUD,
        }

    def global_vars(self):
        return {
            #**{name: ["uint8_t", str(pin.position)] for name, pin in self.board_instance.pins.items()},
            **{ard_var.name: [ard_var.type, ard_var.value] for attr,ard_var in self.board_instance.get_arduino_vars().items() if ard_var.is_global_var},
            "writedata[SERIALARRAYSIZE]": ["uint8_t", None],
            "serialread[SERIALARRAYSIZE]": ["uint8_t", None],
            "serialreadpos": ["uint8_t", 0],
            "commandlength": ["uint8_t", 0],
            "cmds[MAXFUNCTIONS ]": ["uint8_t", None],
            "cmd_length[MAXFUNCTIONS]": ["uint8_t", None],
            "(*cmd_calls[MAXFUNCTIONS])(uint8_t* data, uint8_t s)": ["void", None],
            "lastdata": ["uint32_t", 0],
            "ct": ["uint32_t", None],
            "c": ["uint8_t", None],
            "identified": ["bool", "false"],
        }

    def includes(self):  # ["<Package.h"]
        return ["<EEPROM.h>"]

    def functions(self):  # name:[returntype,[(argtype,argname),...], stringcode]
        return {
            "generate_checksum": [
                "uint16_t",
                [("uint8_t*", "data"), ("int", "count")],
                "uint16_t sum1 = 0;\n"
                "uint16_t sum2 = 0;\n"
                "for (int index = 0; index < count; ++index ) {\n"
                "sum1 = (sum1 + data[index]) % 255;\n"
                "sum2 = (sum2 + sum1) % 255;\n"
                "}\n"
                "return (sum2 << 8) | sum1;\n",
            ],
            "write_data_array": [
                "void",
                [("uint8_t*", "data"), ("uint8_t", "cmd"), ("uint8_t", "len")],
                "writedata[STARTBYTEPOSITION] = STARTBYTE;\n"
                "writedata[COMMANDBYTEPOSITION] = cmd;\n"
                "writedata[LENBYTEPOSITION] = len;\n"
                "for (uint8_t i = 0; i < len; i++) {\n"
                "writedata[DATABYTEPOSITION + i] = data[i];\n"
                "}"
                "uint16_t cs = generate_checksum(writedata, len + DATABYTEPOSITION);\n"
                "writedata[DATABYTEPOSITION + len] = cs >> 8;\n"
                "writedata[DATABYTEPOSITION + len + 1] = cs >> 0;\n"
                "Serial.write(writedata, len + DATABYTEPOSITION + 2);\n",
            ],
            "write_data": [
                "template< typename T> void",
                [("T", "data"), ("uint8_t", "cmd")],
                "uint8_t d[sizeof(T)];\n"
                "for (uint8_t i = 0;i<sizeof(T) ; i++) {\n"
                "d[i] = (uint8_t) (data >> (8 * i) & 0xff );\n"
                "}\n"
                "write_data_array(d, cmd, sizeof(T));\n",
            ],
            "get_id": [
                "uint64_t",
                [],
                "uint64_t id;\n" "EEPROM.get(0, id);\n" "return id;\n",
            ],
            "checkUUID": [
                "void",
                [],
                "uint64_t id = get_id();\n"
                "uint16_t cs = generate_checksum((uint8_t*)&id, sizeof(id));\n"
                "uint16_t cs2;\n"
                "EEPROM.get(sizeof(id), cs2);\n"
                "if (cs != cs2) {\n"
                "id = (uint64_t)("
                "(((uint64_t)random()) << 48) | "
                "(((uint64_t)random()) << 32) | "
                "(((uint64_t)random()) << 16) | "
                "(((uint64_t)random()))"
                ");\n"
                "EEPROM.put(0, id);\n"
                "EEPROM.put(sizeof(id), generate_checksum((uint8_t*)&id, sizeof(id)));\n"
                "}\n",
            ],
            "add_command": [
                "void",
                [
                    ("uint8_t", "cmd"),
                    ("uint8_t", "len"),
                    ("void", "(*func)(uint8_t* data, uint8_t s)"),
                ],
                "for (uint8_t i = 0; i < MAXFUNCTIONS; i++ ) {\n"
                "if (cmds[i] == 255) {\n"
                "cmds[i] = cmd;\n"
                "cmd_length[i] = len;\n"
                "cmd_calls[i] = func;\n"
                "return;\n"
                "}\n"
                "}\n",
            ],
            "endread": [
                "void",
                [],
                "commandlength = 0;\n" "serialreadpos = STARTBYTEPOSITION;\n",
            ],
            "get_cmd_index": [
                "uint8_t",
                [("uint8_t", "cmd")],
                "for (uint8_t i = 0; i < MAXFUNCTIONS; i++ ) {\n"
                "if (cmds[i] == cmd) {\n"
                "return i;\n"
                "}\n"
                "}\n"
                ""
                "return 255;",
            ],
            "validate_serial_command": [
                "void",
                [],
                "if(generate_checksum(serialread, DATABYTEPOSITION + serialread[LENBYTEPOSITION]) == (uint16_t)(serialread[DATABYTEPOSITION + serialread[LENBYTEPOSITION]] << 8) + serialread[DATABYTEPOSITION + serialread[LENBYTEPOSITION]+1]){\n"
                "uint8_t cmd_index = get_cmd_index(serialread[COMMANDBYTEPOSITION]);\n"
                "if(cmd_index != 255){\n"
                "uint8_t data[serialread[LENBYTEPOSITION]];\n"
                "memcpy(data,&serialread[DATABYTEPOSITION],serialread[LENBYTEPOSITION]);\n"
                "cmd_calls[cmd_index](data,serialread[LENBYTEPOSITION]);\n"
                "}\n"
                "}\n",
            ],
            "readloop": [
                "uint64_t",
                [],
                "while(Serial.available() > 0) {\n"
                "c = Serial.read();\n"
                "serialread[serialreadpos] = c;\n"
                "if (serialreadpos == STARTBYTEPOSITION) {\n"
                "if (c == STARTBYTE) {\n"
                "} else {\n"
                "endread();\n"
                "continue;\n"
                "}\n"
                "}\n"
                "else {\n"
                "if (serialreadpos == LENBYTEPOSITION) {\n"
                "commandlength = c;\n"
                "} else if (serialreadpos - commandlength > DATABYTEPOSITION + 1 ) { //stx cmd len cs cs (len = 0; pos = 4)\n"
                "endread();\n"
                "continue;\n"
                "}\n"
                "else if (serialreadpos - commandlength == DATABYTEPOSITION + 1) {\n"
                "validate_serial_command();\n"
                "endread();\n"
                "continue;\n"
                "}\n"
                "}\n"
                "serialreadpos++;\n"
                "}\n",
            ],
            **{
                portcommand.name
                + "_"
                + str(portcommand.byteid): [
                    "void",
                    [("uint8_t*", "data"), ("uint8_t", "s")],
                    portcommand.arduino_code,
                ]
                for portcommand in self.board_instance.port_commands
            },
        }

    def setup(self):
        setup = (
            "Serial.begin(BAUD);\n"
            "while (!Serial) {;}\n"
            "for (int i = STARTANALOG; i < ENDANALOG; i++) {\n"
            "randomSeed(analogRead(i)*random());\n"
            "}\n"
            "checkUUID();\n"
            "for (uint8_t i = 0; i < MAXFUNCTIONS; i++ ) {\n"
            "cmds[i] = 255;\n"
            "}\n"
            "ct = millis();\n"
        )
        #for name, pin in self.board_instance.pins.items():
        #    setup += "pinMode(" + name + ", " + pin.arduinoMode() + ");\n"
        for portcommand in self.board_instance.port_commands:
            setup += (
                    "add_command("
                    + str(portcommand.byteid)
                    + ", "
                    + str(portcommand.sendlength)
                    + ", "
                    + portcommand.name
                    + "_"
                    + str(portcommand.byteid)
                    + ");\n"
            )
        return setup

    def loop(self):
        return (
            "readloop();\n"
            "ct = millis();\n"
            "if(ct-lastdata>data_rate && identified){\n"
            "dataloop();\n"
            "lastdata=ct;\n"
            "}\n"
        )

    def dataloop(self):
        return ""

if __name__ == "__main__":
    ins = ArduinoBasicBoard()
    ins.create_ino()
