import numpy as np

from arduino_controller.modul_variable import ModuleVariable, ModuleVarianbleStruct, ModuleVariableTemplate


class PythonVariable(ModuleVariable):
    def __init__(
        self,
        name,
            board,
        type=np.float,
        html_input=None,
        python_variable_struc=None,
        save=True,
        getter=None,
        setter=None,
        default=None,
        minimum=None,
        maximum=None,
        is_data_point=False,
        allowed_values=None,
        nullable=True,
        changeable=None,
    ):

        super().__init__(
            name=name,
            board=board,
            html_input=html_input,
            var_structure=python_variable_struc,
            save=save,
            getter=getter,
            setter=setter,
            default=default,
            minimum=minimum,
            maximum=maximum,
            python_type=type,
            is_data_point=is_data_point,
            allowed_values=allowed_values,
            nullable=nullable,
            changeable=changeable,
        )


class PythonVariableTemplate(ModuleVariableTemplate):
    targetclass = PythonVariable
    def __init__(self, name, type=np.float,**kwargs):
        super().__init__(name=name,python_type=type,type=type,**kwargs)

python_variable = PythonVariableTemplate
