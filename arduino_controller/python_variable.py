import numpy as np

from arduino_controller.modul_variable import ModuleVariable, ModuleVarianbleStruct


class PythonVarianbleStruct(ModuleVarianbleStruct):
    def __init__(
        self,
        minimum=None,
        maximum=None,
        python_type=np.int,
        html_input="number",
        html_attributes=None,
        default_value=0,
    ):
        super().__init__(
            minimum, maximum, python_type, html_input, html_attributes, default_value
        )


python_variable_to_struc_available = {
    np.int: PythonVarianbleStruct(),
    np.float: PythonVarianbleStruct(
        python_type=np.float, html_attributes=dict(step=0.01)
    ),
}


class PythonVariable(ModuleVariable):
    def __init__(
        self,
        name,
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
        is_global_var=True,
        nullable=True,
        changeable=None,
    ):

        if python_variable_struc is not None:
            assert isinstance(
                python_variable_struc, PythonVarianbleStruct
            ), "var_structure not of class PythonVarianbleStruct"

        self.structure_list = python_variable_to_struc_available

        super().__init__(
            name=name,
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
            is_global_var=is_global_var,
            nullable=nullable,
            changeable=changeable,
        )


python_variable = PythonVariable
