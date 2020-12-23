
try:
    from ipywidgets import interact, interactive, interact_manual
    import ipywidgets as widgets
except:
    print("Can't import ipywidgets. Notebook widgets not available")

from tinc_object import TincObject

import struct
import numpy as np

# used in set_XXX_from_message 
import tinc_protocol_pb2 as TincProtocol

parameter_space_type = {
    "VALUE" : 0x00,
    "ID" : 0x01,
    "INDEX" : 0x02
    }


class Parameter(TincObject):
    def __init__(self, tinc_id: str, group = None, minimum: float = -99999.0, maximum: float = 99999.0, default_value: float = 0.0, tinc_client = None):
        # Should not change:tinc_id
        super().__init__(tinc_id)
        self.group = group if group is not None else ""
        self.tinc_client = tinc_client
        
        # Mutable properties
        self.minimum = minimum
        self.maximum = maximum
        self._ids = []
        self._values = []
        self._space_type = parameter_space_type["VALUE"]
        
        # Internal
        self._interactive_widget = None
        self._value_callbacks = []
        self._init(default_value)
        
    def _init(self, default_value):
        self._data_type = float
        self.default = default_value
        if default_value is None:
            self.default = 0.0
        self._value = self.default
        
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self.set_value(value)
            
    @property
    def ids(self):
        return self._ids

    @ids.setter
    def ids(self, ids):
        self.set_ids(ids)
        
    @property
    def values(self):
        return self._values

    @values.setter
    def values(self, values):
        self.set_values(values)
        
    @property
    def space_type(self):
        return self._space_type

    @space_type.setter
    def space_type(self, space_type):
        self.set_space_type(space_type)
        
    def print(self):
        print(f" ** Parameter {self.id} group: {self.group} ({type(self.value)})")
        print(f"    Default: {self.default}")
        print(f"    Min: {self.minimum}")
        print(f"    Max: {self.maximum}")
            
    def set_value(self, value):
        self._value = self._data_type(value)
        if self.tinc_client:
            self.tinc_client.send_parameter_value(self)
        if self._interactive_widget:
            self._interactive_widget.children[0].value = self._data_type(value)
        for cb in self._value_callbacks:
            try:
                cb(value)
            except Exception as e:
                print(e.with_traceback())
            
    def set_at(self, index):
        new_value = self._values[index]
        self.set_value(new_value)
    
    def set_ids(self, ids):
        self._ids = [str(id) for id in ids]
        if self.tinc_client:
            self.tinc_client.send_parameter_space(self)
            
    def set_values(self, values):
        self._values = values
        try:
            self.minimum = min(self._values)
            self.maximum = max(self._values)
            if self.value < self.minimum:
                self.value = self.minimum
                
            if self.value < self.minimum:
                self.value = self.minimum
            if self.value > self.maximum:
                self.value = self.maximum
        except:
            print("Error setting min and max from space values")
        if self.tinc_client:
            self.tinc_client.send_parameter_space(self)
            
    def set_space_type(self, space_type):
        if space_type in parameter_space_type:
            self._space_type = space_type
            self.tinc_client.send_parameter_space_type(self)
        elif type(space_type) == int:
            self._space_type = parameter_space_type[parameter_space_type.values().index(space_type)]
        else:
            raise TypeError("Invalid space type")
            
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
            try:
                cb(value.valueFloat)
            except Exception as e:
                print(e)
        return True

    def set_space_from_message(self, message):
        values = TincProtocol.ParameterSpaceValues()
        message.Unpack(values)
        self._ids = values.ids
        count = len(values.values)
        # print(f'setting space {count}')
        self._values = np.ndarray((count))
        for i, v in enumerate(values.values):
            self._values[i] = v.valueFloat
        return True
    
    def set_space_type_from_message(self, message):
        value = TincProtocol.ParameteValue()
        message.Unpack(value)
        self._space_type = value.valueInt32
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
        if self.tinc_client:
            self.tinc_client.send_parameter_value(self)
        for cb in self._value_callbacks:
            try:
                cb(value)
            except Exception as e:
                print(e) 

    def get_osc_address(self):
        # TODO sanitize names
        addr = "/"
        if not self.group == "":
            addr += self.group + "/"
        addr += self.id    
        return addr
    
    def get_current_id(self):
        index = self.values.tolist().index(self._value)
        return self.ids[index]
        
    
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
    def __init__(self, tinc_id: str, group: str = "", default_value: str = "", tinc_client= None):
        super().__init__(tinc_id, group, default_value=default_value, tinc_client=tinc_client)
        

    def _init(self, default_value):
        self._data_type = str
        self.default = default_value
        if default_value is None:
            self.default = ""
        self._value = self.default
        
    def print(self):
        print(f" ** Parameter {self.id} group: {self.group} ({type(self.value)})")
        print(f"    Default: {self.default}")
    # def get_value_serialized(self):
    #     return struct.pack('f', self._value)
    def set_value(self, value):
        self._value = self._data_type(value)
        if self.tinc_client:
            self.tinc_client.send_parameter_value(self)
        if self._interactive_widget:
            self._interactive_widget.children[0].value = self._data_type(value)
        for cb in self._value_callbacks:
            try:
                cb(value)
            except Exception as e:
                print(e)
    
    def set_value_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        
        # print(f"set {value.valueFloat}")
        if not self._value == value.valueString:
            self._value = self._data_type(value.valueString)

            if self._interactive_widget:
                self._interactive_widget.children[0].value = self._data_type(value.valueString)
        for cb in self._value_callbacks:
            try:
                cb(value.valueString)
            except Exception as e:
                print(e)
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
        # value = TincProtocol.ParameterValue()
        # message.Unpack(value)
        # # print(f"min {value.valueFloat}")
        # self.minimum = value.valueString
        return True
        
    def set_max_from_message(self, message):
        # value = TincProtocol.ParameterValue()
        # message.Unpack(value)
        # # print(f"max {value.valueFloat}")
        # self.maximum = value.valueString
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
    def __init__(self, tinc_id: str, group: str = "", minimum: int = 0, maximum: int = 127, default_value: int = 0, tinc_client = None):
        super().__init__(tinc_id, group, minimum = minimum, maximum = maximum, default_value = default_value, tinc_client = tinc_client)
        
    def _init(self, default_value):
        self._data_type = int
        self.default = default_value
        if default_value is None:
            self.default = 0
        self._value = self.default
        
    def set_value_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        
        # print(f"set {value.valueFloat}")
        if not self._value == value.valueInt32:
            self._value = self._data_type(value.valueInt32)

            if self._interactive_widget:
                self._interactive_widget.children[0].value = self._data_type(value.valueInt32)
        for cb in self._value_callbacks:
            try:
                cb(value.valueInt32)
            except Exception as e:
                print(e)
        return True

    def set_space_from_message(self, message):
        values = TincProtocol.ParameterSpaceValues()
        message.Unpack(values)
        self._ids = values.ids
        count = len(values.values)
        # print(f'setting space {count}')
        self._values = np.ndarray((count))
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
    def __init__(self, tinc_id: str, group: str = "", minimum: int = 0, maximum: int = 127, default_value: int = 0, tinc_client = None):
        super().__init__(tinc_id, group, minimum = minimum, maximum = maximum, default_value = default_value, tinc_client = tinc_client)

        
        
    def _init(self, default_value):
        self._data_type = int
        self.default = default_value
        if default_value is None:
            self.default = 0
        self._value = self.default
        self.elements = []
        
    def set_value_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        
        print(f"set {value.valueUint64}")
        if not self._value == value.valueUint64:
            self._value = self._data_type(value.valueUint64)

            if self._interactive_widget:
                self._interactive_widget.children[0].value = self._data_type(value.valueUint64)
        for cb in self._value_callbacks:
            try:
                cb(value.valueUint64)
            except Exception as e:
                print(e)
        return True

    def set_space_from_message(self, message):
        values = TincProtocol.ParameterSpaceValues()
        message.Unpack(values)
        self._ids = values.ids
        count = len(values.values)
        # print(f'setting space {count}')
        self._values = np.ndarray((count))
        for i, v in enumerate(values.values):
            self._values[i] = v.valueUint64
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

    def set_elements(self, elements):
        self.elements = elements
        
    def get_current_elements(self):
        b = self._value
        current = []
        for e in self.elements:
            if b & 1 == 1:
                current.append(e)
            b = b >> 1
        return current

class ParameterColor(Parameter):
    def __init__(self, tinc_id: str, group: str = "", default_value = [0,0,0,0], tinc_client = None):
        super().__init__(tinc_id, group, default_value = default_value, tinc_client = tinc_client)
        
    def _init(self, default_value):
        self._data_type = lambda l: [float(f) for f in l]
        self.default = default_value
        if default_value is None:
            self.default = [0,0,0,0]
        self._value = self.default
        self.minimum = [0,0,0,0]
        self.maximum = [1,1,1,1]
        
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
            try:
                cb(value._value)
            except Exception as e:
                print(e)
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
    def __init__(self, tinc_id: str, group: str = "", default_value = False, tinc_client = None):
        
        super().__init__(tinc_id, group, default_value = default_value, tinc_client = tinc_client)
        
    def _init(self, default_value):
        self._data_type = bool
        self.default = default_value
        if default_value is None:
            self.default = False
        self._value = self.default
        
    def set_value_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        
        new_value = value.valueBool
        if not self._value == new_value:
            self._value = new_value

            # if self._interactive_widget:
            #     self._interactive_widget.children[0].value = self._data_type(value.valueUint64)
        for cb in self._value_callbacks:
            try:
                cb(value._value)
            except Exception as e:
                print(e)
        return True
        

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

class Trigger(ParameterBool):
    def __init__(self, tinc_id: str, group: str = "", default_value = False, tinc_client = None):
        # default value is ignored
        super().__init__(tinc_id, group, default_value = False, tinc_client = tinc_client)
        
    def _init(self, default_value):
        self._data_type = bool
        self.default = False
        self._value = False
        
    def set_value(self, value):
        self._value = self._data_type(value)
        # if self._interactive_widget:
        #     self._interactive_widget.children[0].value = self._data_type(value)
            
        if self.value == True:
            if self.tinc_client:
                self.tinc_client.send_parameter_value(self)
            for cb in self._value_callbacks:
                try:
                    cb(value)
                except Exception as e:
                    print(e)
            self._value = False
    
    def trigger(self):
        self.set_value(True)

    def set_value_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        print(f"hello {value.valueBool}")
        
        new_value = value.valueBool
        self._value = new_value
        if self._value == True:
            for cb in self._value_callbacks:
                try:
                    cb(value.valueBool)
                except Exception as e:
                    print(e)
            self._value = False
        return True