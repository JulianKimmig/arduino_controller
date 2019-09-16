import logging
import logging
import time

from ArduinoCodeCreator import basic_types as at
from ArduinoCodeCreator.arduino import Eeprom, Serial, Arduino
from ArduinoCodeCreator.arduino_data_types import *
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
from arduino_controller.modul_variable import ModuleVariableTemplate, ModuleVariable
from arduino_controller.portcommand import PortCommand
from arduino_controller.python_variable import PythonVariable

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
    modules = []
    FIRMWARE = -1
    BAUD = 9600
    CLASSNAME = None

    def __init__(self):
        if self.CLASSNAME is None:
            self.CLASSNAME = self.__class__.__name__

        self._first_free_byte_id = 0
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
        self.id = None

        self._loaded_module_instances = []
        self._module_variables = {}
        self.eeprom_position = at.ArduinoEnum("eeprom_position", {})
        self.byte_ids = at.ArduinoEnum("byte_ids", {})

        for module in self.modules:
            self.load_module(module)
        # print(self._loaded_module_instances)
        self.initalize_variables()

        for module in self._loaded_module_instances:
            module.post_initalization()

        for attr, ard_var in self._module_variables.items():
            if isinstance(ard_var, ArduinoVariable):
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

        for attr, modvar in self._module_variables.items():
            modvar.return_self = False

    def create_ino(self, file=None, obscure=False):
        arduino_code_creator = ArduinoCodeCreator()
        assert self.FIRMWARE > -1, "No Firmware defined"

        #self.firmware = self.FIRMWARE
        for attr, modvar in self._module_variables.items():
            modvar.return_self = True
        self.firmware.value = self.FIRMWARE
        module_classes = []
        for module in self._loaded_module_instances:
            if module.__class__ not in module_classes:
                module_classes.append(module.__class__)

        for module_class in module_classes:
            module_class._module_arduino_code(self, arduino_code_creator)
            module_class.module_arduino_code(self, arduino_code_creator)

        for module in self._loaded_module_instances:
            module._instance_arduino_code(arduino_code_creator)
            module.instance_arduino_code(arduino_code_creator)
        ino = arduino_code_creator.create_code(obscure=obscure)

        if file is None:
            print(ino)
            return

        with open(file, "w+") as f:
            f.write(ino)

    def initalize_variables(self):

        for module in self._loaded_module_instances:
            for attribute, tempplate in module.module_variable_templates.items():
                tempplate.original_name = attribute
                i = 0
                while tempplate.name in self._module_variables:
                    i += 1
                    tempplate.name = "{}_{}".format(attribute, i)
                self._module_variables[tempplate.name] = tempplate.initialize(
                    self, tempplate.name
                )
                setattr(module, attribute, self._module_variables[tempplate.name])

        # print(self._module_variables)

    def load_module(self, module):
        """
        :type module: ArduinoBoardModule
        """
        module_instance = module.get_instance(self)
        if module_instance in self._loaded_module_instances:
            return module_instance

        for name, submodule in module_instance.get_dependencies().items():
            setattr(module_instance, name, self.load_module(submodule))

        if module_instance in self._loaded_module_instances:
            return module_instance
        self._loaded_module_instances.append(module_instance)

        return module_instance

    def set_update_time(self, update_time):
        self._update_time = update_time

    def get_update_time(self):
        return self._update_time

    update_time = property(get_update_time, set_update_time)

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

    def get_portcommand_by_name(self, command_name):
        for p in self.port_commands:
            if p.name == command_name:
                return p
        return None

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

    def get_first_free_byte_id(self):
        ffbid = self._first_free_byte_id
        self._first_free_byte_id += 1
        return ffbid

    first_free_byte_id = property(get_first_free_byte_id)

    def get_portcommand_by_cmd(self, byteid):
        for p in self.port_commands:
            if p.byteid == byteid:
                return p
        return None

    def add_port_command(self, port_command):
        assert (
            self.get_portcommand_by_cmd(port_command.byteid) is None
            and self.get_portcommand_by_name(port_command.name) is None
        ), "byteid of {} {} already defined".format(port_command, port_command.name)
        self.port_commands.append(port_command)
        return port_command

    def get_module_vars(self):
        return self._module_variables

    def get_arduino_vars(self):
        return {
            attr: ard_var
            for attr, ard_var in self.get_module_vars().items()
            if isinstance(ard_var, ArduinoVariable)
        }

    def get_python_vars(self):
        return {
            attr: ard_var
            for attr, ard_var in self.get_module_vars().items()
            if isinstance(ard_var, PythonVariable)
        }

    def receive_from_port(self, cmd, data):
        self._logger.debug(
            "receive from port cmd: " + str(cmd) + " " + str([i for i in data])
        )
        portcommand = self.get_portcommand_by_cmd(cmd)
        if portcommand is not None:
            portcommand.receive(data)
        else:
            self._logger.debug("cmd " + str(cmd) + " not defined")

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
        for attr, ard_var in self.get_arduino_vars().items():
            # print(attr)
            if ard_var.arduino_getter:
                pc = self.get_portcommand_arduino_getter(ard_var.arduino_getter)
                if pc is not None:
                    if pc is not None:
                        pc.sendfunction(0)
        time.sleep(1)
        for attr, ard_var in self.get_module_vars().items():
            if ard_var.save and attr in data:
                setattr(self, attr, data[attr])
            # print(attr, self.get_portcommand_arduino_getter(ard_var.arduino_getter))

    def get_all_variable_values(self):
        data = {}
        for attr, py_var in self.get_module_vars().items():
            data[attr] = py_var.value
        return data

    def save(self):
        data = {}
        for attr, py_var in self.get_module_vars().items():
            if py_var.save:
                data[attr] = py_var.value
        return data

    def get_board(self):
        board = {"module_variables": {}}
        for attr, mod_var in self.get_module_vars().items():
            if len(mod_var.html_input) > 0:
                form = mod_var.html_input.replace(
                    "{{value}}", str(getattr(self, attr, ""))
                )
                board["module_variables"][attr] = {"form": form}
        return board

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

    def __repr__(self):
        return "{}({})".format(self.CLASSNAME, self.id)


class ArduinoBoardModule:
    unique = False
    _instances = []

    def post_initalization(self):
        pass

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

    @classmethod
    def add_ardvar_to_board(cls, variable, board, arduino_code_creator):
        if variable.is_data_point:
            BasicBoardModule.dataloop.add_call(
                WRITE_DATA_FUNCTION(
                    variable,
                    board.byte_ids.get(
                        board.get_portcommand_by_name(
                            _GET_PREFIX + variable.name
                        ).arduino_function
                    ),
                )
            )
        if variable.eeprom:
            board.eeprom_position.add_possibility(
                variable, size=variable.type.byte_size
            )
            arduino_code_creator.setup.prepend_call(
                Eeprom.get(board.eeprom_position.get(variable), variable)
            )

    @classmethod
    def _arduino_code_try_to_add_var(cls, variable, board, arduino_code_creator):
        if isinstance(variable, at.Variable):
            if getattr(variable, "add_to_code", True):
                arduino_code_creator.add(variable)

        if isinstance(variable, ArduinoVariable):
            cls.add_ardvar_to_board(variable, board, arduino_code_creator)

        if isinstance(variable, at.Function):
            arduino_code_creator.add(variable)

        if isinstance(variable, at.ArduinoEnum):
            arduino_code_creator.add(variable)

        if isinstance(variable, at.ArduinoClass):
            arduino_code_creator.add(variable)

        if isinstance(variable, at.Definition):
            arduino_code_creator.add(variable)

        if isinstance(variable, at.Include):
            arduino_code_creator.add(variable)

    @classmethod
    def _module_arduino_code(cls, board, arduino_code_creator):
        for name, variable in cls.__dict__.items():
            cls._arduino_code_try_to_add_var(variable, board, arduino_code_creator)

    def _instance_arduino_code(self, arduino_code_creator):
        for name, variable in self.__dict__.items():
            # print(name,variable.__class__)
            self._arduino_code_try_to_add_var(
                variable, self.board, arduino_code_creator
            )

    @classmethod
    def module_arduino_code(cls, board, arduino_code_creator):
        pass

    def instance_arduino_code(self, arduino_code_creator):
        pass

    def __repr__(self):
        return "{}:{}".format(self.__class__.__name__, id(self))

    def get_dependencies(self):
        depencies = {}
        for name, dependency in self.__class__.__dict__.items():
            try:
                if issubclass(dependency, ArduinoBoardModule):
                    depencies[name] = dependency
            except TypeError:
                pass
        return depencies

    def __init__(self, board):
        self.board = board
        self._instances.append(self)
        self.module_variable_templates = {}
        self._load_module_variable_templates()

    def _load_module_variable_templates(self):
        for name, module_variable in self.__class__.__dict__.items():
            try:
                if isinstance(module_variable, ModuleVariableTemplate):
                    self.module_variable_templates[name] = module_variable
            except TypeError:
                pass

    @classmethod
    def get_instance(cls, board, *args, **kwargs):
        initiate = None
        if cls.unique:
            for instance in cls._instances:
                if instance.board is board and cls is instance.__class__:
                    return instance

        return cls(board)


class ArduinoBoard2:
    FIRMWARE = -1
    CLASSNAME = None
    BAUD = 9600
    modules = []

    def __init__(self):

        self._module_variables = {}
        # self.eeprom_position = at.ArduinoEnum("eeprom_position", {})
        # self.byte_ids = at.ArduinoEnum("byte_ids", {})

        self.loaded_module_instances = []
        # for module in self.modules:
        #     self.load_module(module)

        self.initialize_variables()

        for module in self.loaded_module_instances:
            module.after_added_to_board(board=self)
        for attr, modvar in self._module_variables.items():
            modvar.return_self = False

    def initialize_variables(self):
        for module in self.loaded_module_instances:
            for module_variable in module.get_module_variables():
                i = 0
                prename = module_variable.name
                set_name = module_variable.name
                while hasattr(self, set_name):
                    i += 1
                    set_name = "{}_{}".format(module_variable.name, i)

                variable_instance = module_variable.initialize(self, set_name)
                # print(module, prename, variable_instance)
                setattr(module, prename, variable_instance)
                setattr(module, set_name, variable_instance)
                self._module_variables[set_name] = variable_instance


class ArduinoBoardModule2:
    unique = False
    _last_instance = None

    def after_added_to_board(self, board):
        pass

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
            if not obj.return_self:
                obj.set_value(self, value)
                return
        object.__setattr__(self, attr, value)

    # @classmethod
    # def _arduino_code_try_to_add_var(cls,variable, board,arduino_code_creator):
    #     if isinstance(variable, at.Variable):
    #         if getattr(variable, "add_to_code", True):
    #             arduino_code_creator.add(variable)
    #
    #     if isinstance(variable, ArduinoVariable):
    #         cls.add_ardvar_to_board(variable, board, arduino_code_creator)
    #
    #     if isinstance(variable, at.Function):
    #         arduino_code_creator.add(variable)
    #
    #     if isinstance(variable, at.ArduinoEnum):
    #         arduino_code_creator.add(variable)
    #
    #     if isinstance(variable, at.ArduinoClass):
    #         arduino_code_creator.add(variable)
    #
    #     if isinstance(variable, at.Definition):
    #         arduino_code_creator.add(variable)

    # @classmethod
    # def _module_arduino_code(cls, board, arduino_code_creator):
    #     for name, variable in cls.__dict__.items():
    #         cls._arduino_code_try_to_add_var(variable,board,arduino_code_creator)
    #
    # def _instance_arduino_code(self, board, arduino_code_creator):
    #     for name, variable in self.__dict__.items():
    #        # print(name,variable.__class__)
    #         self._arduino_code_try_to_add_var(variable,board,arduino_code_creator)
    #
    #
    # @classmethod
    # def module_arduino_code(cls, board, arduino_code_creator):
    #     pass
    #
    # def instance_arduino_code(self, board, arduino_code_creator):
    #     pass

    def __init__(self):
        self._dependencies = []
        self._module_variables = []
        self.load_dependencies()
        self.load_module_variables()

    # @classmethod
    # def get_instance(cls, *args, **kwargs):
    #     if not cls.unique or cls._last_instance is None:
    #         cls._last_instance = cls(*args, **kwargs)
    #     return cls._last_instance

    # def load_dependencies(self):
    #     for name, dependency in self.__class__.__dict__.items():
    #         try:
    #             if issubclass(dependency, ArduinoBoardModule):
    #                 dependency = dependency.get_instance()
    #                 if dependency not in self._dependencies:
    #                     self._dependencies.append(dependency)
    #                 setattr(self, name, dependency)
    #         except TypeError:
    #             pass

    # def load_module_variables(self):
    #     for name, module_variable in self.__class__.__dict__.items():
    #         try:
    #             if isinstance(module_variable, ModuleVariableTemplate):
    #                 self._module_variables.append(module_variable)
    #         except TypeError:
    #             pass

    def get_module_variables(self, deep=False):
        mv = []
        if deep:
            for dependency in self._dependencies:
                for v in dependency.get_module_variables(deep=True):
                    if v not in mv:
                        mv.append(v)
        for v in self._module_variables:
            v._module_instance = self
            if v not in mv:
                mv.append(v)

        return mv

    def get_dependencies(self, deep=False):
        if not deep:
            dependencies = self._dependencies
        else:
            dependencies = []
            for dependency in self._dependencies:
                dependencies.extend(dependency.get_dependencies(deep=True))
            dependencies.extend(self._dependencies)

        seen = set()
        seen_add = seen.add
        return [x for x in dependencies if not (x in seen or seen_add(x))]

    # @classmethod
    # def add_ardvar_to_board(cls, variable, board, arduino_code_creator):
    #     if variable.is_data_point:
    #         BasicBoardModule.dataloop.add_call(
    #             WRITE_DATA_FUNCTION(
    #                 variable, board.byte_ids.get(board.get_portcommand_by_name(_GET_PREFIX + variable.name).arduino_function)
    #             )
    #         )
    #     if variable.eeprom:
    #         board.eeprom_position.add_possibility(variable, size=variable.type.byte_size)
    #         arduino_code_creator.setup.prepend_call(Eeprom.get(board.eeprom_position.get(variable), variable))


from arduino_controller.portrequest import (
    STARTBYTE,
    DATABYTEPOSITION,
    LENBYTEPOSITION,
    STARTBYTEPOSITION,
    COMMANDBYTEPOSITION,
)


class BasicBoardModule(ArduinoBoardModule):
    unique = True
    firmware = arduio_variable(
        name="firmware",
        arduino_data_type=uint64_t,
        arduino_setter=False,
        default=-1,
        save=False,
        unique=True,
    )
    arduino_id = arduio_variable(
        arduino_data_type=uint64_t,
        name="arduino_id",
        eeprom=True,
        getter=False,
        setter=False,
        arduino_setter=False,
        arduino_getter=False,
    )
    arduino_id_cs = arduio_variable(
        arduino_data_type=uint16_t,
        name="arduino_id_cs",
        eeprom=True,
        getter=False,
        setter=False,
        arduino_setter=False,
        arduino_getter=False,
    )
    data_rate = arduio_variable(
        name="data_rate", arduino_data_type=uint32_t, minimum=1, eeprom=True
    )

    dummy8 = at.Variable("dummy8", type=uint8_t)
    dummy16 = at.Variable("dummy16", type=uint16_t)
    dummy32 = at.Variable("dummy32", type=uint32_t)
    dummy64 = at.Variable("dummy64", type=uint64_t)

    STARTANALOG = at.Definition("STARTANALOG", 0)
    STARTBYTE = at.Definition("STARTBYTE", int.from_bytes(STARTBYTE, "big"))
    STARTBYTEPOSITION = at.Definition("STARTBYTEPOSITION", STARTBYTEPOSITION)

    COMMANDBYTEPOSITION = at.Definition("COMMANDBYTEPOSITION", COMMANDBYTEPOSITION)

    LENBYTEPOSITION = at.Definition("LENBYTEPOSITION", LENBYTEPOSITION)
    ENDANALOG = at.Definition("ENDANALOG", 100)
    MAXFUNCTIONS = at.Definition("MAXFUNCTIONS", 0)
    BAUD = at.Definition("BAUD", 0)
    DATABYTEPOSITION = at.Definition("DATABYTEPOSITION", DATABYTEPOSITION)
    SERIALARRAYSIZE = at.Definition("SERIALARRAYSIZE", DATABYTEPOSITION + 2)

    dataloop = at.Function("dataloop")
    arduino_identified = at.Variable(type=bool_, value=0, name="arduino_identified")
    current_time = at.Variable(type=uint32_t, name="current_time")
    last_time = at.Variable(type=uint32_t, name="last_time")

    def post_initalization(self):
        def _receive_id(board, data):
            board.id = np.uint64(data)

        identify_portcommand = PortCommand(
            module=self.board,
            name="identify",
            python_receivetype=np.uint64,
            python_sendtype=np.bool,
            receivefunction=_receive_id,
            arduino_function=at.Function(
                return_type=void,
                arguments=COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS,
                name="identify",
                code=(
                    self.arduino_identified.set(
                        COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS[0][0]
                    ),
                ),
            ),
        )
        identify_portcommand.arduino_function.add_call(
            WRITE_DATA_FUNCTION(
                self.arduino_id,
                self.board.byte_ids.get(identify_portcommand.arduino_function),
            )
        )
        self.board.add_port_command(identify_portcommand)

    def instance_arduino_code(self, ad):
        self.MAXFUNCTIONS.value = len(self.board.port_commands)
        self.BAUD.value = self.board.BAUD
        self.SERIALARRAYSIZE.value = (
            DATABYTEPOSITION
            + max(
                *[
                    max(portcommand.receivelength, portcommand.sendlength)
                    for portcommand in self.board.port_commands
                ],
                0,
                0
            )
            + 2
        )

        ad.add(self.board.eeprom_position)
        ad.add(self.board.byte_ids)

        last_data = ad.add(at.Variable("lastdata", uint32_t, 0))
        current_character = ad.add(at.Variable(type=uint8_t, name="current_character"))
        checksum = ad.add(at.Variable(type=uint16_t, name="checksum"))

        serialreadpos = ad.add(at.Variable(type=uint8_t, value=0, name="serialreadpos"))
        commandlength = ad.add(at.Variable(type=uint8_t, value=0, name="commandlength"))

        writedata = ad.add(
            at.Array(size=self.SERIALARRAYSIZE, type=uint8_t, name="writedata")
        )
        serialread = ad.add(
            at.Array(size=self.SERIALARRAYSIZE, type=uint8_t, name="serialread")
        )
        cmds = ad.add(at.Array(size=self.MAXFUNCTIONS, type=uint8_t, name="cmds"))
        cmd_length = ad.add(
            at.Array(size=self.MAXFUNCTIONS, type=uint8_t, name="cmd_length")
        )
        cmd_calls = ad.add(
            at.FunctionArray(
                size=self.MAXFUNCTIONS,
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
            writedata[self.STARTBYTEPOSITION].set(self.STARTBYTE),
            writedata[self.COMMANDBYTEPOSITION].set(write_data_array.arg2),
            writedata[self.LENBYTEPOSITION].set(write_data_array.arg3),
            for_(
                i,
                i < write_data_array.arg3,
                1,
                writedata[self.DATABYTEPOSITION + i].set(write_data_array.arg1[i]),
            ),
            generate_checksum(writedata, write_data_array.arg3 + self.DATABYTEPOSITION),
            writedata[self.DATABYTEPOSITION + write_data_array.arg3].set(checksum >> 0),
            writedata[self.DATABYTEPOSITION + write_data_array.arg3 + 1].set(
                checksum >> 8
            ),
            Serial.write_buf(
                writedata, self.DATABYTEPOSITION + write_data_array.arg3 + 2
            ),
        )

        write_data_function = ad.add(WRITE_DATA_FUNCTION)
        # d = write_data_function.add_variable(
        #    at.Array(size=Arduino.sizeof(T), type=uint8_t, name="d")
        # )
        write_data_function.add_call(
            # for_(
            #    i,
            #    i < Arduino.sizeof(T),
            #    1,
            #    d[i].set((write_data_function.arg1 >> i * 8 & 0xFF).cast(uint8_t)),
            # ),
            write_data_array(
                write_data_function.arg1.to_pointer(),
                write_data_function.arg2,
                Arduino.sizeof(T),
            )
        )

        check_uuid = ad.add(
            at.Function(
                "check_uuid", return_type=void, variables=[(checksum.type, "id_cs")]
            )
        )

        checkuuidvar = at.Variable(
            "i", uint8_t, self.board.eeprom_position.get(self.arduino_id)
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
                        self.board.eeprom_position.get(self.arduino_id), self.arduino_id
                    ),
                    generate_checksum(
                        self.arduino_id.to_pointer(), Arduino.sizeof(self.arduino_id)
                    ),
                    Eeprom.put(
                        self.board.eeprom_position.get(self.arduino_id_cs), checksum
                    ),
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
                i < self.MAXFUNCTIONS,
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
                i,
                i < self.MAXFUNCTIONS,
                1,
                if_(cmds[i] == get_cmd_index.arg1, return_(i)),
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
                serialread, self.DATABYTEPOSITION + serialread[self.LENBYTEPOSITION]
            ),
            if_(
                checksum
                == (
                    (
                        serialread[
                            self.DATABYTEPOSITION + serialread[self.LENBYTEPOSITION] + 1
                        ]
                    ).cast(uint16_t)
                    * 256
                )
                + serialread[self.DATABYTEPOSITION + serialread[self.LENBYTEPOSITION]],
                code=(
                    validate_serial_command.var1.set(
                        get_cmd_index(serialread[self.COMMANDBYTEPOSITION])
                    ),
                    if_(
                        validate_serial_command.var1 != 255,
                        code=(
                            Arduino.memcpy(
                                validate_serial_command.var2,
                                serialread[self.DATABYTEPOSITION].to_pointer(),
                                serialread[self.LENBYTEPOSITION],
                            ),
                            cmd_calls[validate_serial_command.var1](
                                validate_serial_command.var2,
                                serialread[self.LENBYTEPOSITION],
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
                            if_(serialreadpos > self.SERIALARRAYSIZE, endread()),
                            current_character.set(Serial.read()),
                            serialread[serialreadpos].set(current_character),
                            if_(
                                serialreadpos == self.STARTBYTEPOSITION,
                                code=if_(
                                    current_character != self.STARTBYTE,
                                    code=(endread(), continue_()),
                                ),
                            ),
                            else_(
                                if_(
                                    serialreadpos == self.LENBYTEPOSITION,
                                    commandlength.set(current_character),
                                ),
                                elseif_(
                                    serialreadpos - commandlength
                                    > self.DATABYTEPOSITION + 1,
                                    code=(endread(), continue_()),
                                ),
                                elseif_(
                                    serialreadpos - commandlength
                                    == self.DATABYTEPOSITION + 1,
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
            self.last_time.set(self.current_time),
            self.current_time.set(Arduino.millis()),
            if_(
                (self.current_time - last_data > self.board.data_rate).and_(
                    self.arduino_identified
                ),
                code=(self.dataloop(), last_data.set(self.current_time)),
            ),
        )

        ti = at.Variable("i", int_, self.STARTANALOG)
        ad.setup.add_call(
            Serial.begin(self.BAUD),
            # Eeprom.get(0, self.arduino_id),
            for_(
                ti,
                ti < self.ENDANALOG,
                1,
                Arduino.randomSeed(
                    Arduino.max(1, Arduino.analogRead(ti)) * Arduino.random()
                ),
            ),
            check_uuid(),
            for_(i, i < self.MAXFUNCTIONS, 1, cmds[i].set(255)),
            self.current_time.set(Arduino.millis()),
            self.last_time.set(self.current_time),
            *[
                add_command(
                    self.board.byte_ids.get(portcommand.arduino_function),
                    portcommand.sendlength,
                    portcommand.arduino_function.name,
                )
                for portcommand in self.board.port_commands
            ]
        )
        for portcommand in self.board.port_commands:
            # arduino_code_creator.add(BYTEID.redefine(portcommand.byteid))
            ad.add(portcommand.arduino_function)


class BasicBoard(ArduinoBoard):
    FIRMWARE = 0
    modules = [BasicBoardModule]


if __name__ == "__main__":
    ins = BasicBoard()
    ins.create_ino()
