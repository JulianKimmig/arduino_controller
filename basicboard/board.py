import time
from collections import OrderedDict

from arduino_controller.portcommand import PortCommand

from basicboard import arduino_data, webgui
from basicboard.ino_creator import InoCreator
from basicboard.pin import Pin

MAXATTEMPTS = 3
IDENTIFYTIME = 2


# noinspection PyBroadException
class ArduinoBasicBoard:
    FIRMWARE = 0

    FIRSTFREEBYTEID = 0

    def get_first_free_byteid(self):
        ffbid = self.FIRSTFREEBYTEID
        self.FIRSTFREEBYTEID += 1
        return ffbid

    firstfreebyteid = property(get_first_free_byteid)

    def __init__(self):
        self.inocreator = InoCreator(self)
        self.inocreator.add_creator(arduino_data.create)
        self._pins = dict()
        self.save_attributes = OrderedDict()
        self.static_attributes = set()
        self.free_digital_pins = list(range(2, 12))
        self.name = None
        self.port = None
        self.lastdata = None
        self.updatetime = 2
        self._datarate = 0
        self.identify_attempts = 0

        self.save_attributes.update(
            {
                "fw": "int+",
                "port": "string",
                "id": "int+",
                "name": "string",
                "updatetime": "double+",
                "datarate": "int+",
                "pins": "int+0",
            }
        )

        self.static_attributes.update(["fw", "id", "port"])
        self.identified = False
        self.id = None
        self.portcommands = []
        self.serialport = None
        self.fw = None
        self.add_port_command(
            PortCommand(
                module=self,
                name="identify",
                receivetype="Q",
                sendtype="?",
                receivefunction=self.receive_id,
                byteid=self.firstfreebyteid,
                arduino_code="identified=data[0];if(!identified){uint64_t id = get_id();write_data(id,{BYTEID});}",
            )
        )
        self.add_port_command(
            PortCommand(
                module=self,
                name="get_fw",
                receivetype="Q",
                receivefunction=self.receive_fw,
                byteid=self.firstfreebyteid,
                arduino_code="write_data((uint64_t)FIRMWARE,{BYTEID});",
            )
        )
        self.add_port_command(
            PortCommand(
                module=self,
                name="datarate",
                receivetype="L",
                sendtype="L",
                receivefunction=lambda data: (self.set_datarate(data, to_board=False)),
                byteid=self.firstfreebyteid,
                arduino_code="uint32_t temp;memcpy(&temp,data,4);if(temp>0){{NAME}=temp;}write_data({NAME},{BYTEID});",
            )
        )

    def set_datarate(self, dc, to_board=True):
        self._datarate = max(1, dc)
        if to_board:
            self.get_portcommand_by_name("datarate").sendfunction(int(self._datarate))

    def set_serial_port(self, serialport):
        self.serialport = serialport
        self.port = serialport.port
        if self.name is None:
            self.name = self.port

    def get_datarate(self):
        return self._datarate

    datarate = property(get_datarate, set_datarate)

    def add_pin(self, pinname, defaultposition, pintype=Pin.DIGITAL_OUT):
        portcommand = PortCommand(
            module=self,
            name=pinname,
            receivetype="B",
            sendtype="B",
            receivefunction=lambda data: (self.set_pin(pinname, data, to_board=False)),
            byteid=self.firstfreebyteid,
        )
        pin = Pin(
            name=pinname,
            defaultposition=defaultposition,
            portcommand=portcommand,
            pintype=pintype,
        )
        self.set_pin(pinname, pin, to_board=False)
        self.add_port_command(portcommand)

    def get_first_free_digitalpin(self, catch=True):
        fp = self.free_digital_pins[0]
        if catch:
            self.free_digital_pins.remove(fp)
        return fp

    def identify(self):
        from arduino_controller.serialreader import BAUDRATES

        for b in set([self.serialport.baudrate] + list(BAUDRATES)):
            self.identify_attempts = 0
            self.serialport.logger.info(
                "intentify with baud " + str(b) + " and firmware " + str(self.FIRMWARE)
            )
            try:
                self.serialport.baudrate = b
                while self.id is None and self.identify_attempts < MAXATTEMPTS:
                    self.get_portcommand_by_name("identify").sendfunction(0)
                    self.identify_attempts += 1
                    time.sleep(IDENTIFYTIME)
                if self.id is not None:
                    self.identified = True
                    break
            except Exception as e:
                self.serialport.logger.exception(e)
                pass
        if not self.identified:
            return False

        self.identified = False
        self.identify_attempts = 0
        while self.fw is None and self.identify_attempts < MAXATTEMPTS:
            self.get_portcommand_by_name("get_fw").sendfunction()
            self.identify_attempts += 1
            time.sleep(IDENTIFYTIME)
        if self.fw is not None:
            self.identified = True
        return self.identified

    def specific_identification(self):
        self.identified = False
        self.identify_attempts = 0
        while self._datarate <= 0 and self.identify_attempts < MAXATTEMPTS:
            self.get_portcommand_by_name("datarate").sendfunction(0)
            self.identify_attempts += 1
            time.sleep(IDENTIFYTIME)
        if self._datarate > 0:
            self.identified = True
        if not self.identified:
            return False

        return self.identified

    def receive_from_port(self, cmd, data):
        self.serialport.logger.debug(
            "receive from port cmd: " + str(cmd) + " " + str([i for i in data])
        )
        portcommand = self.get_portcommand_by_cmd(cmd)
        if portcommand is not None:
            portcommand.receive(data)
        else:
            self.serialport.logger.debug("cmd " + str(cmd) + " not defined")

    def add_port_command(self, port_command):
        if (
                self.get_portcommand_by_cmd(port_command.byteid) is None
                and self.get_portcommand_by_name(port_command.name) is None
        ):
            self.portcommands.append(port_command)
        else:
            self.serialport.logger.error(
                "byteid of "
                + str(port_command)
                + " "
                + port_command.name
                + " already defined"
            )

    def get_portcommand_by_cmd(self, byteid):
        for p in self.portcommands:
            if p.byteid == byteid:
                return p
        return None

    def get_portcommand_by_name(self, command_name):
        for p in self.portcommands:
            if p.name == command_name:
                return p
        return None

    def receive_id(self, data):
        self.id = data

    def receive_fw(self, data):
        self.fw = data

    def datapoint(self, data):
        self.lastdata = data
        if self.identified:
            self.serialport.data_to_socket(key=str(self.id) + "_data", y=data, x=None)

    def restore(self, data):
        for key, value in data.items():
            if key not in self.static_attributes:
                if getattr(self, key, None) != value:
                    print(key, getattr(self, key, None), value)
                    setattr(self, key, value)

    def set_pins(self, pindict):
        for pin_name, pin in pindict.items():
            self.set_pin(pin_name, pin)

    def get_pins(self):
        return self._pins

    pins = property(get_pins, set_pins)

    def set_pin(self, pin_name, pin, to_board=True):
        if isinstance(pin, Pin):
            if self._pins.get(pin_name, None) == pin:
                return
            elif self._pins.get(pin_name, None) is not None:
                if self._pins[pin_name].position == pin.position:
                    self._pins[pin_name] = pin
                    return
            else:
                self._pins[pin_name] = pin
        else:
            if pin_name in self._pins:
                if self._pins[pin_name].position == pin:
                    return
                else:
                    self._pins[pin_name].position = pin
            else:
                return
        try:
            self.serialport.logger.info(
                "set Pin " + pin_name + " to " + str(self._pins[pin_name].position)
            )
        except Exception as e:
            pass
        if to_board:
            self._pins[pin_name].portcommand.sendfunction(pin)

    def get_pin(self, pin_name):
        self._pins.get(pin_name, None)

    def serialize_attribute(self, value):
        try:
            return value.to_json()
        except Exception as e:
            pass

        if isinstance(value, dict):
            return {key: self.serialize_attribute(val) for key, val in value.items()}
        if isinstance(value, list):
            return [self.serialize_attribute(val) for val in value]
        return value

    def save(self):
        data = {}

        for attribute in self.save_attributes:
            val = getattr(self, attribute, None)
            val = self.serialize_attribute(val)
            data[attribute] = val

        return data

    def get_web_gui(self):
        return {
            "moduleclasscaller": self.webgui_get_module_classclaller(),
            "moduleclass": self.webgui_get_module_class(),
            "moduleoptions": webgui.get_module_options(self),
            "modulecontroller": self.webgui_get_module_controller(),
        }

    def webgui_get_module_class(self):
        return None

    def webgui_get_module_controller(self):
        return None

    def webgui_get_module_classclaller(self):
        return "ArduinoBasicBoard"


if __name__ == "__main__":
    import inspect
    import os

    ins = ArduinoBasicBoard()

    ino = ins.inocreator.create()
    dir = os.path.dirname(inspect.getfile(ins.__class__))
    name = os.path.basename(dir)
    with open(os.path.join(dir, name + ".ino"), "w+") as f:
        f.write(ino)
