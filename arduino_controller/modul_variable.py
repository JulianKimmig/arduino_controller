import numpy as np

import filter_dict


class StrucTypeNotFoundException(Exception):
    pass


class ModuleVarianbleStruct:
    def __init__(
        self,
        minimum=None,
        maximum=None,
        python_type=int,
        html_input="number",
        html_attributes=None,
        default_value=0,
    ):
        if html_attributes is None:
            html_attributes = dict()
        self.value = default_value
        self.html_attributes = html_attributes
        self.html_input = html_input
        self.python_type = python_type
        self.maximum = maximum
        self.minimum = minimum


DEFAULT_STRUCTURES = {
    **{
        nptype: ModuleVarianbleStruct(
            minimum=np.iinfo(nptype).min,
            maximum=np.iinfo(nptype).max,
            python_type=nptype,
            html_input="number",
        )
        for nptype in [
            np.int8,
            np.int16,
            np.int32,
            np.int64,
            np.uint8,
            np.uint16,
            np.uint32,
            np.uint64,
            np.int,
        ]
    },
    **{
        nptype: ModuleVarianbleStruct(python_type=nptype, html_input="number")
        for nptype in [np.double, np.float, np.float32, np.float16, np.float64]
    },
    bool: ModuleVarianbleStruct(python_type=bool, html_input="checkbox"),
}


class ModuleVariable:
    def __init__(
        self,
        name,
        python_type,
        board,
        html_input=None,
        var_structure=None,
        save=None,
        getter=None,
        setter=None,
        default=None,
        minimum=None,
        maximum=None,
        is_data_point=None,
        allowed_values=None,
        nullable=None,
        changeable=None,
        html_attributes=None,
    ):

        if save is None:
            save = True
        if is_data_point is None:
            is_data_point = False
        if nullable is None:
            nullable = False

        if html_attributes is None:
            html_attributes = {}
        self.html_attributes = html_attributes
        self.board = board
        self.name = str(name)
        self.python_type = python_type
        self.save = save
        self.is_data_point = is_data_point
        self.html_input = html_input
        self.allowed_values = allowed_values
        self.nullable = nullable
        self.attributes = {}
        self.return_self = True

        if not hasattr(self, "structure_list"):
            self.structure_list = DEFAULT_STRUCTURES

        if var_structure is not None:
            assert isinstance(
                var_structure, ModuleVarianbleStruct
            ), "var_structure not of class ModuleVarianbleStruct"
            self.var_structure = var_structure
        else:
            self.var_structure = self.structure_list.get(python_type)
            if self.var_structure is None:
                self.var_structure = self.structure_list.get(str(python_type))
                if self.var_structure is None:
                    raise StrucTypeNotFoundException(
                        "Struct equivalent not found for {}({}) please define manually".format(
                            name, python_type
                        )
                    )
        self.default = 0 if default is None else default

        self.maximum = self.var_structure.maximum if maximum is None else maximum
        self.minimum = self.var_structure.minimum if minimum is None else minimum

        self.value = self.default
        self.setter = (
            None
            if setter is False
            else (self.default_setter if setter is None else setter)
        )
        self.getter = (
            None
            if setter is False
            else (self.default_getter if getter is None else getter)
        )
        self.changeable = (
            changeable
            if changeable is not None
            else (False if self.setter is None else True)
        )

    def default_getter(self, instance):
        return self.value

    def default_setter(self, var, instance, data):
        if data is None and not var.nullable:
            return
        if data is not None:
            data = var.python_type(data)

        # print(self.name,instance,getattr(instance,self.name))
        if var.allowed_values is not None:
            # if value is not allowed by allowed_values
            if data not in var.allowed_values:
                # select nearest allowed value
                data = min(var.allowed_values, key=lambda x: abs(x - data))

        if data is not None:
            if var.minimum is not None:
                if data < var.minimum:
                    data = var.minimum
            if var.maximum is not None:
                if data > var.maximum:
                    data = var.maximum

        var.value = data
        if var.is_data_point:
            var.send_data_point(data)
        return data

    def send_data_point(self, data):
        self.board.data_point(self.name, data)

    def set_value(self, instance, value):
        self.setter(var=self, instance=instance, data=value)

    def get_value(self, instance, owner):
        if self.return_self or self.getter is None:
            return self
        return self.getter(instance)

    def modulvar_getter_modification(self, newfunc):
        pregetter = self.getter

        def newgetter(*args, **kwargs):
            return newfunc(pregetter(*args, **kwargs))

        self.getter = newgetter

    def modulvar_setter_modification(self, newfunc):
        presetter = self.setter

        def newsetter(data=0, *args, **kwargs):
            data = newfunc(self.python_type(data))
            return presetter(data=data, *args, **kwargs)

        self.setter = newsetter

    def data_point_modification(self, newfunc):
        presetter = self.send_data_point

        def newsetter(data):
            data = newfunc(self.python_type(data))
            return presetter(data=data)

        self.send_data_point = newsetter

    def _generate_html_input(self):
        if self.changeable:
            if self.allowed_values is not None:
                html_input = '<select name="{}" {}>{}</select>'.format(
                    self.name,
                    " ".join(
                        [
                            str(key) + '="' + str(val) + '"'
                            for key, val in {
                                **self.var_structure.html_attributes,
                                **self.html_attributes,
                            }.items()
                        ]
                    ),
                    "".join(
                        [
                            '<option value="{}" {}>{}</option>'.format(
                                allowed_value,
                                " selected" if allowed_value == self.value else "",
                                self.allowed_values[allowed_value]
                                if isinstance(self.allowed_values, dict)
                                else allowed_value,
                            )
                            for allowed_value in self.allowed_values
                        ]
                    ),
                )
                # + str(
                #                     self.allowed_values[allowed] if isinstance(self.allowed_values, dict) else allowed) +

            #    html_input = '<select name="' + self.name + '" ' + ' '.join(
            #        [str(key) + '="' + str(val) + '"' for key, val in self.var_structure.html_attributes.items()]) + ' >' + \
            #                 ''.join(['<option value="' + str(allowed) + '" ' + str(
            #                     " selected" if allowed == self.value else "") + '>' + str(
            #                     self.allowed_values[allowed] if isinstance(self.allowed_values,
            #                                                                dict) else allowed) + '</option>' for
            #                          allowed in self.allowed_values]) + \
            #                  '</select>'
            else:
                html_input = (
                    '<input type="'
                    + self.var_structure.html_input
                    + '" min="'
                    + str(self.minimum)
                    + '" max="'
                    + str(self.maximum)
                    + '" name="modul_variable_input_'
                    + self.name
                    + '" value="{{value}}" '
                    + " ".join(
                        [
                            str(key) + '="' + str(val) + '"'
                            for key, val in {
                                **self.var_structure.html_attributes,
                                **self.html_attributes,
                            }.items()
                        ]
                    )
                    + (" readonly" if self.setter is None else "")
                    + ">"
                )
        else:
            html_input = ""

        if self.is_data_point:
            html_input += '<input type={} name="data_point_{}" value="{{value}}" readonly disabled>'.format(
                self.var_structure.html_input, self.name
            )

        if self.allowed_values is None:
            self.attributes["html_input"] = html_input

        return html_input

    def get_html_input(self):
        return self.attributes.get("html_input", self._generate_html_input())

    def set_html_input(self, html_input):
        if html_input is not None:
            self.attributes["html_input"] = html_input

    html_input = property(get_html_input, set_html_input)


class ModuleVariableTemplate:
    targetclass = ModuleVariable

    def __init__(self, name, python_type, **kwargs):
        for key, val in kwargs.items():
            setattr(self, key, val)
        self.name = name
        self.python_type = python_type
        self.board = None

    def initialize(self, instance, name):
        self.board = instance
        new_var = filter_dict.call_method(self.targetclass, kwargs=self.__dict__)
        new_var.name = name
        setattr(instance, name, new_var)
        return new_var
