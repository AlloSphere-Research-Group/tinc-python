
try:
    from ipywidgets import interact, interactive, interact_manual
    import ipywidgets as widgets
except:
    print("Error importin ipywidgets. Notebook widgets not available")
    

class Parameter(object):
    def __init__(self, name: str, group: str = "", default: float = 0.0, prefix: str = "", minimum: float = -99999.0, maximum: float = 99999.0):
        self._value:float = default
        self._data_type = float
        self.name = name
        self.group = group
        self.default = default
        self.prefix = prefix
        self.minimum = minimum
        self.maximum = maximum
        
        self.parent_bundle = None
        
        self._interactive_widget = None
        self.observers = []
        self._value_callbacks = []
        
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self.set_value(value)
            
    def set_value(self, value, source_address=None):
        # This assumes we are never primary application, and
        # we don't relay repetitions. This stops feedback,
        # but means if this is the primary app, some things
        # might not work as expected.
#         print("Got " + str(value))
        if not self._value == value:
            self._value = self._data_type(value)
            for o in self.observers:
                o.send_parameter_value(self, source_address)

            if self._interactive_widget:
                self._interactive_widget.children[0].value = self._data_type(value)
        for cb in self._value_callbacks:
            cb(value)
        
    def set_from_internal_widget(self, value):
        self._value = value
        for o in self.observers:
            o.send_parameter_value(self, None)
        for cb in self._value_callbacks:
            cb(value)
        
    def get_full_address(self):
        # TODO sanitize names
        addr = "/"
        if not self.prefix == "":
            addr += self.prefix + "/"
        if not self.group == "":
            addr += self.group + "/"
        addr += self.name    
        return addr
    
    def interactive_widget(self):
        self._interactive_widget = interactive(self.set_from_internal_widget,
                value=widgets.FloatSlider(
                value=self._value,
                min=self.minimum,
                max=self.maximum,
                description=self.name,
                disabled=False,
                continuous_update=True,
                orientation='horizontal',
                readout=True,
                readout_format='.3f',
            ));
        return self._interactive_widget
    
    def register_callback(self, f):
        for i,cb in enumerate(self._value_callbacks):
            if f.__name__ == cb.__name__:
                print("Replacing previously registered callback")
                self._value_callbacks[i] = f
                return
                
        self._value_callbacks.append(f)
        
class ParameterString(Parameter):
    def __init__(self, name: str, group: str = "", default: str = "", prefix: str = ""):
        self._value :str = default
        self._data_type = str
        self.name = name
        self.group = group
        self.default = default
        self.prefix = prefix
        
        self.parent_bundle = None
        
        self._interactive_widget = None
        self.observers = []
        self._value_callbacks = []
        
    def interactive_widget(self):
        self._interactive_widget = interactive(self.set_from_internal_widget,
                value=widgets.Textarea(
                value=self._value,
                description=self.name,
                disabled=False,
                continuous_update=True,
#                 orientation='horizontal',
                readout=True,
#                 readout_format='.3f',
            ));
        return self._interactive_widget
    

class ParameterInt(Parameter):
    def __init__(self, name: str, group: str = "", default: int = 0, prefix: str = "", minimum: int = 0, maximum: int = 127):
        self._value :int = default
        self._data_type = int
        self.name = name
        self.group = group
        self.default = default
        self.prefix = prefix
        self.minimum = minimum
        self.maximum = maximum
        
        self.parent_bundle = None
        
        self._interactive_widget = None
        self.observers = []
        self._value_callbacks = []
        
#     def interactive_widget(self):
#         self._interactive_widget = interactive(self.set_from_internal_widget,
#                 value=widgets.Textarea(
#                 value=self._value,
#                 description=self.name,
#                 disabled=False,
#                 continuous_update=True,
# #                 orientation='horizontal',
#                 readout=True,
# #                 readout_format='.3f',
#             ));
#         return self._interactive_widget

class ParameterBundle(object):
    def __init__(self, name):
        self.parameters = []
        str:self.id = ''
    
