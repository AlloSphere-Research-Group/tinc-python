
try:
    from ipywidgets import interact, interactive, interact_manual
    import ipywidgets as widgets
except:
    print("Can't import ipywidgets. Notebook widgets not available")

from .tinc_object import TincObject

import struct
import numpy as np
import threading
import traceback

# used in set_XXX_from_message 
from . import tinc_protocol_pb2 as TincProtocol

parameter_space_type = {
    "VALUE" : 0x00,
    "INDEX" : 0x01,
    "ID" : 0x02
    }


class Parameter(TincObject):
    def __init__(self, tinc_id: str, group = None, minimum: float = -99999.0, maximum: float = 99999.0, default_value: float = 0.0, tinc_client = None):
        # Should not change:tinc_id
        if tinc_id.count(' ') != 0 or (group and (group.count(' ') != 0)):
            raise ValueError("Parameter names and group can't contain spaces")
        super().__init__(tinc_id)
        self.group = group if group is not None else ""
        self.tinc_client = tinc_client
        
        # Mutable properties
        self._minimum = minimum
        self._maximum = maximum
        self._ids = []
        self._values = []
        self._space_type = parameter_space_type["VALUE"]
        
        # Internal
        self._interactive_widget = None
        self._value_callbacks = []
        self._async_callbacks = []
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
         
    @property
    def minimum(self):
        return self._minimum

    @minimum.setter
    def minimum(self, minimum):
        self.set_minimum(minimum)
        
    @property
    def maximum(self):
        return self._maximum

    @maximum.setter
    def maximum(self, maximum):
        self.set_maximum(maximum)
        
    def print(self):
        print(f" ** Parameter {self.id} group: {self.group} ({type(self.value)})")
        print(f"    Default: {self.default}")
        print(f"    Min: {self.minimum}")
        print(f"    Max: {self.maximum}")
            
    def set_value(self, value):
        if value < self._minimum:
            value = self._minimum
        if value > self._maximum:
            value = self._maximum
        value = self._find_nearest(value)
            
        self._value = self._data_type(value)
        if self.tinc_client:
            self.tinc_client.send_parameter_value(self)
        if self._interactive_widget:
            self._interactive_widget.children[0].value = self._data_type(value)
        self._trigger_callbacks(self._value)
            
    def set_at(self, index):
        new_value = self._values[index]
        self.set_value(new_value)
    
    def set_ids(self, ids):
        self._ids = [str(id) for id in ids]
        if self.tinc_client:
            self.tinc_client.send_parameter_space(self)
            
    def set_values(self, values):
        # TODO sort values before storing
        self._values = values
        try:
            self._minimum = min(self._values)
            self._maximum = max(self._values)
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
            self._space_type = parameter_space_type[space_type]
            self.tinc_client.send_parameter_space_type(self)
        elif type(space_type) == int:
            self._space_type = parameter_space_type[parameter_space_type.values().index(space_type)]
        else:
            raise TypeError("Invalid space type")
            
    def set_minimum(self, minimum):
        self._minimum = minimum   
        if self.tinc_client:
            self.tinc_client.send_parameter_meta(self, fields=("minimum"))
        
    def set_maximum(self, maximum):
        self._maximum = maximum 
        if self.tinc_client:
            self.tinc_client.send_parameter_meta(self, fields= ("maximum"))  
    
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
            self._trigger_callbacks(self._value)
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
        self._minimum = value.valueFloat
        return True
        
    def set_max_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        # print(f"max {value.valueFloat}")
        self._maximum = value.valueFloat
        return True
        
    def set_from_internal_widget(self, value):
        self._value = value
        if self.tinc_client:
            self.tinc_client.send_parameter_value(self)
        self._trigger_callbacks(value)

    def get_osc_address(self):
        # TODO sanitize names
        addr = "/"
        if not self.group == "":
            addr += self.group + "/"
        addr += self.id    
        return addr
    
    def get_current_id(self):
        if type(self.values) == np.ndarray or type(self.values) == list:
            index = self.get_current_index()
        else:
            raise ValueError("Unsupported list type for values")
        return self.ids[index]
    
    def get_current_index(self):
        if type(self.values) ==list:
            return self.values.index(self.value)
        elif type(self.values) == np.ndarray:
            return np.where (self.values == self.value)[0][0]
    
    def _find_nearest(self, value):
        # TODO assumes values are sorted ascending. Add checks and support for other models.
        if len(self._values) > 0:
            for i in range(len(self._values) - 1):
                if value < (self._values[i] + self._values[i + 1]) /2:
                    return self._values[i]
            return self._values[-1]
        else:
            return value
            
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
    
    def register_callback(self, f, synchronous = True):
        for i,cb in enumerate(self._value_callbacks):
            if f.__name__ == cb.__name__:
                if self._async_callbacks.count(self._value_callbacks[i]) > 0:
                    self._async_callbacks.remove(self._value_callbacks[i])
                self._value_callbacks[i] = f
                if not synchronous:
                    self._async_callbacks.append(f)
                return
                
        self._value_callbacks.append(f)
        if not synchronous:
            self._async_callbacks.append(f)
    
    
    def register_callback_async(self, f):
        self.register_callback(f, False)
        
    def clear_callbacks(self):
        self._value_callbacks = []
        
    def _trigger_callbacks(self, value):
        for cb in self._value_callbacks:
            if self._async_callbacks.count(cb) == 1:
                print(f"starting async callback {cb}")
                x = threading.Thread(target=self._cb_async_wrapper, args=(cb, value), daemon=True)
                x.start()
            else:
                try:
                    cb(value)
                except Exception as e:
                    print("Exception in parameter callback (Continuing):")
                    traceback.print_exc()
    
    def _cb_async_wrapper(self, cb, value):
        try:
            cb(value)
        except Exception as e:
            print("Exception in *async* parameter callback (Continuing):")
            traceback.print_exc()
        
        
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
        self._trigger_callbacks(self._value)
    
    def set_value_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        
        # print(f"set {value.valueFloat}")
        if not self._value == value.valueString:
            self._value = self._data_type(value.valueString)

            if self._interactive_widget:
                self._interactive_widget.children[0].value = self._data_type(value.valueString)
        self._trigger_callbacks(self._value)
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
        self._trigger_callbacks(self._value)
        return True

    def set_space_from_message(self, message):
        values = TincProtocol.ParameterSpaceValues()
        message.Unpack(values)
        self._ids = list(values.ids)
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
        self._minimum = value.valueInt32
        return True
        
    def set_max_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        # print(f"max {value.valueFloat}")
        self._maximum = value.valueInt32
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
        
        # print(f"set {value.valueUint64}")
        if not self._value == value.valueUint64:
            self._value = self._data_type(value.valueUint64)

            if self._interactive_widget:
                self._interactive_widget.children[0].value = self._data_type(value.valueUint64)
        self._trigger_callbacks(self._value)
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
        self._minimum = value.valueUint64
        return True
        
    def set_max_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        # print(f"max {value.valueFloat}")
        self._maximum = value.valueUint64
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
    # TODO merge color with ParameterVec, make ParameterColor sub class of ParameterVec
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
        self._trigger_callbacks(new_value)
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

        self._trigger_callbacks(self._value)
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
            
        if self._value == True:
            if self.tinc_client:
                self.tinc_client.send_parameter_value(self)
            
            self._trigger_callbacks(self._value)
            self._value = False
    
    def trigger(self):
        self.set_value(True)

    def set_value_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        #print(f"hello {value.valueBool}")
        
        new_value = value.valueBool
        self._value = new_value
        if self._value == True:
            self._trigger_callbacks(self._value)
            self._value = False
        return True


class ParameterVec(Parameter):
    def __init__(self, tinc_id: str, group: str = "", size = 3, tinc_client = None):
        
        self.default = [0 for i in range(size)]
        super().__init__(tinc_id, group, minimum = None, maximum = None, default_value = None, tinc_client = tinc_client)
        self.size = size

    def _init(self, default_value):
        self._data_type = list
        # self.default = default_value
        # TODO implement default
        # if default_value is None:
        #     self.default = 0
        self._value = self.default
        
    def set_value(self, value):
        # if value < self._minimum:
        #     value = self._minimum
        # if value > self._maximum:
        #     value = self._maximum
        # TODO implement support for parameter space values for ParameterVec
        # value = self._find_nearest(value)
            
        self._value = self._data_type(value)
        if self.tinc_client:
            self.tinc_client.send_parameter_value(self)
        # TODO implement interactive widget for ParameterVec
        # if self._interactive_widget:
        #     self._interactive_widget.children[0].value = self._data_type(value)
        self._trigger_callbacks(self._value)
            
            
    def set_values(self, values):
        
        # TODO implement support for parameter space values for ParameterVec
        # TODO sort values before storing
        self._values = values
        # try:
        #     self._minimum = min(self._values)
        #     self._maximum = max(self._values)
        #     if self.value < self.minimum:
        #         self.value = self.minimum
        #     if self.value > self.maximum:
        #         self.value = self.maximum
        # except:
        #     print("Error setting min and max from space values")
        # if self.tinc_client:
        #     self.tinc_client.send_parameter_space(self)

    def set_value_from_message(self, message):
        value = TincProtocol.ParameterValue()
        message.Unpack(value)
        
        # print(f"set {value.valueFloat}")
        # TODO check if equal to current value and don't set if equal
        self._value = [v.valueFloat for v in value.valueList]
        # if not self._value == value.valueInt32:
        #     self._value = self._data_type(value.valueInt32)

        #     if self._interactive_widget:
        #         self._interactive_widget.children[0].value = self._data_type(value.valueInt32)
        self._trigger_callbacks(self._value)
        return True

    def set_space_from_message(self, message):
        # TODO implement support for parameter space values for ParameterVec
        # values = TincProtocol.ParameterSpaceValues()
        # message.Unpack(values)
        # self._ids = list(values.ids)
        # count = len(values.values)
        # # print(f'setting space {count}')
        # self._values = np.ndarray((count))
        # for i, v in enumerate(values.values):
        #     self.values[i] = v.valueInt32
        return True

    def set_min_from_message(self, message):
        # TODO implement min
        # value = TincProtocol.ParameterValue()
        # message.Unpack(value)
        # # print(f"min {value.valueFloat}")
        # self._minimum = value.valueInt32
        return True
        
    def set_max_from_message(self, message):
        # TODO implement max
        # value = TincProtocol.ParameterValue()
        # message.Unpack(value)
        # # print(f"max {value.valueFloat}")
        # self._maximum = value.valueInt32
        return True