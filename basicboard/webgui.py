type_form_elements = {
    "int+": '<input class="form-control" name="%s" type="number" min="1" value="%s"/>',
    "int": '<input class="form-control" name="%s" type="number" value="%s"/>',
    "int+0": '<input class="form-control" name="%s" type="number" min="0" value="%s"/>',
    "double+": '<input class="form-control" name="%s" type="number" min="0.01" step="0.01" value="%s"/>',
    "double": '<input class="form-control" name="%s" type="number" step="0.1" value="%s"/>',
    "double+0": '<input class="form-control" name="%s" type="number" min="0.00" step="0.01" value="%s"/>',
    "string": '<input class="form-control" name="%s" type="text" value="%s"/>',
    "bool": '<input name="%s" type="checkbox" value="%s"/>',
}


def get_module_class(self):
    return None


def get_form_element(self, attribute, type, name):
    ele = type_form_elements.get(type.split("_")[0], type_form_elements["string"]) % (
        name,
        str(attribute),
    )
    if "_" in type:
        for mergedattribute in type.split("_")[1:]:
            attr = mergedattribute.split("=")
            if len(attr)>1:
                ele = ele.replace("/>", attr[0]+"=\""+attr[1]+"\" />")
            else:
                ele = ele.replace("/>", attr[0]+" />")

    if type == "bool" or type == "boolean":
        ele = ele.split('value="')[0] + (" checked />" if attribute else " />")

    if name in self.static_attributes:
        ele = ele.replace("/>", " readonly />")
    return ele


def get_form_elements(self):
    eles = []
    data = self.save()
    for attribute, type in self.save_attributes.items():
        eleattribute = data[attribute]
        if isinstance(eleattribute, dict):
            s = '<div class="form-group">'
            for subele, value in eleattribute.items():
                s += (
                    '<label for="'
                    + attribute
                    + "_"
                    + subele
                    + '">'
                    + subele.replace("/([A-Z])/g", " $1").capitalize().replace("_", " ")
                    + ":</label>"
                )
                s += get_form_element(self, value, type, attribute + "_" + subele)
            s += "</div>"
            eles.append(s)
        elif isinstance(eleattribute, list):
            s = '<div class="form-group">'
            for i in range(len(eleattribute)):
                s += (
                    '<label for="'
                    + attribute
                    + "_"
                    + str(i)
                    + '">'
                    + attribute.replace("/([A-Z])/g", " $1")
                    .capitalize()
                    .replace("_", " ")
                    + " "
                    + str(i)
                    + ":</label>"
                )
                s += get_form_element(
                    self, eleattribute[i], type, attribute + "_" + str(i)
                )
            s += "</div>"
            eles.append(s)
        else:
            eles.append(
                '<div class="form-group">'
                + '<label for="'
                + attribute
                + '">'
                + attribute.replace("/([A-Z])/g", " $1").capitalize().replace("_", " ")
                + ":</label>"
                + get_form_element(self, eleattribute, type, attribute)
                + "</div>"
            )

    return eles


def get_module_options(self):
    form = "<form>"
    for ele in get_form_elements(self):
        form += ele
    form += "</form>"
    return form


def get_module_controller(self):
    return None
