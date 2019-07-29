class InoCreator:
    def __init__(self, board):
        self.creatorclasses = []
        self.board = board
        self.data = dict(
            definitions={},
            global_vars={},
            includes=set([]),
            functions={},
            setup="",
            loop="",
            dataloop="",
        )

    def add_code_dict(
        self,
        definitions=None,
        global_vars=None,
        includes=None,
        functions=None,
        setup=None,
        loop=None,
        dataloop=None,
    ):
        if definitions is not None:
            self.add_definitions(definitions)
        if global_vars is not None:
            self.add_global_vars(global_vars)
        if includes is not None:
            self.add_includes(includes)
        if functions is not None:
            self.add_functions(functions)
        if setup is not None:
            self.add_setup(setup)
        if loop is not None:
            self.add_loop(loop)
        if dataloop is not None:
            self.add_dataloop(dataloop)

    def add_definitions(self, definitions):
        for name,value in definitions.items():
            self.add_definition(name,value)

    def add_definition(self, definition_name,definition_value):
        if definition_name in self.data["definitions"]:
            raise ValueError(definition_name + " already defined")
        self.data["definitions"][definition_name] = definition_value

    def add_global_vars(self, vars):
        for var in vars:
            self.add_global_var(var)

    def add_global_var(self, var):
        if var.name in self.data["global_vars"]:
            raise ValueError(var.name + " already defined")
        self.data["global_vars"][var.name] = var

    def add_includes(self, includes):
        self.data["includes"].update(includes)

    def add_functions(self, functions):
        for function in functions:
            self.add_function(function)

    def add_function(self,function):
        if function.name in self.data["functions"]:
            raise ValueError(function + " already defined")
        self.data["functions"][function] = function

    def add_setup(self, setup):
        self.data["setup"] = self.data["setup"] + setup

    def add_loop(self, loop):
        self.data["loop"] = self.data["loop"] + loop

    def add_dataloop(self, dataloop):
        self.data["dataloop"] = self.data["dataloop"] + dataloop

    def create(self):
        for creatorclass in self.creatorclasses:
            creatorclass_instance = creatorclass(self.board)
            self.add_code_dict(**creatorclass_instance.create_code())

        text = ""

        for name, definition in self.data["definitions"].items():
            text += definition
        text += "\n"

        for inc in self.data["includes"]:
            text += inc.include_code()
        text += "\n"

        for name, var in self.data["global_vars"].items():
            text += var.initialization_code()
        text += "\n"

        for name, func in self.data["functions"].items():
            text += "{} {}({}){{\n{}\n}}\n".format(func.return_type,name,
                                                   ", ".join([arg.initialization_code(line_end=False) for arg in func.arguments]),
                                                   func.function)
        text += "\n"

        text += "\nvoid dataloop(){\n" + self.data["dataloop"] + "\n}\n"
        text += "\nvoid loop(){\n" + self.data["loop"] + "\n}\n"
        text += "\nvoid setup(){\n" + self.data["setup"] + "\n}\n"
        return text

    def add_creator(self, creatorclass):
        self.creatorclasses.append(creatorclass)
