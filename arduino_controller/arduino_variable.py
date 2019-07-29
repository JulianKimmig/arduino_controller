import struct

from ArduinoCodeCreator import arduino_data_types
from ArduinoCodeCreator.arduino import Arduino

from arduino_controller.modul_variable import ModuleVariable, ModuleVarianbleStruct

#
# def calculate_strcut_max_min(struct_fmt):
#     if "?" in struct_fmt:
#         return 0, 1
#     n = 0
#     while 1:
#         try:
#             struct.pack(struct_fmt, 2 ** n)
#             n += 1
#         except:
#             break
#     try:
#         struct.pack(struct_fmt, 2 ** n - 1)
#         i = 1
#     except:
#         i = 0
#         n -= 1
#     maximum = 2 ** n - i
#     n = 0
#     minimum = 0
#     while 1:
#         try:
#             s = struct.pack(struct_fmt, -2 ** n)
#             minimum = -2 ** n
#             n += 1
#         except:
#             break
#
#     STRUCT_SIZES[struct_fmt] = (minimum, maximum)
#
#     return minimum, maximum
#
#
# STRUCT_SIZES = dict()
#
#
#
# arduino_var_to_struc_available = {
#     'bool': ArduinoVarianbleStruct(struct_fmt="?", arduino_setter="{{ardvar_name}}=data[0];",
#                                    arduino_getter='write_data({{ardvar_name}},{BYTEID});',
#                                    html_input='checkbox', python_type=bool),
#     'uint8_t': ArduinoVarianbleStruct(struct_fmt="B", arduino_setter="{{ardvar_name}}=data[0];",
#                                       arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
#     'int8_t': ArduinoVarianbleStruct(struct_fmt="b", arduino_setter="{{ardvar_name}}=data[0];",
#                                      arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
#     'uint16_t': ArduinoVarianbleStruct(struct_fmt="H",
#                                        arduino_setter="uint16_t temp;memcpy(&temp,data,2);{{ardvar_name}}=temp;",
#                                        arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
#     'int16_t': ArduinoVarianbleStruct(struct_fmt="h",
#                                       arduino_setter="int16_t temp;memcpy(&temp,data,2);{{ardvar_name}}=temp;",
#                                       arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
#     'uint32_t': ArduinoVarianbleStruct(struct_fmt="L",
#                                        arduino_setter="uint32_t temp;memcpy(&temp,data,4);{{ardvar_name}}=temp;",
#                                        arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
#     'int32_t': ArduinoVarianbleStruct(struct_fmt="l",
#                                       arduino_setter="int32_t temp;memcpy(&temp,data,4);{{ardvar_name}}=temp;",
#                                       arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
#     'uint64_t': ArduinoVarianbleStruct(struct_fmt="Q",
#                                        arduino_setter="uint64_t temp;memcpy(&temp,data,8);{{ardvar_name}}=temp;",
#                                        arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
#     'int64_t': ArduinoVarianbleStruct(struct_fmt="q",
#                                       arduino_setter="int64_t temp;memcpy(&temp,data,8);{{ardvar_name}}=temp;",
#                                       arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
# }


ARDUINO_VAR_TYPES = {
    getattr(arduino_data_types,attr).python_type:getattr(arduino_data_types,attr)
    for attr in dir(arduino_data_types)
    if isinstance(getattr(arduino_data_types,attr),arduino_data_types.ArduinoDataType)
}

from ArduinoCodeCreator.basic_types import Variable as ACCArdVar, Function
from ArduinoCodeCreator import arduino_data_types as dt


def generate_arduino_setter(ardvar):
    from ArduinoCodeCreator.basic_types import Function
    from arduino_controller.basicboard.board import COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS

    func = Function(return_type=dt.void,arguments=COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS,name="set_{}".format(ardvar))
    #temp = func.add_variable((ardvar.arduino_data_type,"temp"))

    func.add_call(
        Arduino.memcpy(ardvar.to_pointer(),func.arg1,ardvar.type.byte_size),
       # ardvar.set(temp)
    )
    return func

def generate_arduino_getter(ardvar):
    from arduino_controller.basicboard.board import COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS, WRITE_DATA_FUNCTION

    func = Function(return_type=dt.void,arguments=COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS,name="get_{}".format(ardvar))
    func.byte_id=0
    func.add_call(
        WRITE_DATA_FUNCTION(ardvar,lambda **kwargs:str(func.byte_id))
    )
    return func

class ArduinoVariable(ACCArdVar,ModuleVariable):
    def __init__(self,
                 #for ArduinoVariable
                 name, arduino_data_type=arduino_data_types.uint8_t,default=None,

                 # for module_variable

                 html_input=None, save=True,
                 getter=None, setter=None, minimum=None, maximum=None,
                 python_type=None, is_data_point=False, allowed_values=None, is_global_var=True,
                 sendtype=None, receivetype=None, arduino_getter=None, arduino_setter=None, byte_size=None,
                 eeprom=False, changeable=None
                 ):

        ACCArdVar.__init__(self,type = arduino_data_type,value=default,name=name)

        self.structure_list = ARDUINO_VAR_TYPES
        ModuleVariable.__init__(self,name=self.name,python_type=self.type.python_type,

                                html_input=html_input, save=save,
                         getter=getter, setter=setter, default=default, minimum=minimum, maximum=maximum,
                        is_data_point=is_data_point, allowed_values=allowed_values,
                         is_global_var=is_global_var,
                         nullable=False, changeable=changeable if changeable is not None else arduino_setter != False
                         )


        #self.eeprom = eeprom

        #self.receivetype = self.var_structure.struct_fmt if receivetype is None else receivetype
        #self.sendtype = self.var_structure.struct_fmt if sendtype is None else sendtype

        #self.byte_size = self.var_structure.byte_size if byte_size is None else byte_size


        self.arduino_setter = None if arduino_setter is False else (
            generate_arduino_setter(self) if arduino_setter is None else arduino_setter)

        self.arduino_getter = None if arduino_getter is False else (
            generate_arduino_getter(self) if arduino_getter is None else arduino_getter)


      #  self.python_type = arduino_var_to_struc_available.get(
      #      type).python_type if python_type is None else python_type

        #        if eeprom:
        #           self.arduino_setter=self.arduino_setter+""

    @staticmethod
    def default_setter(var, instance, data, send_to_board=True):
        data = super().default_setter(var=var, instance=instance, data=data)

        if var.arduino_setter is not None:
            if send_to_board:
                instance.get_portcommand_by_name("set_" + var.name).sendfunction(data)

    def set_without_sending_to_board(self, instance, data):
        self.setter(var=self, instance=instance, data=data, send_to_board=False)


arduio_variable = ArduinoVariable
