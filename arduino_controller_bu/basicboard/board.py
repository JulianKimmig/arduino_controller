import inspect
import logging
import time

from ArduinoCodeCreator import basic_types as at
from ArduinoCodeCreator.arduino import Eeprom, Serial, Arduino
from ArduinoCodeCreator.arduino_data_types import *
from ArduinoCodeCreator.basic_types import ArduinoClass
from ArduinoCodeCreator.code_creator import ArduinoCodeCreator
from ArduinoCodeCreator.statements import (
    for_,
    if_,
    return_,
    while_,
    continue_,
    else_,
    elseif_,
)
from arduino_controller.modul_variable import ModuleVariable
from arduino_controller.portcommand import PortCommand
from arduino_controller.python_variable import python_variable

MAXATTEMPTS = 3
IDENTIFYTIME = 2
_GET_PREFIX = "get_"
_SET_PREFIX = "set_"
COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS = [
    at.Array("data", uint8_t, 0),
    at.Variable(type=uint8_t, name="s"),
]
WRITE_DATA_FUNCTION = at.Function(
    "write_data", ((T, "data"), (uint8_t, "cmd")), template_void
)
from arduino_controller.arduino_variable import arduio_variable, ArduinoVariable


class ArduinoBoard:
    FIRMWARE = -1

    def create_ino(self, file=None, obscure=False):
        arduino_code_creator = ArduinoCodeCreator()
        assert self.FIRMWARE > -1, "No Firmware defined"

        self.firmware = self.FIRMWARE
        for attr, modvar in self.get_module_vars().items():
            modvar.return_self = True

        for boardclass in reversed(self.__class__.__mro__):
            if issubclass(boardclass, ArduinoBasicBoard):
                if "add_arduino_code" in boardclass.__dict__:
                    boardclass.add_arduino_code(self, arduino_code_creator)
                self.add_board_to_arduino(boardclass, arduino_code_creator)
        ino = arduino_code_creator.create_code(obscure=obscure)

        import inspect
        import os

        if file is None:
            print(ino)
            return

        with open(file, "w+") as f:
            f.write(ino)

    def __init__(self):
        self.loaded_modules = []
        for module in self.modules:
            self.load_module(module)

    def load_module(self, module):
        if module.unique and module in self.loaded_modules:
            return
        # load depencies
        for depency in module.depencies:
            self.load_module(depency)

        # load modul variables

        self.loaded_modules.append(module)


class ArduinoBoardModul:
    depencies = []
    unique = False
    pass


class BasicBoardModul(ArduinoBoardModul):
    pass


class BasicBoard(ArduinoBoard):
    FIRMWARE = 0
    unique = True
    firmware = arduio_variable(
        name="firmware",
        arduino_data_type=uint64_t,
        arduino_setter=False,
        default=-1,
        save=False,
    )


# noinspection PyBroadException
class ArduinoBasicBoard:
    FIRMWARE = 0
    FIRSTFREEBYTEID = 0
    BAUD = 9600
    CLASSNAME = None

    dataloop = at.Function("dataloop")
    arduino_identified_var = at.Variable(type=bool_, value=0, name="identified")

    arduino_id = arduio_variable(
        arduino_data_type=uint64_t,
        name="id",
        eeprom=True,
        getter=False,
        setter=False,
        arduino_setter=False,
        arduino_getter=False,
    )
    arduino_id_cs = arduio_variable(
        arduino_data_type=uint16_t,
        name="id_cs",
        eeprom=True,
        getter=False,
        setter=False,
        arduino_setter=False,
        arduino_getter=False,
    )

    data_rate = arduio_variable(
        name="data_rate", arduino_data_type=uint32_t, minimum=1, eeprom=True
    )

    def pre_ini_function(self):
        for attr, modvar in self.get_module_vars().items():
            modvar.return_self = True

    def post_ini_function(self):
        pass

    def __init__(self):
        self.parse_base_boards(self.baseboards)
        self.module_vars = None
        self.pre_ini_function()
        for attr, modvar in self.get_module_vars(reforce=True).items():
            modvar.return_self = False

        self.eeprom_position = at.ArduinoEnum("eeprom_position", {})

        if self.CLASSNAME is None:
            self.CLASSNAME = self.__class__.__name__

        self._serial_port = None
        self._port = None
        self._logger = logging.getLogger("Unidentified " + self.__class__.__name__)

        self.name = None

        self._last_data = None
        self._update_time = 2
        self._identify_attempts = 0

        self.identified = False
        self.id = None
        self.port_commands = []

        attr_dict = dict()
        for cls in reversed(inspect.getmro(self.__class__)):
            attr_dict.update(cls.__dict__)
        attr_dict.update(self.__dict__)
        for attr, attr_var in attr_dict.items():
            if attr_var is not None:
                if isinstance(attr_var, arduio_variable):
                    attr_var.initialize(self, attr)

        def _receive_id(self, data):
            self.id = int(np.uint64(data))

        self.add_port_command(
            PortCommand(
                module=self,
                name="identify",
                python_receivetype=np.uint64,
                python_sendtype=np.bool,
                receivefunction=_receive_id,
                arduino_function=at.Function(
                    return_type=void,
                    arguments=COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS,
                    name="identify",
                    code=(
                        self.arduino_identified_var.set(
                            COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS[0][0]
                        ),
                        WRITE_DATA_FUNCTION(self.arduino_id, "BYTEID"),
                    )
                    # "identified=data[0];"+
                    # "write_data(id,{BYTEID});"
                ),
            )
        )

        for attr, ard_var in self.get_arduino_vars(reforce=True).items():

            if ard_var.arduino_setter is not None:
                self.add_port_command(
                    PortCommand(
                        module=self,
                        name=_SET_PREFIX + ard_var.name,
                        python_sendtype=ard_var.type.python_type,
                        python_receivetype=None,
                        receivefunction=ard_var.set_without_sending_to_board,
                        arduino_function=ard_var.arduino_setter,
                    )
                )
            if ard_var.arduino_getter is not None:
                self.add_port_command(
                    PortCommand(
                        module=self,
                        name=_GET_PREFIX + ard_var.name,
                        python_sendtype=None,
                        python_receivetype=ard_var.type.python_type,
                        receivefunction=ard_var.set_without_sending_to_board,
                        arduino_function=ard_var.arduino_getter,
                    )
                )

        self.post_ini_function()

    def get_first_free_byte_id(self):
        ffbid = self.FIRSTFREEBYTEID
        self.FIRSTFREEBYTEID += 1
        return ffbid

    first_free_byte_id = property(get_first_free_byte_id)

    def get_arduino_vars(self, reforce=False):
        ardvars = {}
        for attr, ard_var in self.get_module_vars(reforce=reforce).items():
            if isinstance(ard_var, ArduinoVariable):
                ardvars[attr] = ard_var
        return ardvars

    def get_python_vars(self, reforce=False):
        pyvars = {}
        for attr, pyvar in self.get_module_vars(reforce=reforce).items():
            if isinstance(pyvar, python_variable):
                pyvars[attr] = pyvar
        return pyvars

    def get_module_vars(self, reforce=False):
        if self.module_vars is not None and not reforce:
            return self.module_vars
        mod_vars = {}
        classes = inspect.getmro(self.__class__)
        for cls in reversed(classes):
            for attr, mod_var in cls.__dict__.items():
                if isinstance(mod_var, ModuleVariable):
                    mod_vars[attr] = mod_var

        for attr, mod_var in vars(self).items():
            if isinstance(mod_var, ModuleVariable):
                mod_vars[attr] = mod_var

        self.module_vars = mod_vars
        return self.module_vars

    def get_module_var_by_name(self, name):
        for attr, var in self.get_module_vars().items():
            if attr == name:
                return var
        return None

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
            self._logger.info(
                "intentify with baud " + str(b) + " and firmware " + str(self.FIRMWARE)
            )
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
        self._logger.debug(
            "receive from port cmd: " + str(cmd) + " " + str([i for i in data])
        )
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

    def get_portcommand_arduino_getter(self, arduino_getter):
        if arduino_getter is None:
            return None
        for p in self.port_commands:
            if p.arduino_function is arduino_getter:
                return p
        return None

    def data_point(self, name, data):
        self._last_data = data
        if self.identified:
            self._serial_port.add_data_point(self, str(name), y=data, x=None)

    def restore(self, data):
        for attr, ard_var in self.get_module_vars().items():
            if ard_var.save and attr in data:
                setattr(self, attr, data[attr])
        for attr, ard_var in self.get_arduino_vars().items():
            print(attr)
            if ard_var.eeprom:
                pc = self.get_portcommand_arduino_getter(ard_var.arduino_getter)
                if pc is not None:
                    pc.sendfunction(0)
                print(attr, self.get_portcommand_arduino_getter(ard_var.arduino_getter))

    def save(self):
        data = {}
        for attr, py_var in self.get_module_vars().items():
            if py_var.save:
                data[attr] = py_var.value
        return data

    def get_board(self):
        board = {"module_variables": {}}
        print("AAAAAAAAAAAAAAAAAAAAAAAA")
        for attr, mod_var in self.get_module_vars().items():
            if len(mod_var.html_input) > 0:
                form = mod_var.html_input.replace(
                    "{{value}}", str(getattr(self, attr, ""))
                )
                board["module_variables"][attr] = {"form": form}
        return board

    def set_update_time(self, update_time):
        self._update_time = update_time

    def get_update_time(self):
        return self._update_time

    update_time = property(get_update_time, set_update_time)

    def add_arduino_code(self, ad):
        from arduino_controller.portrequest import (
            STARTBYTE,
            DATABYTEPOSITION,
            LENBYTEPOSITION,
            STARTBYTEPOSITION,
            COMMANDBYTEPOSITION,
        )

        # from ArduinoCodeCreator import arduino_default_functions as df
        # from ArduinoCodeCreator import operators as op
        # from ArduinoCodeCreator.variable import ArduinoDefinition, at.Variable, at.Array,ArduinoInclude

        # from ArduinoCodeCreator.functions import at.FunctionArray, at.Function, at.FunctionSet

        BYTEID = ad.add(at.Definition("BYTEID", 0, obscurable=False))
        STARTANALOG = ad.add(at.Definition("STARTANALOG", 0))
        STARTBYTE = ad.add(at.Definition("STARTBYTE", int.from_bytes(STARTBYTE, "big")))
        STARTBYTEPOSITION = ad.add(
            at.Definition("STARTBYTEPOSITION", STARTBYTEPOSITION)
        )
        COMMANDBYTEPOSITION = ad.add(
            at.Definition("COMMANDBYTEPOSITION", COMMANDBYTEPOSITION)
        )
        LENBYTEPOSITION = ad.add(at.Definition("LENBYTEPOSITION", LENBYTEPOSITION))
        ENDANALOG = ad.add(at.Definition("ENDANALOG", 100))
        MAXFUNCTIONS = ad.add(at.Definition("MAXFUNCTIONS", len(self.port_commands)))
        BAUD = ad.add(at.Definition("BAUD", self.BAUD))

        SERIALARRAYSIZE = ad.add(
            at.Definition(
                "SERIALARRAYSIZE",
                DATABYTEPOSITION
                + max(
                    *[
                        max(portcommand.receivelength, portcommand.sendlength)
                        for portcommand in self.port_commands
                    ],
                    0,
                    0
                )
                + 2,
            )
        )

        DATABYTEPOSITION = ad.add(at.Definition("DATABYTEPOSITION", DATABYTEPOSITION))

        last_data = ad.add(at.Variable("lastdata", uint32_t, 0))
        current_time = ad.add(at.Variable(type=uint32_t, name="current_time"))
        current_character = ad.add(at.Variable(type=uint8_t, name="current_character"))
        checksum = ad.add(at.Variable(type=uint16_t, name="checksum"))

        serialreadpos = ad.add(at.Variable(type=uint8_t, value=0, name="serialreadpos"))
        commandlength = ad.add(at.Variable(type=uint8_t, value=0, name="commandlength"))

        writedata = ad.add(
            at.Array(size=SERIALARRAYSIZE, type=uint8_t, name="writedata")
        )
        serialread = ad.add(
            at.Array(size=SERIALARRAYSIZE, type=uint8_t, name="serialread")
        )
        cmds = ad.add(at.Array(size=MAXFUNCTIONS, type=uint8_t, name="cmds"))
        cmd_length = ad.add(
            at.Array(size=MAXFUNCTIONS, type=uint8_t, name="cmd_length")
        )
        cmd_calls = ad.add(
            at.FunctionArray(
                size=MAXFUNCTIONS,
                return_type=void,
                arguments=COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS,
                name="cmd_calls",
            )
        )

        ad.add(Eeprom)

        i = for_.i

        generate_checksum = ad.add(
            at.Function(
                "generate_checksum",
                [at.Array("data"), (uint8_t, "count")],
                variables=[(uint8_t, "sum1", 0), (uint8_t, "sum2", 0)],
            )
        )
        generate_checksum.add_call(
            # count_vaiable,endcondition,raising_value=1
            for_(
                i,
                i < generate_checksum.arg2,
                code=(
                    generate_checksum.var1.set(
                        generate_checksum.var1 + generate_checksum.arg1[i]
                    ),
                    generate_checksum.var2.set(
                        generate_checksum.var1 + generate_checksum.var2
                    ),
                ),
            ),
            checksum.set(
                generate_checksum.var2.cast(uint16_t) * 256 + generate_checksum.var1
            ),
        )

        write_data_array = ad.add(
            at.Function(
                "write_data_array",
                [at.Array("data"), (uint8_t, "cmd"), (uint8_t, "len")],
                void,
            )
        )

        write_data_array.add_call(
            writedata[STARTBYTEPOSITION].set(STARTBYTE),
            writedata[COMMANDBYTEPOSITION].set(write_data_array.arg2),
            writedata[LENBYTEPOSITION].set(write_data_array.arg3),
            for_(
                i,
                i < write_data_array.arg3,
                1,
                writedata[DATABYTEPOSITION + i].set(write_data_array.arg1[i]),
            ),
            generate_checksum(writedata, write_data_array.arg3 + DATABYTEPOSITION),
            writedata[DATABYTEPOSITION + write_data_array.arg3].set(checksum >> 0),
            writedata[DATABYTEPOSITION + write_data_array.arg3 + 1].set(checksum >> 8),
            Serial.write_buf(writedata, DATABYTEPOSITION + write_data_array.arg3 + 2),
        )

        write_data_function = ad.add(WRITE_DATA_FUNCTION)
        d = write_data_function.add_variable(
            at.Array(size=Arduino.sizeof(T), type=uint8_t, name="d")
        )
        write_data_function.add_call(
            for_(
                i,
                i < Arduino.sizeof(T),
                1,
                d[i].set((write_data_function.arg1 >> i * 8 & 0xFF).cast(uint8_t)),
            ),
            write_data_array(d, write_data_function.arg2, Arduino.sizeof(T)),
        )

        check_uuid = ad.add(
            at.Function(
                "check_uuid", return_type=void, variables=[(checksum.type, "id_cs")]
            )
        )

        checkuuidvar = at.Variable(
            "i", uint8_t, self.eeprom_position.get(self.arduino_id)
        )
        check_uuid.add_call(
            generate_checksum(
                self.arduino_id.to_pointer(), Arduino.sizeof(self.arduino_id)
            ),
            Eeprom.get(Arduino.sizeof(self.arduino_id), check_uuid.var1),
            if_(
                checksum != check_uuid.var1,
                code=(
                    for_(
                        checkuuidvar,
                        checkuuidvar < Arduino.sizeof(self.arduino_id),
                        1,
                        Eeprom.write(i, Arduino.random()),
                    ),
                    Eeprom.get(
                        self.eeprom_position.get(self.arduino_id), self.arduino_id
                    ),
                    generate_checksum(
                        self.arduino_id.to_pointer(), Arduino.sizeof(self.arduino_id)
                    ),
                    Eeprom.put(self.eeprom_position.get(self.arduino_id_cs), checksum),
                ),
            ),
        )

        add_command = ad.add(
            at.Function(
                return_type=void,
                arguments=[
                    (uint8_t, "cmd"),
                    (uint8_t, "len"),
                    at.Function(
                        return_type=void,
                        arguments=[(uint8_t_pointer, "data"), (uint8_t, "s")],
                        name="caller",
                    ),
                ],
                name="add_command",
            )
        )
        add_command.add_call(
            for_(
                i,
                i < MAXFUNCTIONS,
                1,
                if_(
                    cmds[i] == 255,
                    code=(
                        cmds[i].set(add_command.arg1),
                        cmd_length[i].set(add_command.arg2),
                        cmd_calls[i].set(add_command.arg3),
                        return_(),
                    ),
                ),
            )
        )

        endread = ad.add(at.Function("endread"))
        endread.add_call(commandlength.set(0), serialreadpos.set(0))

        get_cmd_index = ad.add(
            at.Function("get_cmd_index", [(uint8_t, "cmd")], uint8_t)
        )
        get_cmd_index.add_call(
            for_(
                i, i < MAXFUNCTIONS, 1, if_(cmds[i] == get_cmd_index.arg1, return_(i))
            ),
            return_(255),
        )

        validate_serial_command = ad.add(
            at.Function(
                "validate_serial_command",
                variables=[
                    (uint8_t, "cmd_index"),
                    at.Array(size=serialread[LENBYTEPOSITION], name="data"),
                ],
            )
        )
        validate_serial_command.add_call(
            generate_checksum(
                serialread, DATABYTEPOSITION + serialread[LENBYTEPOSITION]
            ),
            if_(
                checksum
                == (
                    (
                        serialread[DATABYTEPOSITION + serialread[LENBYTEPOSITION] + 1]
                    ).cast(uint16_t)
                    * 256
                )
                + serialread[DATABYTEPOSITION + serialread[LENBYTEPOSITION]],
                code=(
                    validate_serial_command.var1.set(
                        get_cmd_index(serialread[COMMANDBYTEPOSITION])
                    ),
                    if_(
                        validate_serial_command.var1 != 255,
                        code=(
                            Arduino.memcpy(
                                validate_serial_command.var2,
                                serialread[DATABYTEPOSITION].to_pointer(),
                                serialread[LENBYTEPOSITION],
                            ),
                            cmd_calls[validate_serial_command.var1](
                                validate_serial_command.var2,
                                serialread[LENBYTEPOSITION],
                            ),
                        ),
                    ),
                ),
            ),
        )

        readloop = ad.add(
            at.Function(
                "readloop",
                code=(
                    while_(
                        Serial.available() > 0,
                        code=(
                            if_(serialreadpos > SERIALARRAYSIZE, endread()),
                            current_character.set(Serial.read()),
                            serialread[serialreadpos].set(current_character),
                            if_(
                                serialreadpos == STARTBYTEPOSITION,
                                code=if_(
                                    current_character != STARTBYTE,
                                    code=(endread(), continue_()),
                                ),
                            ),
                            else_(
                                if_(
                                    serialreadpos == LENBYTEPOSITION,
                                    commandlength.set(current_character),
                                ),
                                elseif_(
                                    serialreadpos - commandlength
                                    > DATABYTEPOSITION + 1,
                                    code=(endread(), continue_()),
                                ),
                                elseif_(
                                    serialreadpos - commandlength
                                    == DATABYTEPOSITION + 1,
                                    code=(
                                        validate_serial_command(),
                                        endread(),
                                        continue_(),
                                    ),
                                ),
                            ),
                            serialreadpos.set(serialreadpos + 1),
                        ),
                    )
                ),
            )
        )

        ad.loop.add_call(
            readloop(),
            current_time.set(Arduino.millis()),
            if_(
                (current_time - last_data > self.data_rate).and_(
                    self.arduino_identified_var
                ),
                code=(self.dataloop(), last_data.set(current_time)),
            ),
        )

        ti = at.Variable("i", int_, STARTANALOG)
        ad.setup.add_call(
            Serial.begin(BAUD),
            # Eeprom.get(0, self.arduino_id),
            for_(
                ti,
                ti < ENDANALOG,
                1,
                Arduino.randomSeed(
                    Arduino.max(1, Arduino.analogRead(ti)) * Arduino.random()
                ),
            ),
            check_uuid(),
            for_(i, i < MAXFUNCTIONS, 1, cmds[i].set(255)),
            current_time.set(Arduino.millis()),
            *[
                add_command(
                    portcommand.byteid,
                    portcommand.sendlength,
                    portcommand.arduino_function.name,
                )
                for portcommand in self.port_commands
            ]
        )

        for portcommand in self.port_commands:
            ad.add(BYTEID.redefine(portcommand.byteid))
            ad.add(portcommand.arduino_function)

        for name, attr in vars(self).items():
            if isinstance(attr, at.Variable):
                if getattr(attr, "add_to_code", True):
                    ad.add(attr)
            if isinstance(attr, ArduinoVariable):
                self.add_ardvar_to_board(attr, ad)

            if isinstance(attr, at.Function):
                ad.add(attr)

            if isinstance(attr, at.ArduinoEnum):
                ad.add(attr)

            if isinstance(attr, ArduinoClass):
                ad.add(attr)

    def add_ardvar_to_board(self, attr, ad):
        if attr.is_data_point:
            print(attr)
            self.dataloop.add_call(
                WRITE_DATA_FUNCTION(
                    attr, self.get_portcommand_by_name(_GET_PREFIX + attr.name).byteid
                )
            )
        if attr.eeprom:
            self.eeprom_position.add_possibility(attr, size=attr.type.byte_size)
            ad.setup.prepend_call(Eeprom.get(self.eeprom_position.get(attr), attr))

    def __getattribute__(self, attr):
        obj = object.__getattribute__(self, attr)
        if isinstance(obj, ModuleVariable):
            obj = obj.get_value(self, type(self))
        return obj

    def __setattr__(self, attr, value):
        obj = None
        if hasattr(self, attr):
            obj = object.__getattribute__(self, attr)
        if isinstance(obj, ModuleVariable):
            obj = obj.set_value(self, value)
        else:
            object.__setattr__(self, attr, value)

    def add_board_to_arduino(self, boardclass, ad):
        for attr_name, attr in boardclass.__dict__.items():
            if isinstance(attr, at.Variable):
                if getattr(attr, "add_to_code", True):
                    ad.add(attr)
            if isinstance(attr, ArduinoVariable):
                self.add_ardvar_to_board(attr, ad)

            if isinstance(attr, at.Function):
                ad.add(attr)

            if isinstance(attr, at.ArduinoEnum):
                ad.add(attr)

            if isinstance(attr, ArduinoClass):
                ad.add(attr)
        pass


if __name__ == "__main__":
    ins = BasicBoard()
    ins.create_ino()
