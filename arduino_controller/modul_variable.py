import collections


class StrucTypeNotFoundException(Exception): pass


class ModuleVarianbleStruct:
    def __init__(self, minimum=None, maximum=None, python_type=int, html_input='number',
                 html_attributes=None, default_value=0):
        if html_attributes is None:
            html_attributes = dict()
        self.value = default_value
        self.html_attributes = html_attributes
        self.html_input = html_input
        self.python_type = python_type
        self.maximum = maximum
        self.minimum = minimum


class ModuleVariable():
    def __init__(self, name, python_type, html_input=None, var_structure=None, save=True,
                 getter=None, setter=None, default=None, minimum=None, maximum=None,
                 is_data_point=False, allowed_values=None, is_global_var=True,
                 nullable=False,changeable=None
                 ):

        self.name = str(name)
        self.python_type = python_type
        self.save = save
        self.is_data_point = is_data_point
        self.html_input = html_input
        self.allowed_values = allowed_values
        self.is_global_var = is_global_var
        self.nullable = nullable
        self.attributes = {}

        if not hasattr(self, "structure_list"):
            self.structure_list = {}

        if var_structure is not None:
            assert isinstance(var_structure,ModuleVarianbleStruct), "var_structure not of class ModuleVarianbleStruct"
            self.var_structure = var_structure
        else:
            self.var_structure = self.structure_list.get(python_type)
            if self.var_structure is None:
                self.var_structure = self.structure_list.get(str(python_type))
                if self.var_structure is None:
                    raise StrucTypeNotFoundException(
                        'Struct equivalent not found for {}({}) please define manually'.format(name,python_type))
        self.default = 0 if default is None else default

        self.maximum = self.var_structure.maximum if maximum is None else maximum
        self.minimum = self.var_structure.minimum if minimum is None else minimum

        self.value = self.default
        self.setter = None if setter is False else (self.default_setter if setter is None else setter)
        self.getter = None if setter is False else (self.default_getter if getter is None else getter)
        self.changeable = changeable if changeable is not None else (False if self.setter is None else True)

    def default_getter(self, instance):
        return self.value

    @staticmethod
    def default_setter(var, instance, data):
        if data is None and not var.nullable: return
        if data is not None:
            data = var.python_type(data)

        if var.allowed_values is not None:
            # if value is not allowed by allowed_values
            if data not in var.allowed_values:
                # select nearest allowed value
                data = min(var.allowed_values, key=lambda x: abs(x - data))

        if data is not None:
            if var.minimum is not None:
                if data < var.minimum: data = var.minimum
            if var.maximum is not None:
                if data > var.maximum: data = var.maximum

        var.value = data
        if var.is_data_point:
            instance.data_point(var.name, data)
        return data

    def __set__(self, instance, value):
        self.setter(var=self, instance=instance, data=value)

    def __get__(self, instance, owner):
        return self.getter(instance)

    def _generate_html_input(self):
        if self.changeable:
            if self.allowed_values is not None:
                html_input = '<select name="' + self.name + '" ' + ' '.join(
                    [str(key) + '="' + str(val) + '"' for key, val in self.var_structure.html_attributes.items()]) + ' >' + \
                             ''.join(['<option value="' + str(allowed) + '" ' + str(
                                 " selected" if allowed == self.value else "") + '>' + str(
                                 self.allowed_values[allowed] if isinstance(self.allowed_values,
                                                                            dict) else allowed) + '</option>' for
                                      allowed in self.allowed_values]) + \
                             '</select>'
            else:
                html_input = '<input type="' + self.var_structure.html_input + '" min="' + str(self.minimum) + '" max="' + str(
                    self.maximum) + '" name="modul_variable_input_' + self.name + '" value="{{value}}" ' + ' '.join(
                    [str(key) + '="' + str(val) + '"' for key, val in self.var_structure.html_attributes.items()]) + (
                                 ' readonly' if self.setter is None else '') + '>'
        else:
            html_input = ""

        if self.is_data_point:
            html_input += (
                    '<input type=' + self.var_structure.html_input + ' name="data_point_' + self.name + '" value="{{value}}">').replace(
                ">", ' readonly>')

        if self.allowed_values is None:
            self.attributes["html_input"] = html_input

        return html_input

    def get_html_input(self):
        return self.attributes.get("html_input", self._generate_html_input())

    def set_html_input(self, html_input):
        if html_input is not None:
            self.attributes["html_input"] = html_input

    html_input = property(get_html_input, set_html_input)
