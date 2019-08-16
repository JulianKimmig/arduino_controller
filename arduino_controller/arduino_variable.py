import filter_dict
from ArduinoCodeCreator import arduino_data_types
from ArduinoCodeCreator.arduino import Arduino, Eeprom
from ArduinoCodeCreator.basic_types import Variable as ACCArdVar, Function, ArduinoEnum

from arduino_controller.modul_variable import ModuleVariable, ModuleVariableTemplate


class ArduinoVariable(ACCArdVar, ModuleVariable):
    def __init__(
            self,
            # for ArduinoVariable
            board,
            name,
            arduino_data_type=None,
            default=None,
            # for module_variable
            html_input=None,
            save=None,
            getter=None,
            setter=None,
            minimum=None,
            maximum=None,
            is_data_point=None,
            allowed_values=None,
            arduino_getter=None,
            arduino_setter=None,
            eeprom=None,
            changeable=None,
            add_to_code=None,
            html_attributes=None,
    ):

        #defaults
        if arduino_data_type is None: arduino_data_type=arduino_data_types.uint8_t
        if save is None: save=True
        if is_data_point is None: is_data_point=False
        if eeprom is None: eeprom=False
        if add_to_code is None: add_to_code=True

        ACCArdVar.__init__(self, type=arduino_data_type, value=default, name=name)

        # self.add_to_code = add_to_code
        if is_data_point and setter is False:
            setter=None
            changeable = False
        if eeprom:
            save = False

        self.add_to_code = add_to_code
        if isinstance(allowed_values, ArduinoEnum):
            allowed_values = {
                key: val[1] for key, val in allowed_values.possibilities.items()
            }
        ModuleVariable.__init__(
            self,
            name=self.name,
            python_type=self.type.python_type,
            board=board,
            html_input=html_input,
            save=save,
            getter=getter,
            setter=setter,
            default=default,
            minimum=minimum,
            maximum=maximum,
            is_data_point=is_data_point,
            allowed_values=allowed_values,
            nullable=False,
            changeable=changeable
            if changeable is not None
            else arduino_setter != False,
            html_attributes=html_attributes,
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
            else self.generate_arduino_getter(arduino_getter)
        )

    def modulvar_getter_modification(self, newfunc):
        pregetter = self.getter

        def newgetter(*args, **kwargs):
            return newfunc(pregetter(*args, **kwargs))

        self.getter = newgetter

    def modulvar_setter_modification(self, newfunc):
        presetter = self.setter

        def newsetter(data=0, send_to_board=True, *args, **kwargs):
            if send_to_board:
                data = newfunc(self.python_type(data))
            return presetter(data=data, *args, **kwargs)

        self.setter = newsetter

    @staticmethod
    def default_setter(var, instance, data, send_to_board=True):
        data = super().default_setter(var=var, instance=instance, data=data)
        if var.arduino_setter is not None:
            if send_to_board:
                var.board.get_portcommand_by_name("set_" + var.name).sendfunction(data)

    def set_without_sending_to_board(self, instance, data):
        self.setter(var=self, instance=instance, data=data, send_to_board=False)

    def generate_arduino_setter(self):
        from arduino_controller.basicboard.board import (
            COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS,
        )

        functions = []
        if self.add_to_code:
            functions.append(
                Arduino.memcpy(
                    self.to_pointer(),
                    COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS[0],
                    self.type.byte_size,
                )
            )
        if self.eeprom:
            functions.append(Eeprom.put(self.board.eeprom_position.get(self), self))
        return functions

    def generate_arduino_getter(self, arduino_getter):
        from arduino_controller.basicboard.board import WRITE_DATA_FUNCTION, COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS
        f = Function(
            arguments=COMMAND_FUNCTION_COMMUNICATION_ARGUMENTS,
            name="get_{}".format(self),
            code=()
            if arduino_getter is None
            else arduino_getter,
        )
        if arduino_getter is None:
            if self.add_to_code:
                f.add_call(WRITE_DATA_FUNCTION(self, self.board.byte_ids.get(f)))
        return f


class ArduinoVariableTemplate(ModuleVariableTemplate):
    targetclass = ArduinoVariable
    def __init__(self, name, arduino_data_type=arduino_data_types.uint8_t, **kwargs):
        super().__init__(name=name, python_type=arduino_data_type.python_type,arduino_data_type=arduino_data_type,**kwargs)


arduio_variable = ArduinoVariableTemplate
