from ArduinoCodeCreator import arduino_data_types
from ArduinoCodeCreator.arduino import Arduino, Eeprom
from ArduinoCodeCreator.basic_types import Variable as ACCArdVar, Function, ArduinoEnum

from arduino_controller.modul_variable import ModuleVariable


class ArduinoVariable(ACCArdVar, ModuleVariable):
    def __init__(
        self,
        # for ArduinoVariable
        board,
        name,
        arduino_data_type=arduino_data_types.uint8_t,
        default=None,
        # for module_variable
        html_input=None,
        save=True,
        getter=None,
        setter=None,
        minimum=None,
        maximum=None,
        is_data_point=False,
        allowed_values=None,
        is_global_var=True,
        arduino_getter=None,
        arduino_setter=None,
        eeprom=False,
        changeable=None,
        add_to_code=True,
    ):

        ACCArdVar.__init__(self, type=arduino_data_type, value=default, name=name)

        if eeprom:
            save = False

        self.board = board
        self.add_to_code = add_to_code
        if isinstance(allowed_values, ArduinoEnum):
            allowed_values = {
                key: val[1] for key, val in allowed_values.possibilities.items()
            }
        ModuleVariable.__init__(
            self,
            name=self.name,
            python_type=self.type.python_type,
            html_input=html_input,
            save=save,
            getter=getter,
            setter=setter,
            default=default,
            minimum=minimum,
            maximum=maximum,
            is_data_point=is_data_point,
            allowed_values=allowed_values,
            is_global_var=is_global_var,
            nullable=False,
            changeable=changeable
            if changeable is not None
            else arduino_setter != False,
        )

        self.eeprom = eeprom

        from arduino_controller.basicboard.board import (
            COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS,
        )

        self.arduino_setter = (
            None
            if arduino_setter is False
            else Function(
                arguments=COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS,
                name="set_{}".format(self),
                code=self.generate_arduino_setter()
                if arduino_setter is None
                else arduino_setter,
            )
        )
        self.arduino_getter = (
            None
            if arduino_getter is False
            else Function(
                arguments=COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS,
                name="get_{}".format(self),
                code=self.generate_arduino_getter()
                if arduino_getter is None
                else arduino_getter,
            )
        )

    @staticmethod
    def default_setter(var, instance, data, send_to_board=True):
        data = super().default_setter(var=var, instance=instance, data=data)

        if var.arduino_setter is not None:
            if send_to_board:
                instance.get_portcommand_by_name("set_" + var.name).sendfunction(data)

    def set_without_sending_to_board(self, instance, data):
        self.setter(var=self, instance=instance, data=data, send_to_board=False)

    def generate_arduino_setter(self):
        from arduino_controller.basicboard.board import (
            COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS,
        )

        functions = [
            Arduino.memcpy(
                self.to_pointer(),
                COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS[0],
                self.type.byte_size,
            )
        ]
        if self.eeprom:
            functions.append(Eeprom.put(self.board.eeprom_position.get(self), self))
        return functions

    def generate_arduino_getter(self):
        from arduino_controller.basicboard.board import WRITE_DATA_FUNCTION

        return WRITE_DATA_FUNCTION(self, "BYTEID")


class ArduinoVariableTemplate:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def initialize(self, instance, name):
        setattr(instance, name, ArduinoVariable(instance, *self.args, **self.kwargs))


arduio_variable = ArduinoVariableTemplate
