
try:
    from ipywidgets import interact, interactive, interact_manual
    import ipywidgets as widgets
except:
    print("Error importin ipywidgets. Notebook widgets not available")
    
from message import Message
import struct
import numpy as np

# used in set_XXX_from_message 
import tinc_protocol_pb2 as TincProtocol
from google.protobuf import any_pb2


class Parameter(object):
    def __init__(self, tinc_client, id: str, group: str = "", default: float = 0.0, minimum: float = -99999.0, maximum: float = 99999.0):
        # Should not change:
        self.id = id
        self.group = group
        self.default = default
        self.tinc_client = tinc_client
        
        # Mutable properties
        self._data_type = float
        self.minimum = minimum
        self.maximum = maximum
        self.ids = []
        self.values = None
        
        # Internal
        self._value:float = default
        self.parent_bundle = None
        
        self._interactive_widget = None
        self._value_callbacks = []
        
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self.set_value(value)
        
    def print(self):
        print(f" ** Parameter {self.id} group: {self.group} ({type(self.value)})")
        print(f"    Default: {self.default}")
        print(f"    Min: {self.minimum}")
        print(f"    Max: {self.maximum}")
            
    def set_value(self, value):
        self._value = self._data_type(value)
        self.tinc_client.send_parameter_value(self)
        if self._interactive_widget:
            self._interactive_widget.children[0].value = self._data_type(value)
        for cb in self._value_callbacks:
            cb(value)
            
    def get_value_serialized(self):
        return struct.pack('f', self._value)
    
    def set_value_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        
        # print(f"set {value.valueFloat}")
        if not self._value == value.valueFloat:
            self._value = self._data_type(value.valueFloat)

            if self._interactive_widget:
                self._interactive_widget.children[0].value = self._data_type(value.valueFloat)
        for cb in self._value_callbacks:
            cb(value.valueFloat)
        return True

    def set_space_from_message(self, message):
        values = TincProtocol.ParameterSpaceValues()
        message.Unpack(values)
        self.ids = values.ids
        count = len(values.values)
        # print(f'setting space {count}')
        self.values = np.ndarray((count))
        for i, v in enumerate(values.values):
            self.values[i] = v.valueFloat
        return True

    def set_min_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        # print(f"min {value.valueFloat}")
        self.minimum = value.valueFloat
        return True
        
    def set_max_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        # print(f"max {value.valueFloat}")
        self.maximum = value.valueFloat
        return True
        
    def set_from_internal_widget(self, value):
        self._value = value
        self.tinc_client.send_parameter_value(self)
        for cb in self._value_callbacks:
            cb(value)

    def get_osc_address(self):
        # TODO sanitize names
        addr = "/"
        if not self.group == "":
            addr += self.group + "/"
        addr += self.id    
        return addr
    
    def interactive_widget(self):
        self._interactive_widget = interactive(self.set_from_internal_widget,
                value=widgets.FloatSlider(
                value=self._value,
                min=self.minimum,
                max=self.maximum,
                description=self.id,
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
    def __init__(self, tinc_client, id: str, group: str = "", default: str = ""):
        self._value :str = default
        self._data_type = str
        self.id = id
        self.group = group
        self.default = default
        self.tinc_client = tinc_client
        
        self.parent_bundle = None
        
        self._interactive_widget = None
        self.observers = []
        self._value_callbacks = []
        
    # def get_value_serialized(self):
    #     return struct.pack('f', self._value)
    def set_value(self, value):
        if len(value) > 4:
            value = value[:4]
        if len(value) < 4:
            value.append(self._value[len(value):])
        self._value = self._data_type(value)
        self.tinc_client.send_parameter_value(self)
        if self._interactive_widget:
            self._interactive_widget.children[0].value = self._data_type(value)
        for cb in self._value_callbacks:
            cb(value)
    
    def set_value_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        
        # print(f"set {value.valueFloat}")
        if not self._value == value.valueFloat:
            self._value = self._data_type(value.valueFloat)

            if self._interactive_widget:
                self._interactive_widget.children[0].value = self._data_type(value.valueString)
        for cb in self._value_callbacks:
            cb(value.valueString)
        return True

    def set_space_from_message(self, message):
        values = TincProtocol.ParameterSpaceValues()
        message.Unpack(values)
        self.ids = values.ids
        count = len(values.values)
        # print(f'setting space {count}')
        self.values = np.ndarray((count))
        for i, v in enumerate(values.values):
            self.values[i] = v.valueString
        return True

    def set_min_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        # print(f"min {value.valueFloat}")
        self.minimum = value.valueString
        return True
        
    def set_max_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        # print(f"max {value.valueFloat}")
        self.maximum = value.valueString
        return True
    
    def interactive_widget(self):
        self._interactive_widget = interactive(self.set_from_internal_widget,
                value=widgets.Textarea(
                value=self._value,
                description=self.id,
                disabled=False,
                continuous_update=True,
#                 orientation='horizontal',
                readout=True,
#                 readout_format='.3f',
            ));
        return self._interactive_widget
    

class ParameterInt(Parameter):
    def __init__(self, tinc_client, id: str, group: str = "", default: int = 0, minimum: int = 0, maximum: int = 127):
        self._value :int = default
        self._data_type = int
        self.id = id
        self.group = group
        self.default = default
        self.minimum = minimum
        self.maximum = maximum
        self.tinc_client = tinc_client
        
        self.parent_bundle = None
        
        self._interactive_widget = None
        self.observers = []
        self._value_callbacks = []
        
    def set_value_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        
        # print(f"set {value.valueFloat}")
        if not self._value == value.valueInt32:
            self._value = self._data_type(value.valueInt32)

            if self._interactive_widget:
                self._interactive_widget.children[0].value = self._data_type(value.valueInt32)
        for cb in self._value_callbacks:
            cb(value.valueInt32)
        return True

    def set_space_from_message(self, message):
        values = TincProtocol.ParameterSpaceValues()
        message.Unpack(values)
        self.ids = values.ids
        count = len(values.values)
        # print(f'setting space {count}')
        self.values = np.ndarray((count))
        for i, v in enumerate(values.values):
            self.values[i] = v.valueInt32
        return True

    def set_min_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        # print(f"min {value.valueFloat}")
        self.minimum = value.valueInt32
        return True
        
    def set_max_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        # print(f"max {value.valueFloat}")
        self.maximum = value.valueInt32
        return True
    
class ParameterChoice(Parameter):
    def __init__(self, tinc_client, id: str, group: str = "", default: int = 0, minimum: int = 0, maximum: int = 127):
        self._value :int = default
        self._data_type = int
        self.id = id
        self.group = group
        self.default = default
        self.minimum = minimum
        self.maximum = maximum
        self.tinc_client = tinc_client
        
        self.parent_bundle = None
        
        self._interactive_widget = None
        self.observers = []
        self._value_callbacks = []
        
    def set_value_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        
        # print(f"set {value.valueFloat}")
        if not self._value == value.valueUint64:
            self._value = self._data_type(value.valueUint64)

            if self._interactive_widget:
                self._interactive_widget.children[0].value = self._data_type(value.valueUint64)
        for cb in self._value_callbacks:
            cb(value.valueUint64)
        return True

    def set_space_from_message(self, message):
        values = TincProtocol.ParameterSpaceValues()
        message.Unpack(values)
        self.ids = values.ids
        count = len(values.values)
        # print(f'setting space {count}')
        self.values = np.ndarray((count))
        for i, v in enumerate(values.values):
            self.values[i] = v.valueUint64
        return True

    def set_min_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        # print(f"min {value.valueFloat}")
        self.minimum = value.valueUint64
        return True
        
    def set_max_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        # print(f"max {value.valueFloat}")
        self.maximum = value.valueUint64
        return True
        

class ParameterColor(Parameter):
    def __init__(self, tinc_client, id: str, group: str = "", default = [0,0,0,0]):
        self._value = default
        self._data_type = lambda l: [float(f) for f in l]
        self.id = id
        self.group = group
        self.default = default
        self.minimum = [0,0,0,0]
        self.maximum = [1,1,1,1]
        self.tinc_client = tinc_client
        
        self.parent_bundle = None
        
        self._interactive_widget = None
        self.observers = []
        self._value_callbacks = []
        
    def set_value_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        
        new_value = [v.valueFloat for v in value.valueList]
        # print(f"set {value.valueFloat}")
        if not self._value == new_value:
            self._value = new_value

            # if self._interactive_widget:
            #     self._interactive_widget.children[0].value = self._data_type(value.valueUint64)
        for cb in self._value_callbacks:
            cb(self._value)
        return True

    def set_space_from_message(self, message):
        print("No parameter space for ParameterColor")
        # values = TincProtocol.ParameterSpaceValues()
        # message.Unpack(values)
        # self.ids = values.ids
        # count = len(values.values)
        # # print(f'setting space {count}')
        # self.values = np.ndarray((count))
        # for i, v in enumerate(values.values):
        #     self.values[i] = v.valueUint64
        return True

    def set_min_from_message(self, message):
        print("Can't set minimum for ParameterColor")
        # value = TincProtocol.ParameterValue()
        # message.Unpack(value)
        # # print(f"min {value.valueFloat}")
        # self.minimum = value.valueUint64
        return True
        
    def set_max_from_message(self, message):
        print("Can't set maximum for ParameterColor")
        # value = TincProtocol.ParameterValue()
        # message.Unpack(value)
        # # print(f"max {value.valueFloat}")
        # self.maximum = value.valueUint64
        return True    

class ParameterBool(Parameter):
    def __init__(self, p_id: str, group: str = "", default: float = 0.0):
        self._value = default
        self._data_type = float
        self.id = p_id
        self.group = group
        self.default = default
        
        self.parent_bundle = None
        
        self._interactive_widget = None
        self.observers = []
        self._value_callbacks = []
        
        
#     def interactive_widget(self):
#         self._interactive_widget = interactive(self.set_from_internal_widget,
#                 value=widgets.Textarea(
#                 value=self._value,
#                 description=self.id,
#                 disabled=False,
#                 continuous_update=True,
# #                 orientation='horizontal',
#                 readout=True,
# #                 readout_format='.3f',
#             ));
#         return self._interactive_widget

class ParameterBundle(object):
    def __init__(self, id):
        self.parameters = []
        str:self.id = ''
    
