import collections
import struct

from arduino_controller.modul_variable import ModuleVariable, ModuleVarianbleStruct


def calculate_strcut_max_min(struct_fmt):
    if "?" in struct_fmt:
        return 0, 1
    n = 0
    while 1:
        try:
            struct.pack(struct_fmt, 2 ** n)
            n += 1
        except:
            break
    try:
        struct.pack(struct_fmt, 2 ** n - 1)
        i = 1
    except:
        i = 0
        n -= 1
    maximum = 2 ** n - i
    n = 0
    minimum = 0
    while 1:
        try:
            s = struct.pack(struct_fmt, -2 ** n)
            minimum = -2 ** n
            n += 1
        except:
            break

    STRUCT_SIZES[struct_fmt] = (minimum, maximum)

    return minimum, maximum


STRUCT_SIZES = dict()


class ArduinoVarianbleStruct(ModuleVarianbleStruct):

    def __init__(self, struct_fmt, arduino_setter, arduino_getter, default_value=0, minimum=None, maximum=None,
                 python_type=int, html_input='number',
                 html_attributes=None,
                 ):
        self.arduino_getter = arduino_getter
        self.arduino_setter = arduino_setter
        self.struct_fmt = struct_fmt
        self.byte_size = struct.calcsize(struct_fmt)
        alc_minimum, calc_maximum = None, None
        if minimum is None or maximum is None:
            calc_minimum, calc_maximum = STRUCT_SIZES.get(struct_fmt, calculate_strcut_max_min(struct_fmt))
        if minimum is None:
            minimum = calc_minimum
        if maximum is None:
            maximum = calc_maximum
        super().__init__(minimum, maximum, python_type, html_input, html_attributes, default_value)


arduino_var_to_struc_available = {
    'bool': ArduinoVarianbleStruct(struct_fmt="?", arduino_setter="{{ardvar_name}}=data[0];",
                                   arduino_getter='write_data({{ardvar_name}},{BYTEID});',
                                   html_input='checkbox', python_type=bool),
    'uint8_t': ArduinoVarianbleStruct(struct_fmt="B", arduino_setter="{{ardvar_name}}=data[0];",
                                      arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
    'int8_t': ArduinoVarianbleStruct(struct_fmt="b", arduino_setter="{{ardvar_name}}=data[0];",
                                     arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
    'uint16_t': ArduinoVarianbleStruct(struct_fmt="H",
                                       arduino_setter="uint16_t temp;memcpy(&temp,data,2);{{ardvar_name}}=temp;",
                                       arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
    'int16_t': ArduinoVarianbleStruct(struct_fmt="h",
                                      arduino_setter="int16_t temp;memcpy(&temp,data,2);{{ardvar_name}}=temp;",
                                      arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
    'uint32_t': ArduinoVarianbleStruct(struct_fmt="L",
                                       arduino_setter="uint32_t temp;memcpy(&temp,data,4);{{ardvar_name}}=temp;",
                                       arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
    'int32_t': ArduinoVarianbleStruct(struct_fmt="l",
                                      arduino_setter="int32_t temp;memcpy(&temp,data,4);{{ardvar_name}}=temp;",
                                      arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
    'uint64_t': ArduinoVarianbleStruct(struct_fmt="Q",
                                       arduino_setter="uint64_t temp;memcpy(&temp,data,8);{{ardvar_name}}=temp;",
                                       arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
    'int64_t': ArduinoVarianbleStruct(struct_fmt="q",
                                      arduino_setter="int64_t temp;memcpy(&temp,data,8);{{ardvar_name}}=temp;",
                                      arduino_getter='write_data({{ardvar_name}},{BYTEID});'),
}


class ArduinoVariable(ModuleVariable):
    def __init__(self, name, type='uint8_t', html_input=None, arduino_var_struc=None, save=True,
                 getter=None, setter=None, default=None, minimum=None, maximum=None,
                 python_type=None, is_data_point=False, allowed_values=None, is_global_var=True,
                 sendtype=None, receivetype=None, arduino_getter=None, arduino_setter=None, byte_size=None,
                 eeprom=False, changeable=None
                 ):

        if arduino_var_struc is not None:
            assert isinstance(arduino_var_struc,
                              ArduinoVarianbleStruct), "var_structure not of class ArduinoVarianbleStruct"

        self.structure_list = arduino_var_to_struc_available
        super().__init__(name=name, type=type, html_input=html_input, var_structure=arduino_var_struc, save=save,
                         getter=getter, setter=setter, default=default, minimum=minimum, maximum=maximum,
                         python_type=python_type, is_data_point=is_data_point, allowed_values=allowed_values,
                         is_global_var=is_global_var,
                         nullable=False, changeable=changeable if changeable is not None else arduino_setter != False
                         )

        self.eeprom = eeprom

        self.receivetype = self.var_structure.struct_fmt if receivetype is None else receivetype
        self.sendtype = self.var_structure.struct_fmt if sendtype is None else sendtype

        self.byte_size = self.var_structure.byte_size if byte_size is None else byte_size

        self.arduino_setter = None if arduino_setter is False else (
            self.var_structure.arduino_setter if arduino_setter is None else arduino_setter)
        if self.arduino_setter is not None:
            self.arduino_setter = self.arduino_setter.replace("{{ardvar_name}}", self.name)

        self.arduino_getter = None if arduino_getter is False else (
            self.var_structure.arduino_getter if arduino_getter is None else arduino_getter)
        if self.arduino_getter is not None:
            self.arduino_getter = self.arduino_getter.replace("{{ardvar_name}}", self.name)

        self.python_type = arduino_var_to_struc_available.get(
            type).python_type if python_type is None else python_type

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
