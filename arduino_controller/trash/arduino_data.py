import inspect
import random
import string
import time


class ArduinoDataTypes:
    void = "void"
    bool = "bool"
    boolean = bool
    uint8_t = "uint8_t"
    uint16_t = "uint16_t"
    uint32_t = "uint32_t"
    uint64_t = "uint64_t"
    uint8_t_array = uint8_t + "*"

    double = "double"

class ArduinoDataAbstract():
    def __init__(self, name):
        self.name = name
        self._abstruse_name = "v" + ''.join([random.choice(string.ascii_letters + string.digits) for n in range(24)]) + str(
            time.time()).replace(".", "")[:5]

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


class ArduinoVariable(ArduinoDataAbstract):
    def __init__(self, arduino_type, name=None, value=None):
        if name is None:
            name = "v" + ''.join([random.choice(string.ascii_letters + string.digits) for n in range(24)]) + str(
                time.time()).replace(".", "")[:5]
        super().__init__(name)
        self.arduino_type = arduino_type
        self.value = value

    def initialization_code(self,line_end=True):
        return "{} {}".format(self.arduino_type, self.name) + (
            "=" + str(self.value) if self.value is not None else "") +(";\n" if line_end else "")

    def code_set(self, new_val):
        return "{}={};\n".format(self.name, new_val)


class ArduinoDataDefinition(ArduinoDataAbstract):
    def __init__(self, name, value):
        super().__init__(name=name)
        self.value = value

    def define_code(self,arduino_data_instance):
        value = self.value
        try:
            value = self.value(arduino_data_instance)
        except TypeError:
            pass
        return ("#define {} {}\n").format(self.name,value)

class ArduinoArray(ArduinoVariable):
    def __init__(self, arduino_type, size, name):
        super().__init__(arduino_type=arduino_type, name=name, value=None)
        self.size = size

    def initialization_code(self):
        return "{} {}[{}];\n".format(self.arduino_type, self.name, self.size)

    def code_set(self, index, new_val):
        return "{}[{}]={};\n".format(self.name, index, new_val)

class ArduinoVariableFunction(ArduinoVariable):
    def __init__(self, return_type=ArduinoDataTypes.void, name=None, arguments=None):
        super().__init__(arduino_type=return_type, name=name)
        if arguments is None:
            arguments = []
        self.arguments = arguments

    def initialization_code(self,line_end=True):
        return "{} (*{})({})".format(self.arduino_type, self.name, ",".join(["{} {}".format(arg[0], arg[1]) for arg in self.arguments]))+(";\n" if line_end else "")


class ArduinoDataGlobalVariable(ArduinoVariable):
    def __init__(self, name, arduino_type, value=None):
        super().__init__(arduino_type=arduino_type, name=name, value=value)

 #   def to_dict_entry(self, arduinodata):
 #       return self.generate_value(self.name, arduinodata), [self.generate_value(self.arduino_type, arduinodata),
 #                                                            self.generate_value(self.value, arduinodata)]


class ArduinoDataGlobalVariableArray(ArduinoArray):
    def __init__(self, name, arduino_type, size):
        super().__init__(name=name, arduino_type=arduino_type,size=size)


class ArduinoDataGlobalVariableFunctionArray(ArduinoDataGlobalVariableArray):
    def __init__(self, name, return_type, size, arguments=None):
        super().__init__(name=name, arduino_type=return_type, size=size)
        if arguments is None:
            arguments = []
        self.arguments = arguments

    def initialization_code(self,line_end=True):
        return "{} (*{}[{}])({})".format(self.arduino_type, self.name,self.size, ",".join(["{} {}".format(arg[0], arg[1]) for arg in self.arguments]))+(";\n" if line_end else "")




class ArduinoDataInclude(ArduinoDataAbstract):
    def __init__(self, name, relative=False):
        super().__init__(name)
        self.relative = relative

    def include_code(self):
        return ('#include "{}"\n' if self.relative else '#include <{}>\n').format(self.name)

class ArduinoDataFunction(ArduinoDataAbstract):
    def __init__(self, name, return_type="void", arguments=None, function=""):
        super().__init__(name)
        if arguments is None:
            arguments = []
        self.arguments = []
        self.variables = {}
        for argument in arguments:
            if isinstance(argument, ArduinoVariable):
                self.add_argument(argument)
            else:
                if isinstance(argument, str):
                    self.add_argument(ArduinoVariable(argument))
                else:
                    self.add_argument(ArduinoVariable(argument[0], argument[1]))

        self.return_type = return_type
        self.function = function

    def add_argument(self, arduino_variable):
        self.arguments.append(arduino_variable)
        self.add_variable(arduino_variable)
        return arduino_variable

    def set_function(self, function):
        self.function = function

    def add_variable(self, arduino_variable):
        self.variables[arduino_variable.name] = arduino_variable

    def add_new_variable(self, arduino_type, name=None, value=None):
        var = ArduinoVariable(arduino_type, name, value)
        self.add_variable(var)
        return var

    def get_variable(self, name):
        return self.variables.get(name)

    def add_new_array(self, arduino_type, size, name=None):
        var = ArduinoArray(arduino_type, size, name)
        self.add_variable(var)
        return var

    @staticmethod
    def for_loop_int(limit, inner_code, int_start=0, int_name="i"):
        return "for(int {}={};{}<{};{}++){{\n{}}}\n".format(int_name, int_start, int_name, limit, int_name,
                                                              inner_code)

    @staticmethod
    def return_value(value=""):
        return "return {};\n".format(value)

    @staticmethod
    def mod(val, div):
        return "({} % {})".format(val, div)

    @staticmethod
    def add(*args):
        return "(" + ' + '.join([str(arg) for arg in args]) + ")"

    @staticmethod
    def multiply(*args):
        return "(" + ' * '.join([str(arg) for arg in args]) + ")"

    @staticmethod
    def divide(value,divider):
        return "({}/{})".format(value,divider)

    @staticmethod
    def substract(from_this,substract_this):
        return "({} - {})".format(from_this,substract_this)

    @staticmethod
    def min(value1,value2):
        return "min({},{})".format(value1,value2)

    @staticmethod
    def max(value1,value2):
        return "max({},{})".format(value1,value2)

    @staticmethod
    def sin(arg):
        return "sin({})".format(arg)

    @staticmethod
    def map(x, in_min, in_max, out_min, out_max):
        return "map({}, {}, {}, {}, {})".format(x,in_min, in_max, out_min, out_max)

    @staticmethod
    def PI():
        return "PI"

    @staticmethod
    def get_index(array_variable, index):
        return "{}[{}]".format(array_variable, index)

    @staticmethod
    def set_index(array_variable, index, value):
        return "{}[{}] = {};\n".format(array_variable, index, value)

    @staticmethod
    def run_function(function_name, *args, line_end=True):
        return "{}({})".format(function_name, ', '.join([str(arg) for arg in args])) + (";\n" if line_end else "")

    @staticmethod
    def serial_write(buf, len=0):
        if len == 0:
            return "Serial.write({});\n".format(buf)
        else:
            return "Serial.write({}, {});\n".format(buf, len)

    @staticmethod
    def load_eeprom(position, target_variable):
        return "EEPROM.get({}, {});\n".format(position, target_variable)

    @staticmethod
    def put_eeprom(position, source_variable):
        return "EEPROM.put({}, {});\n".format(position, source_variable)

    @staticmethod
    def set_variable(variable,value):
        return "{} = {};\n".format(variable,value)

    @staticmethod
    def variable_to_pointer(variable):
        return "(uint8_t*)&{}".format(variable)

    @staticmethod
    def sizeof(variable):
        return "sizeof({})".format(variable)

    @staticmethod
    def if_condition(condition, func):
        return "if({}){{\n{}}}\n".format(condition, func)
    @staticmethod
    def elseif_condition(condition, func):
        return "else if({}){{\n{}}}\n".format(condition, func)
    @staticmethod
    def else_condition(function):
        return "else {{\n{}}}\n".format(function)

    @staticmethod
    def while_loop(condition, function):
        return "while({}){{\n{}}}\n".format(condition,function)

    @staticmethod
    def greater_than(greater, lesser):
        return "{} > {}".format(greater,lesser)

    @staticmethod
    def greater_equal_than(greater, lesser):
        return "{} >= {}".format(greater,lesser)

    @staticmethod
    def lesser_than(lesser,greater):
        return ArduinoDataFunction.greater_than(greater,lesser)

    @staticmethod
    def lesser_equal_than(lesser,greater):
        return ArduinoDataFunction.greater_equal_than(greater,lesser)

    @staticmethod
    def equal(param1,param2):
        return "{} == {}".format(param1,param2)

    @staticmethod
    def not_equal(param1,param2):
        return "{} != {}".format(param1,param2)

    @staticmethod
    def conditional_and(param1,param2):
        return "({} && {})".format(param1,param2)


    @staticmethod
    def cast(arduino_type, value):
        return "(({})({}))".format(arduino_type,value)

    @staticmethod
    def bitwise_or(*args):
        return "|".join([arg for arg in args])

    @staticmethod
    def bitwise_left_shift(value, number):
        return "(({}) << {})".format(value,number)

    @staticmethod
    def random():
        return "random()"

    @staticmethod
    def memcpy(destination, source, num):
        return  "memcpy({},{},{});\n".format(destination,source,num)

    @staticmethod
    def array_to_pointer(array,index):
        return "&{}[{}]".format(array,index)

    @staticmethod
    def serial_read():
        return "Serial.read()"

    @staticmethod
    def serial_available():
        return "Serial.available()"

    @staticmethod
    def serial_begin(baud):
        return "Serial.begin({});\n".format(baud)

    @staticmethod
    def analog_read(index):
        return "analogRead({})".format(index)

    @staticmethod
    def analog_write(pin,value):
        return "analogWrite({},{});\n".format(pin,value)

    PIN_MODE_OUT="OUTPUT"
    @staticmethod
    def pin_mode(pin,value):
        return "analogWrite({},{});\n".format(pin,value)

    @staticmethod
    def millis():
        return "millis()"

    @staticmethod
    def continue_call():
        return "continue;\n"

    @staticmethod
    def add_to_variable(variable, number):
        if number == 1:
           return "{}++;\n".format(variable)
        if number == -1:
            return "{}--;\n".format(variable)
        if number > 0:
            return "{}+={};\n".format(variable,number)
        if number < 0:
            return "{}-={};\n".format(variable,abs(number))

    @staticmethod
    def random_seed(value):
        return "randomSeed({});\n".format(value)


class ArduinoSetupFunction:
    def __init__(self,function):
        self.function=function

class ArduinoLoopFunction:
    def __init__(self,function):
        self.function=function

class ArduinoDataLoopFunction:
    def __init__(self,function):
        self.function=function

class ArduinoData():
    def __init__(self, board_instance):
        self.board_instance = board_instance

    def definitions(self):
        definitions = {}
        classes = inspect.getmro(self.__class__)
        for cls in reversed(classes):
            for attr, mod_var in cls.__dict__.items():
                if isinstance(mod_var, ArduinoDataDefinition):
                    definitions[mod_var.name]= mod_var.define_code(self)

        for attr, mod_var in self.__dict__.items():
            if isinstance(mod_var, ArduinoDataDefinition):
                definitions[mod_var.name]= mod_var.define_code(self)

        return definitions

    def global_vars(self):
        global_vars = []

        classes = inspect.getmro(self.__class__)
        for cls in reversed(classes):
            for attr, mod_var in cls.__dict__.items():
                if isinstance(mod_var, ArduinoDataGlobalVariable) or isinstance(mod_var, ArduinoDataGlobalVariableArray):
                    global_vars.append(mod_var)

        for attr, mod_var in self.__dict__.items():
            if isinstance(mod_var, ArduinoDataGlobalVariable) or isinstance(mod_var, ArduinoDataGlobalVariableArray):
                global_vars.append(mod_var)

        return global_vars

    def includes(self):
        includes = []
        classes = inspect.getmro(self.__class__)
        for cls in reversed(classes):
            for attr, mod_var in cls.__dict__.items():
                if isinstance(mod_var, ArduinoDataInclude):
                    includes.append(mod_var)
        for attr, mod_var in self.__dict__.items():
            if isinstance(mod_var, ArduinoDataInclude):
                includes.append(mod_var)
        return includes

    def functions(self):
        functions = []
        classes = inspect.getmro(self.__class__)
        for cls in reversed(classes):
            for attr, mod_var in cls.__dict__.items():
                if isinstance(mod_var, ArduinoDataFunction):
                    functions.append(mod_var)

        for attr, mod_var in self.__dict__.items():
            if isinstance(mod_var, ArduinoDataFunction):
                functions.append(mod_var)

        return functions

    def setup(self):
        functions = []
        classes = inspect.getmro(self.__class__)
        for cls in reversed(classes):
            for attr, mod_var in cls.__dict__.items():
                if isinstance(mod_var, ArduinoSetupFunction):
                    functions.append(mod_var.function)

        for attr, mod_var in self.__dict__.items():
            if isinstance(mod_var, ArduinoSetupFunction):
                functions.append(mod_var.function)

        return ''.join(functions)

    def loop(self):
        functions = []
        classes = inspect.getmro(self.__class__)
        for cls in reversed(classes):
            for attr, mod_var in cls.__dict__.items():
                if isinstance(mod_var, ArduinoLoopFunction):
                    functions.append(mod_var.function)

        for attr, mod_var in self.__dict__.items():
            if isinstance(mod_var, ArduinoLoopFunction):
                functions.append(mod_var.function)

        return ''.join(functions)

    def dataloop(self):
        functions = []
        classes = inspect.getmro(self.__class__)
        for cls in reversed(classes):
            for attr, mod_var in cls.__dict__.items():
                if isinstance(mod_var, ArduinoDataLoopFunction):
                    functions.append(mod_var.function)

        for attr, mod_var in self.__dict__.items():
            if isinstance(mod_var, ArduinoDataLoopFunction):
                functions.append(mod_var.function)

        return ''.join(functions)

    def create_code(self):
        return {
            "definitions": self.definitions(),
            "global_vars": self.global_vars(),
            "includes": self.includes(),
            "functions": self.functions(),
            "setup": self.setup(),
            "loop": self.loop(),
            "dataloop": self.dataloop(),
        }
