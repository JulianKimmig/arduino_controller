# from multi_purpose_arduino_controller.arduino_controller.arduino_variable import arduio_variable
# from multi_purpose_arduino_controller.arduino_controller.basicboard import arduino_data
# from multi_purpose_arduino_controller.arduino_controller.basicboard.ino_creator import InoCreator
# from multi_purpose_arduino_controller.arduino_controller.basicboard.pin import Pin
# from multi_purpose_arduino_controller.arduino_controller.portcommand import PortCommand
import inspect
import logging
import time

import numpy as np

from ArduinoCodeCreator import arduino_data_types as dt
from ArduinoCodeCreator.arduino import Eeprom, Serial,Arduino
from ArduinoCodeCreator.arduino_data_types import uint64_t, uint32_t, void
from ArduinoCodeCreator.code_creator import ArduinoCodeCreator
from ArduinoCodeCreator import basic_types as at
from ArduinoCodeCreator.statements import for_, if_, return_, while_, continue_, else_, elseif_
from arduino_controller.arduino_variable import arduio_variable
from arduino_controller.modul_variable import ModuleVariable
from arduino_controller.portcommand import PortCommand
from arduino_controller.python_variable import python_variable

MAXATTEMPTS = 3
IDENTIFYTIME = 2
_GET_PREFIX = "get_"
_SET_PREFIX = "set_"
COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS = [at.Array("data",dt.uint8_t,0), at.Variable(type=dt.uint8_t, name="s")]
WRITE_DATA_FUNCTION = at.Function("write_data",((dt.T, "data"), (dt.uint8_t, "cmd")),dt.template_void)
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
    firmware = arduio_variable(name='firmware', arduino_data_type=uint64_t, arduino_setter=False, default=-1, save=False)
    data_rate = arduio_variable(name='data_rate', arduino_data_type=uint32_t, default=200, minimum=1, eeprom=True)
    def create_ino(self,obscure=False):
        arduino_code_creator = ArduinoCodeCreator()
        for boardclass in reversed(self.__class__.__mro__):
            if "add_arduino_code" in boardclass.__dict__:
                print(boardclass)
                boardclass.add_arduino_code(self,arduino_code_creator)
        print(arduino_code_creator.create_code(obscure=obscure))
        return
        import inspect
        import os
        self.firmware = self.FIRMWARE
        ino = self.inocreator.create()
        dir = os.path.dirname(inspect.getfile(self.__class__))
        name = os.path.basename(dir)
        with open(os.path.join(dir, name + ".ino"), "w+") as f:
            f.write(ino)

    def __init__(self):
        #self.inocreator = InoCreator(self)
        #self.inocreator.add_creator(ArduinoBasicBoardArduinoData)
        #self.arduino_code_creator = ArduinoCodeCreator()
        #add_to_code_creator(self,self.arduino_code_creator)
        self.module_vars = None
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

        self.identified = False
        self.id = None
        self.port_commands = []

        def _receive_id(self, data):
            self.id = int(np.uint64(data))

        self.add_port_command(
            PortCommand(
                module=self,
                name="identify",
                receivetype="Q",
                sendtype="?",
                receivefunction=_receive_id,
                arduino_function=at.Function(return_type=void,arguments=COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS,name="identify",
                                                 #"identified=data[0];"+
                                                 # "write_data(id,{BYTEID});"
                                                 ),
            )
        )

        for attr, ard_var in self.get_arduino_vars().items():
            if ard_var.arduino_setter is not None:
                self.add_port_command(
                    PortCommand(
                        module=self,
                        name=_SET_PREFIX + ard_var.name,
                        sendtype=ard_var.type.python_type,
                        receivetype=None,
                        receivefunction=ard_var.set_without_sending_to_board,
                        arduino_function=ard_var.arduino_setter,
                    )
                )
            if ard_var.arduino_getter is not None:
                self.add_port_command(
                    PortCommand(
                        module=self,
                        name=_GET_PREFIX + ard_var.name,
                        sendtype=None,
                        receivetype=ard_var.type.python_type,
                        receivefunction=ard_var.set_without_sending_to_board,
                        arduino_function=ard_var.arduino_getter,
                    )
                )


    def get_arduino_vars(self):
        ardvars = {}
        for attr, ard_var in self.get_module_vars().items():
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
        if self.module_vars is not None:
            return self.module_vars
        mod_vars = {}
        classes = inspect.getmro(self.__class__)
        for cls in reversed(classes):
            for attr, mod_var in cls.__dict__.items():
                if isinstance(mod_var, ModuleVariable):
                    mod_vars[attr] = mod_var
        self.module_vars = mod_vars
        return self.module_vars

    def get_module_var_by_name(self,name):
        for attr,var in self.get_module_vars().items():
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
        # for key, value in data.items():
        # if key not in self.static_attributes:
        # if getattr(self, key, None) != value:
        # setattr(self, key, value)

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

    # def serialize_attribute(self, value):
    # try:
    #    return value.to_json()
    # except Exception as e:
    #    pass

    # if isinstance(value, dict):
    #    return {key: self.serialize_attribute(val) for key, val in value.items()}
    # if isinstance(value, list):
    #    return [self.serialize_attribute(val) for val in value]
    # return value

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

    def set_update_time(self, update_time):
        self._update_time = update_time

    def get_update_time(self):
        return self._update_time

    update_time = property(get_update_time, set_update_time)

    def add_arduino_code(self,ad):
        from arduino_controller.portrequest import STARTBYTE, DATABYTEPOSITION, LENBYTEPOSITION, STARTBYTEPOSITION, \
            COMMANDBYTEPOSITION

        #from ArduinoCodeCreator import arduino_default_functions as df
        #from ArduinoCodeCreator import operators as op
        #from ArduinoCodeCreator.variable import ArduinoDefinition, at.Variable, at.Array,ArduinoInclude

        #from ArduinoCodeCreator.functions import at.FunctionArray, at.Function, at.FunctionSet
        
        STARTANALOG = ad.add(at.Definition("STARTANALOG",0))
        STARTBYTE = ad.add(at.Definition("STARTBYTE",int.from_bytes(STARTBYTE,"big")))
        STARTBYTEPOSITION = ad.add(at.Definition("STARTBYTEPOSITION",STARTBYTEPOSITION))
        COMMANDBYTEPOSITION = ad.add(at.Definition("COMMANDBYTEPOSITION",COMMANDBYTEPOSITION))
        LENBYTEPOSITION = ad.add(at.Definition("LENBYTEPOSITION",LENBYTEPOSITION))
        ENDANALOG = ad.add(at.Definition("ENDANALOG",100))
        MAXFUNCTIONS = ad.add(at.Definition("MAXFUNCTIONS",len(self.port_commands)))
        BAUD = ad.add(at.Definition("BAUD",self.BAUD))
        SERIALARRAYSIZE = ad.add(at.Definition(
            "SERIALARRAYSIZE",
            DATABYTEPOSITION + max(*[max(portcommand.receivelength, portcommand.sendlength) for portcommand in self.port_commands]) + 2
            ))

        DATABYTEPOSITION = ad.add(at.Definition("DATABYTEPOSITION",DATABYTEPOSITION))

        last_data = ad.add(at.Variable("lastdata",dt.uint32_t, 0))
        current_time = ad.add(at.Variable(type=dt.uint32_t, name= "current_time"))
        current_character = ad.add(at.Variable(type=dt.uint8_t, name= "current_character"))
        checksum = ad.add(at.Variable(type=dt.uint16_t, name= "checksum"))
        id = ad.add(at.Variable(type=dt.uint64_t, name= "id"))
        identified = ad.add(at.Variable(type=dt.bool,value=0, name= "identified"))
        serialreadpos = ad.add(at.Variable(type=dt.uint8_t,value=0, name= "serialreadpos"))
        commandlength = ad.add(at.Variable(type=dt.uint8_t,value=0, name= "commandlength"))

        writedata = ad.add(at.Array(size=SERIALARRAYSIZE,type=dt.uint8_t, name= "writedata"))
        serialread = ad.add(at.Array(size=SERIALARRAYSIZE,type=dt.uint8_t, name= "serialread"))
        cmds = ad.add(at.Array(size=MAXFUNCTIONS,type=dt.uint8_t, name= "cmds"))
        cmd_length = ad.add(at.Array(size=MAXFUNCTIONS,type=dt.uint8_t, name= "cmd_length"))
        cmd_calls = ad.add(at.FunctionArray(size=MAXFUNCTIONS,return_type=dt.void,arguments=COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS, name= "cmd_calls"))

        ad.add(Eeprom)


        #for name, ardvar in self.get_arduino_vars().items():
        #    ad.add(ardvar)


        i = for_.i
        #((dt.uint8_t_pointer, "data"), (dt.uint8_t, "count"))
        generate_checksum = ad.add(
            at.Function("generate_checksum",[at.Array("data"),(dt.uint8_t, "count")],
                        variables=[(dt.uint16_t,"sum1",0),(dt.uint16_t,"sum2",0)],
                        ))
        #sum1,sum2 = generate_checksum.add_variable()
        generate_checksum.add_call(
            #count_vaiable,endcondition,raising_value=1
            for_(i,i < generate_checksum.arg2,
                code=(
                    generate_checksum.var1.set((generate_checksum.var1 + generate_checksum.arg1[i])%255),
                    generate_checksum.var2.set((generate_checksum.var1 + generate_checksum.var2) % 255)
                    )
                 ),
            checksum.set(generate_checksum.var2 << 8 | generate_checksum.var1)
        )


        write_data_array = ad.add(at.Function("write_data_array",[at.Array("data"),(dt.uint8_t, "cmd"),(dt.uint8_t, "len")],dt.void))

        write_data_array.add_call(
            writedata[STARTBYTEPOSITION].set(STARTBYTE),
            writedata[COMMANDBYTEPOSITION].set(write_data_array.arg2),
            writedata[LENBYTEPOSITION].set(write_data_array.arg3),
            for_(i, i < write_data_array.arg3,1,
                 writedata[DATABYTEPOSITION + i].set(write_data_array.arg1[i])
                 ),
            generate_checksum(writedata,write_data_array.arg3 + DATABYTEPOSITION),
            writedata[DATABYTEPOSITION + write_data_array.arg3].set(checksum >> 8),
            writedata[DATABYTEPOSITION + write_data_array.arg3 + 1].set(checksum >> 0),
            Serial.write_buf(writedata,DATABYTEPOSITION + write_data_array.arg3 + 2)
        )


        for attr_name,attr in self.__class__.__dict__.items():
            if isinstance(attr,at.Function):
                ad.add(attr)



        write_data_function = ad.add(WRITE_DATA_FUNCTION)
        d = write_data_function.add_variable(at.Array(size = Arduino.sizeof(dt.T),type=dt.uint8_t,name="d"))
        write_data_function.add_call(
            for_(i,i < Arduino.sizeof(dt.T),1,
                             d[i].set((write_data_function.arg1 >> i * 8 & 0xff).cast(dt.uint8_t))
                             ),
             write_data_array(d,write_data_function.arg2,Arduino.sizeof(dt.T))
        )

        check_uuid = ad.add(
            at.Function(
                "check_uuid",return_type=dt.void,
                variables=[(checksum.type,"id_cs")]
            ))
        check_uuid.add_call(
            generate_checksum(id.to_pointer(),Arduino.sizeof(id)),
            Eeprom.get(Arduino.sizeof(id),check_uuid.var1),
            if_(checksum != check_uuid.var1,
                                code = (
                                    id.set(Arduino.random().cast(dt.uint64_t) << 48 | Arduino.random().cast(dt.uint64_t) << 32| Arduino.random().cast(dt.uint64_t) << 16 | Arduino.random().cast(dt.uint64_t)),
                                    Eeprom.put(0,id),
                                    generate_checksum(id.to_pointer(),Arduino.sizeof(id)),
                                    Eeprom.put(Arduino.sizeof(id),checksum)
                                )
                            )
        )

        add_command = ad.add(at.Function(return_type=dt.void,
                                         arguments=[
                                             (dt.uint8_t,"cmd"),
                                             (dt.uint8_t,"len"),
                                             at.Function(return_type=dt.void,arguments=[(dt.uint8_t_pointer,"data"),(dt.uint8_t,"s")],name="caller")
                                         ],name="add_command"))
        add_command.add_call(
            for_(i,i<MAXFUNCTIONS,1,
                             if_(cmds[i] == 255,
                                             code=(
                                                 cmds[i].set(add_command.arg1),
                                                 cmd_length[i].set(add_command.arg2),
                                                 cmd_calls[i].set(add_command.arg3)
                                             )
                                             )
                             )
        )


        endread = ad.add(at.Function("endread"))
        endread.add_call(
            commandlength.set(0),
            serialreadpos.set(0)
        )

        get_cmd_index = ad.add(at.Function("get_cmd_index",[(dt.uint8_t,"cmd")],dt.uint8_t))
        get_cmd_index.add_call(
            for_(i,i<MAXFUNCTIONS,1,
                             if_(cmds[i] == get_cmd_index.arg1,
                                             return_(i))
                             ),
            return_(255)
        )

        

        validate_serial_command = ad.add(
            at.Function(
                "validate_serial_command",
                variables=[(dt.uint8_t,"cmd_index"),
                           at.Array(size=serialread[LENBYTEPOSITION],name="data")]
            ))
        validate_serial_command.add_call(
            generate_checksum(serialread,DATABYTEPOSITION+serialread[LENBYTEPOSITION]),
            if_(checksum == ((serialread[DATABYTEPOSITION + serialread[LENBYTEPOSITION]]
                                    ).cast(dt.uint16_t) << 8) + serialread[DATABYTEPOSITION + serialread[LENBYTEPOSITION] + 1],
                code=(
                    validate_serial_command.var1.set(get_cmd_index(serialread[COMMANDBYTEPOSITION])),
                    if_(validate_serial_command.var1 != 255,
                       code=(
                            Arduino.memcpy(validate_serial_command.var2,serialread[DATABYTEPOSITION].to_pointer(),serialread[LENBYTEPOSITION]),
                           cmd_calls[validate_serial_command.var1](validate_serial_command.var2,serialread[LENBYTEPOSITION])
                       )
                       )
                )
            )
        )
        

        readloop = ad.add(
            at.Function("readloop",
                        code=(
                            while_(
                                Serial.available() > 0,
                                code=(
                                    current_character.set(Serial.read()),
                                     serialread[serialreadpos].set(current_character),
                                     if_(
                                         serialreadpos == STARTBYTEPOSITION,
                                         code=if_(
                                             current_character != STARTBYTE,
                                             code=(
                                                 endread(),
                                                 continue_(),
                                             )
                                         )
                                     ),
                                     else_(
                                         if_(
                                                 serialreadpos == LENBYTEPOSITION,
                                                 commandlength.set(current_character)
                                             ),
                                             elseif_(
                                                 serialreadpos - commandlength > DATABYTEPOSITION + 1,
                                                 code=(
                                                     endread(),
                                                     continue_()
                                                 )
                                             ),
                                             elseif_(
                                                 serialreadpos - commandlength == DATABYTEPOSITION + 1,
                                                 code=(
                                                     validate_serial_command(),
                                                     endread(),
                                                     continue_()
                                                 )
                                             )
                                     ),
                                     serialreadpos.set(serialreadpos+1)
                                )
                            )
                        )
                        ))

        for function in [portcommand.arduino_function for portcommand in self.port_commands]:
            ad.add(function)

        dataloop = ad.add(at.Function("dataloop"))


        ad.loop.add_call(
            readloop(),
            current_time.set(Arduino.millis()),
            if_(
                (current_time-last_data > 0) & identified,
                code = (
                    dataloop(),
                    last_data.set(current_time)
                )
            )
        )

        ti = at.Variable("i",dt.int,STARTANALOG)
        ad.setup.add_call(
            Serial.begin(BAUD),
            Eeprom.get(0,id),
            for_(
                ti,ti<ENDANALOG,1,
                Arduino.randomSeed(Arduino.max(1,Arduino.analogRead(ti))*Arduino.random())
            ),
            check_uuid(),
            for_(i,i<MAXFUNCTIONS,1,cmds[i].set(255)),
            current_time.set(Arduino.millis()),
           # *[add_command(portcommand.commandbyte,portcommand.receivelength,portcommand.name) for portcommand in self.port_commands]
        )

# void identify_0(uint8_t* data, uint8_t s){
# identified=data[0];write_data(id,0);
# }

# void loop(){
# if(((ct - lastdata) > data_rate && identified)){
# }
# }
#
# void setup(){
# add_command(0, 1, identify_0);
# add_command(1, 0, get_firmware_1);
# add_command(2, 4, set_data_rate_2);
# add_command(3, 0, get_data_rate_3);
#
# }

#
# from arduino_controller.arduino_data import ArduinoData, ArduinoDataDefinition, ArduinoDataGlobalVariable, \
#     ArduinoDataGlobalVariableArray, ArduinoDataGlobalVariableFunctionArray, ArduinoDataInclude, ArduinoDataFunction, \
#     ArduinoDataTypes, at.Variable, at.VariableFunction, ArduinoSetupFunction, ArduinoLoopFunction
# from arduino_controller.portrequest import STARTBYTE, DATABYTEPOSITION, LENBYTEPOSITION, STARTBYTEPOSITION, \
#     COMMANDBYTEPOSITION
#
#
# class ArduinoBasicBoardArduinoData(ArduinoData):
#     # definitions
#
#     STARTANALOG = ArduinoDataDefinition("STARTANALOG", 0)
#     ENDANALOG = ArduinoDataDefinition("ENDANALOG", 100)
#
#     MAXFUNCTIONS = ArduinoDataDefinition("MAXFUNCTIONS", lambda self: len(self.board_instance.port_commands))
#     BAUD = ArduinoDataDefinition("BAUD", lambda self: self.board_instance.BAUD)
#     SERIALARRAYSIZE = ArduinoDataDefinition("SERIALARRAYSIZE", lambda self: DATABYTEPOSITION + max(
#         *[max(portcommand.receivelength, portcommand.sendlength) for portcommand in
#           self.board_instance.port_commands]) + 2)
#
#     # global variables
#     lastdata = ArduinoDataGlobalVariable("lastdata", ArduinoDataTypes.uint32_t, 0)
#     ct = ArduinoDataGlobalVariable("ct", ArduinoDataTypes.uint32_t)
#     c = ArduinoDataGlobalVariable("c", ArduinoDataTypes.uint8_t)
#     cs = ArduinoDataGlobalVariable("cs", ArduinoDataTypes.uint16_t)
#     id = ArduinoDataGlobalVariable("id", ArduinoDataTypes.uint64_t)
#     identified = ArduinoDataGlobalVariable("identified", ArduinoDataTypes.bool, 0)
#     serialreadpos = ArduinoDataGlobalVariable("serialreadpos", ArduinoDataTypes.uint8_t, 0)
#     commandlength = ArduinoDataGlobalVariable("commandlength", ArduinoDataTypes.uint8_t, 0)
#
#     writedata = ArduinoDataGlobalVariableArray("writedata", ArduinoDataTypes.uint8_t, SERIALARRAYSIZE)
#     serialread = ArduinoDataGlobalVariableArray("serialread", ArduinoDataTypes.uint8_t, SERIALARRAYSIZE)
#     cmds = ArduinoDataGlobalVariableArray("cmds", ArduinoDataTypes.uint8_t, MAXFUNCTIONS)
#     cmd_length = ArduinoDataGlobalVariableArray("cmd_length", ArduinoDataTypes.uint8_t, MAXFUNCTIONS)
#     cmd_calls = ArduinoDataGlobalVariableFunctionArray(name="cmd_calls", size=MAXFUNCTIONS, return_type="void",
#                                                        arguments=((ArduinoDataTypes.uint8_t_array, "data"), (ArduinoDataTypes.uint8_t, "s")))
#
#     # includes
#     EEPROM_include = ArduinoDataInclude("EEPROM.h")
#
#     # functions
#     generate_checksum = ArduinoDataFunction(
#         name="generate_checksum",
#         return_type=ArduinoDataTypes.uint16_t,
#         arguments=((ArduinoDataTypes.uint8_t_array, "data"), (ArduinoDataTypes.uint8_t, "count"))
#     )
#
#
#     sum1 = generate_checksum.add_new_variable(ArduinoDataTypes.uint16_t,"sum1",0)
#     sum2 = generate_checksum.add_new_variable(ArduinoDataTypes.uint16_t,"sum2",0)
#     generate_checksum.set_function(
#         sum1.initialization_code() +
#         sum2.initialization_code() +
#         ArduinoDataFunction.for_loop_int(generate_checksum.get_variable("count"),
#                                          sum1.code_set(ArduinoDataFunction.mod(
#                                              ArduinoDataFunction.add(sum1,
#                                                                      ArduinoDataFunction.get_index(
#                                                                          generate_checksum.get_variable("data"),
#                                                                          "i"
#                                                                      )
#                                                                      ),
#                                              255))+
#                                          sum2.code_set(ArduinoDataFunction.mod(
#                                              ArduinoDataFunction.add(sum1,sum2),
#                                              255
#                                          ))
#                                          )+
#         cs.code_set("("+str(sum2)+" << 8) | "+str(sum1))
#     )
#
#
#     write_data_array = ArduinoDataFunction(
#         name="write_data_array",
#         arguments=((ArduinoDataTypes.uint8_t_array, "data"), (ArduinoDataTypes.uint8_t, "cmd"), (ArduinoDataTypes.uint8_t, "len")),
#     )
#     write_data_array.set_function(
#         ArduinoDataFunction.set_index(writedata,STARTBYTEPOSITION,int.from_bytes(STARTBYTE, "big"))+
#         ArduinoDataFunction.set_index(writedata,COMMANDBYTEPOSITION,write_data_array.get_variable("cmd"))+
#         ArduinoDataFunction.set_index(writedata,LENBYTEPOSITION,write_data_array.get_variable("len"))+
#         ArduinoDataFunction.for_loop_int(write_data_array.get_variable("len"),
#                                          ArduinoDataFunction.set_index(writedata,
#                                                                        ArduinoDataFunction.add(DATABYTEPOSITION,"i"),
#                                                                        ArduinoDataFunction.get_index(write_data_array.get_variable("data"),"i")
#                                                                        )
#                                          ) +
#         ArduinoDataFunction.run_function(
#             generate_checksum,
#             writedata,
#             ArduinoDataFunction.add(
#                 write_data_array.get_variable("len"),DATABYTEPOSITION
#             )
#         ) +
#         ArduinoDataFunction.set_index(writedata,
#                                       ArduinoDataFunction.add(DATABYTEPOSITION,write_data_array.get_variable("len")),
#                                       str(cs)+" >> 8"
#                                       ) +
#         ArduinoDataFunction.set_index(writedata,
#                                       ArduinoDataFunction.add(DATABYTEPOSITION,write_data_array.get_variable("len"),1),
#                                       str(cs)+" >> 0"
#                                       )+
#         ArduinoDataFunction.serial_write(writedata,ArduinoDataFunction.add(DATABYTEPOSITION,write_data_array.get_variable("len"),2))
#     )
#
#
#     write_data = ArduinoDataFunction(
#         name="write_data",
#         return_type="template< typename T> void",
#         arguments=[("T", "data"), (ArduinoDataTypes.uint8_t, "cmd")],
#         #function=lambda self:"uint8_t d[sizeof(T)];\n"+
#         #                     "for (uint8_t i = 0;i<sizeof(T) ; i++) {\n"+
#         #                     "d[i] = (uint8_t) (data >> (8 * i) & 0xff );\n"+
#         #                     "}\n"+
#          #                    "{}(d, cmd, sizeof(T));\n".format(self.write_data_array.name)
#     )
#
#     d = write_data.add_new_array(ArduinoDataTypes.uint8_t,size="sizeof(T)")
#     write_data.set_function(
#         d.initialization_code()+
#         ArduinoDataFunction.for_loop_int(d.size,
#                                          d.code_set("i","(uint8_t) (data >> (8 * i) & 0xff )")
#                                          )+
#         ArduinoDataFunction.run_function(write_data_array,d,write_data.get_variable("cmd"),"sizeof(T)")
#     )
#
#     checkUUID = ArduinoDataFunction(name="checkUUID")
#
#     id_cs=checkUUID.add_new_variable(ArduinoDataTypes.uint16_t)
#     checkUUID.set_function(
#         ArduinoDataFunction.run_function(generate_checksum,
#                                          ArduinoDataFunction.variable_to_pointer(id),
#                                          ArduinoDataFunction.sizeof(id),
#                                          ) +
#         id_cs.initialization_code() +
#         ArduinoDataFunction.load_eeprom(ArduinoDataFunction.sizeof(id),id_cs)+
#         ArduinoDataFunction.if_condition(ArduinoDataFunction.not_equal(cs,id_cs),
#                         id.code_set(ArduinoDataFunction.cast(ArduinoDataTypes.uint64_t,
#                                         ArduinoDataFunction.bitwise_or(
#                                             ArduinoDataFunction.bitwise_left_shift(
#                                                 ArduinoDataFunction.cast(ArduinoDataTypes.uint64_t, ArduinoDataFunction.random()),
#                                                                          48),
#                                             ArduinoDataFunction.bitwise_left_shift(
#                                                 ArduinoDataFunction.cast(ArduinoDataTypes.uint64_t, ArduinoDataFunction.random()),
#                                                 32),
#                                             ArduinoDataFunction.bitwise_left_shift(
#                                                 ArduinoDataFunction.cast(ArduinoDataTypes.uint64_t, ArduinoDataFunction.random()),
#                                                 16),
#                                             ArduinoDataFunction.cast(ArduinoDataTypes.uint64_t, ArduinoDataFunction.random())
#                                         )
#                                                              )
#                                     )+
#                          ArduinoDataFunction.put_eeprom(0,id) +
#                          ArduinoDataFunction.run_function(generate_checksum,
#                                                           ArduinoDataFunction.variable_to_pointer(id),
#                                                           ArduinoDataFunction.sizeof(id),
#                                                           ) +
#                          ArduinoDataFunction.put_eeprom(
#                              ArduinoDataFunction.sizeof(id),
#                              cs
#                          )
#             )
#     )
#
#
#
#     add_command = ArduinoDataFunction(name="add_command")
#     cmd = add_command.add_argument(at.Variable(ArduinoDataTypes.uint8_t,"cmd"))
#     len = add_command.add_argument(at.Variable(ArduinoDataTypes.uint8_t,"len"))
#     func = add_command.add_argument(at.VariableFunction(arguments=((ArduinoDataTypes.uint8_t_array, "data"), (ArduinoDataTypes.uint8_t, "s"))))
#
#     add_command.set_function(
#         ArduinoDataFunction.for_loop_int(MAXFUNCTIONS,
#                                          ArduinoDataFunction.if_condition(
#                                              ArduinoDataFunction.equal(
#                                              ArduinoDataFunction.get_index(cmds,"i"),
#                                              255),
#                                              ArduinoDataFunction.set_index(cmds,"i",cmd)+
#                                              ArduinoDataFunction.set_index(cmd_length,"i",len)+
#                                              ArduinoDataFunction.set_index(cmd_calls,"i",func)+
#                                              ArduinoDataFunction.return_value()
#                                          )
#                                          )
#     )
#
#     endread = ArduinoDataFunction(name="endread",)
#     endread.set_function(
#         commandlength.code_set(0)+
#         serialreadpos.code_set(STARTBYTEPOSITION)
#     )
#
#     get_cmd_index = ArduinoDataFunction(
#         name="get_cmd_index",
#         return_type=ArduinoDataTypes.uint8_t,
#     )
#     cmd = get_cmd_index.add_argument(at.Variable(ArduinoDataTypes.uint8_t))
#     get_cmd_index.set_function(
#         ArduinoDataFunction.for_loop_int(MAXFUNCTIONS,
#                                          ArduinoDataFunction.if_condition(
#                                              ArduinoDataFunction.equal(
#                                              ArduinoDataFunction.get_index(cmds,"i"),
#                                              cmd),
#                                              ArduinoDataFunction.return_value("i")
#                                          )
#         )+ArduinoDataFunction.return_value(255)
#     )
#
#     validate_serial_command = ArduinoDataFunction(name="validate_serial_command")
#     cmd_index = validate_serial_command.add_new_variable(ArduinoDataTypes.uint8_t,value=
#             ArduinoDataFunction.run_function(get_cmd_index,ArduinoDataFunction.get_index(serialread,COMMANDBYTEPOSITION),line_end=False))
#     data = validate_serial_command.add_new_array(arduino_type=ArduinoDataTypes.uint8_t,
#                                                  size=ArduinoDataFunction.get_index(serialread,LENBYTEPOSITION)
#                                                  )
#
#     validate_serial_command.set_function(
#         ArduinoDataFunction.run_function(generate_checksum,
#                                          serialread,
#                                          ArduinoDataFunction.add(
#                                              DATABYTEPOSITION,
#                                              ArduinoDataFunction.get_index(serialread,LENBYTEPOSITION)
#                                          )
#                                          ) +
#         ArduinoDataFunction.if_condition(
#             ArduinoDataFunction.equal(cs,
#             ArduinoDataFunction.add(
#                 ArduinoDataFunction.cast(ArduinoDataTypes.uint16_t,
#                                          ArduinoDataFunction.bitwise_left_shift(
#                                              ArduinoDataFunction.get_index(serialread,ArduinoDataFunction.add(
#                                                  DATABYTEPOSITION,ArduinoDataFunction.get_index(serialread,LENBYTEPOSITION)
#                                              )),
#                                              8)
#                                          ),
#                 ArduinoDataFunction.get_index(serialread,ArduinoDataFunction.add(
#                     DATABYTEPOSITION,ArduinoDataFunction.get_index(serialread,LENBYTEPOSITION),1
#                 )),
#             )),
#             cmd_index.initialization_code()+
#             ArduinoDataFunction.if_condition(ArduinoDataFunction.not_equal(cmd_index,255),
#                                              data.initialization_code()+
#                                              ArduinoDataFunction.memcpy(data,
#                                                                         ArduinoDataFunction.array_to_pointer(serialread,DATABYTEPOSITION),
#                                                                         ArduinoDataFunction.get_index(serialread,LENBYTEPOSITION))+
#                                              ArduinoDataFunction.run_function(ArduinoDataFunction.get_index(cmd_calls,cmd_index),
#                                                                               data,
#                                                                               ArduinoDataFunction.get_index(serialread,LENBYTEPOSITION)
#                                                                               )
#                                              )
#
#
#
#         )
#     )
#
#     readloop = ArduinoDataFunction(
#         name="readloop",
#         function=lambda self: "while(Serial.available() > 0) {{\n"+
#                               "{} = Serial.read();\n".format(self.c.name)+
#                               "{}[{}] = {};\n".format(self.serialread.name,self.serialreadpos.name,self.c.name)+
#                               "if ({} == {}) {{\n".format(self.serialreadpos.name,STARTBYTEPOSITION)+
#                               "if ({} == {}) {{\n".format(self.c.name,int.from_bytes(STARTBYTE, "big"))+
#                               "}} else {{\n"+
#                               "{}();\n".format(self.endread.name)+
#                               "continue;\n"+
#                               "}}\n"+
#                               "}}\n"+
#                               "else {{\n"+
#                               "if ({} == {}) {{\n".format(self.serialreadpos.name,LENBYTEPOSITION)+
#                               "{} = {};\n".format(self.commandlength.name,self.c.name)+
#                               "}} else if ({} - {} > {} + 1 ) {{\n".format(self.serialreadpos.name,self.commandlength.name,DATABYTEPOSITION)+
#                               "{}();\n".format(self.endread.name)+
#                               "continue;\n"+
#                               "}}\n"+
#                               "else if ({} - {} == {} + 1) {{\n".format(self.serialreadpos.name,self.commandlength.name,DATABYTEPOSITION)+
#                               "{}();\n".format(self.validate_serial_command.name)+
#                               "{}();\n".format(self.endread.name)+
#                               "continue;\n"+
#                               "}}\n"+
#                               "}}\n"+
#                               "{}++;\n".format(self.serialreadpos.name)+
#                               "}}\n"
#     )
#
#     readloop.set_function(
#         ArduinoDataFunction.while_loop(
#             ArduinoDataFunction.greater_than(ArduinoDataFunction.serial_available(),0),
#             c.code_set(ArduinoDataFunction.serial_read())+
#             ArduinoDataFunction.set_index(serialread,serialreadpos,c)+
#             ArduinoDataFunction.if_condition(ArduinoDataFunction.equal(serialreadpos,STARTBYTEPOSITION),
#                                              ArduinoDataFunction.if_condition(ArduinoDataFunction.equal(c,int.from_bytes(STARTBYTE, "big")),"")+
#                                              ArduinoDataFunction.else_condition(
#                                                  ArduinoDataFunction.run_function(endread)+
#                                                  ArduinoDataFunction.continue_call()
#                                              )
#                                              )+
#             ArduinoDataFunction.else_condition(
#                 ArduinoDataFunction.if_condition(ArduinoDataFunction.equal(serialreadpos,LENBYTEPOSITION),
#                                                  commandlength.code_set(c)
#                                                  )+
#                 ArduinoDataFunction.elseif_condition(ArduinoDataFunction.greater_than(
#                     ArduinoDataFunction.substract(serialreadpos,commandlength),
#                     ArduinoDataFunction.add(DATABYTEPOSITION,1)
#                 ),
#                                                      ArduinoDataFunction.run_function(endread)+
#                                                      ArduinoDataFunction.continue_call()
#                                                  )+
#
#                 ArduinoDataFunction.elseif_condition(ArduinoDataFunction.equal(
#                     ArduinoDataFunction.substract(serialreadpos,commandlength),
#                     ArduinoDataFunction.add(DATABYTEPOSITION,1)
#                 ),
#                     ArduinoDataFunction.run_function(validate_serial_command)+
#                     ArduinoDataFunction.run_function(endread)+
#                     ArduinoDataFunction.continue_call()
#                 )
#
#             )+
#             ArduinoDataFunction.add_to_variable(serialreadpos,1)
#         )
#     )
#
#
#     setup_functions = ArduinoSetupFunction(ArduinoDataFunction.serial_begin(BAUD)+
#                                  #"Serial.begin(BAUD);\n"EEPROM.get(0, id)
#                                  ArduinoDataFunction.load_eeprom(0,id)+
#                                  ArduinoDataFunction.for_loop_int(int_start=STARTANALOG,limit=ENDANALOG,inner_code=
#                                  ArduinoDataFunction.random_seed(
#                                      ArduinoDataFunction.multiply(
#                                          ArduinoDataFunction.max(1,
#                                             ArduinoDataFunction.analog_read("i")
#                                          ),
#                                          ArduinoDataFunction.random()
#                                      )
#                                  )
#                                                                   )+
#                                 ArduinoDataFunction.run_function(checkUUID)+
#                                 ArduinoDataFunction.for_loop_int(MAXFUNCTIONS,
#                                                                  cmds.code_set("i",255)
#                                                                  )+
#                                 ct.code_set(ArduinoDataFunction.millis())
#                                            )
#
#     def __init__(self, board_instance):
#         super().__init__(board_instance)
#         self.loop_function = ArduinoLoopFunction(
#             ArduinoDataFunction.run_function(self.readloop)+
#             self.ct.code_set(ArduinoDataFunction.millis())+
#             ArduinoDataFunction.if_condition(
#                 ArduinoDataFunction.conditional_and(
#                     ArduinoDataFunction.greater_than(ArduinoDataFunction.substract(self.ct,self.lastdata),board_instance.get_module_var_by_name("data_rate").name),
#                     self.identified
#                 ),
#                 ArduinoDataFunction.run_function("dataloop")+
#                 self.lastdata.code_set(self.ct)
#             )
#         )
#
#     def setup(self):
#         setup = super().setup()
#
#         for portcommand in self.board_instance.port_commands:
#             setup += ArduinoDataFunction.run_function(self.add_command,portcommand.byteid,portcommand.sendlength,"{}_{}".format(portcommand.name,portcommand.byteid))
#
#         return setup
#
#     def dataloop(self):
#         data_loop = super().dataloop()
#
#         for attr, ard_var in self.board_instance.get_arduino_vars().items():
#             if ard_var.is_data_point:
#                 data_loop+=ArduinoDataFunction.run_function(self.write_data,ard_var.name,self.board_instance.get_portcommand_by_name(_GET_PREFIX + ard_var.name).byteid)
#
#         return data_loop
#
#     def global_vars(self):
#         global_vars = super().global_vars()
#
#         for attr, ard_var in self.board_instance.get_arduino_vars().items():
#             if ard_var.is_global_var:
#                 global_vars.append(ArduinoDataGlobalVariable(name=ard_var.name,arduino_type=ard_var.type,value=ard_var.value))
#
#         return global_vars
#
#     def functions(self):
#         functions = super().functions()
#
#         for portcommand in self.board_instance.port_commands:
#             name = "{}_{}".format(portcommand.name,portcommand.byteid)
#             functions.append(ArduinoDataFunction(name=name,return_type=ArduinoDataTypes.void,arguments=[(ArduinoDataTypes.uint8_t_array, "data"), (ArduinoDataTypes.uint8_t, "s")],function= portcommand.arduino_code))
#         return functions


if __name__ == "__main__":
    ins = ArduinoBasicBoard()
    ins.create_ino()
    #print(ins.arduino_code_creator.create_code())
    #ins.create_ino()
