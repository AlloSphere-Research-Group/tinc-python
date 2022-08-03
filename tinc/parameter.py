
try:
    from ipywidgets import interact, interactive, interact_manual, HBox
    import ipywidgets as widgets
except:
    print("Can't import ipywidgets. Notebook widgets not available")

from .cachemanager import VariantValue, VariantType
from .tinc_object import TincObject
from .variant import VariantType

import struct
import numpy as np
import threading
import traceback
from enum import IntEnum, unique

# used in set_XXX_from_message 
from .tinc_protocol_pb2 import ParameterValue, ParameterSpaceValues

def to_variant(param):
    '''
    :meta private:
    '''
    if type(param) == Parameter:
        return VariantValue(nctype=VariantType.VARIANT_FLOAT,
                            value = param.value())
    elif type(param) == ParameterString:
        return VariantValue(nctype=VariantType.VARIANT_STRING,
                            value = param.value())
    elif type(param) == ParameterInt:
        return VariantValue(nctype=VariantType.VARIANT_INT,
                            value = param.value())
    elif type(param) == ParameterString:
        return VariantValue(nctype=VariantType.VARIANT_STRING,
                            value = param.value())

class parameter_space_representation_types(IntEnum):
    VALUE = 0x00
    INDEX = 0x01
    ID = 0x02

class Parameter(TincObject):
    '''A parameter space dimension that describes the possible values for the parameter and holds a 'current' value

    :param tinc_id: the name that identifies the parameter
    :param group: the name of the group the parameter belongs to
    :param minimum: the minimum value for the parameter. If the value is set to less than this, it is set to minimum
    :param maximum: the maximum value for the parameter. If the value is set to more than this, it is set to maximum
    :param default_value: The parameter's default value
    :param tinc_client: The :class:`tinc.tinc_client.TincClient` the parameter belongs to. This should be left as None when calling directly.
    '''
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
        self._space_repr_type = parameter_space_representation_types.VALUE
        self._space_data_type = VariantType.VARIANT_FLOAT
        
        # Internal
        self._interactive_widget = None
        self._control_widget = None
        self._value_callbacks = []
        self._async_callbacks = []
        self._init(default_value)
        
    def __str__(self):
        details = f" ** Parameter {self.id} group: {self.group} ({type(self.value)})\n"
        details += f"    Default: {self.default}\n"
        details += f"    Min: {self.minimum}\n"
        details += f"    Max: {self.maximum}\n"
        return details

    def _init(self, default_value):
        self._data_type = float
        self.default = default_value
        if default_value is None:
            self.default = 0.0
        self._value = self.default
        
    @property
    def value(self):
        '''The current value for the parameter

        :returns: the current value
        '''
        return self._value

    @value.setter
    def value(self, value):
        self.set_value(value)
            
    @property
    def ids(self):
        '''A list of string values that correspond to each parameter value in the parameter space.

        This can be used to map values to strings or to directory structures.
        '''
        return self._ids

    @ids.setter
    def ids(self, ids):
        self.set_ids(ids)
        
    @property
    def values(self):
        '''A list of the possible values the parameter can take.
        '''
        return self._values

    @values.setter
    def values(self, values):
        self.set_values(values)
        
    @property
    def space_representation_type(self):
        return self._space_repr_type

    @space_representation_type.setter
    def space_representation_type(self, space_representation_type):
        self.set_space_representation_type(space_representation_type)
         
    @property
    def minimum(self):
        '''The minimum the parameter can take.
        '''
        return self._minimum

    @minimum.setter
    def minimum(self, minimum):
        self.set_minimum(minimum)
        
    @property
    def maximum(self):
        '''The maximum the parameter can take.
        '''
        return self._maximum

    @maximum.setter
    def maximum(self, maximum):
        self.set_maximum(maximum)
        
    # def print(self):
    #     '''Print details for this parameters
    #     '''
    #     print(str(self))
            
    def set_value(self, value):
        '''Set the current value for the parameter
        '''
        if value < self._minimum:
            value = self._minimum
        if value > self._maximum:
            value = self._maximum
        value = self._find_nearest(value)
            
        self._value = self._data_type(value)
        if self.tinc_client:
            self.tinc_client._send_parameter_value(self)
        if self._interactive_widget is not None:
            self._interactive_widget.children[0].value = self._value
            
        if self._control_widget is not None:
            self._control_widget.children[1].value = str(self._value)
        self._trigger_callbacks(self._value)
            
    def set_at(self, index):
        new_value = self._values[index]
        self.set_value(new_value)
    
    def set_ids(self, ids):
        self._ids = [str(id) for id in ids]
        if self.tinc_client:
            self.tinc_client._send_parameter_space(self)
    
    def set_values(self, values):
        if len(values) > 0:
            self._values = values
            if type(values) == list:
                    if type(values[0]) == int:
                        self._space_data_type = VariantType.VARIANT_INT32
                    elif type(values[0]) == float:
                        self._space_data_type = VariantType.VARIANT_FLOAT
                    elif type(values[0]) == str:
                        self._space_data_type = VariantType.VARIANT_STRING
            elif type(values).__module__ == np.__name__:
                if values.dtype == np.float64:
                    self._space_data_type = VariantType.VARIANT_DOUBLE
                elif values.dtype == np.float64:
                    self._space_data_type = VariantType.VARIANT_DOUBLE
                elif values.dtype == np.int8:
                    self._space_data_type = VariantType.VARIANT_INT8
                elif values.dtype == np.int16:
                    self._space_data_type = VariantType.VARIANT_INT16
                elif values.dtype == np.int32:
                    self._space_data_type = VariantType.VARIANT_INT32
                elif values.dtype == np.int64:
                    self._space_data_type = VariantType.VARIANT_INT64
                elif values.dtype == np.uint8:
                    self._space_data_type = VariantType.VARIANT_UINT8
                elif values.dtype == np.uint16:
                    self._space_data_type = VariantType.VARIANT_UINT16
                elif values.dtype == np.uint32:
                    self._space_data_type = VariantType.VARIANT_UINT32
                elif values.dtype == np.uint64:
                    self._space_data_type = VariantType.VARIANT_UINT64
                else:
                    raise ValueError("Unsupported numpy data type")
            try:
                self._minimum = min(self._values)
                self._maximum = max(self._values)
                if self.value < self.minimum:
                    self.value = self.minimum
                if self.value > self.maximum:
                    self.value = self.maximum
            except:
                print("Error setting min and max from space values")
        else:
            self._values = values

        self._configure_widget()
        if self.tinc_client:
            self.tinc_client._send_parameter_space(self)

    def get_values(self, remove_duplicates = True):
        if remove_duplicates:
            unique_vals = []
            for v in self.values:
                if not v in unique_vals:
                    unique_vals.append(v)
            return unique_vals
        else:
            return self.values


    def sort(self):
        if len(self._values) > 0 and len(self._values) == len(self._ids):
            zipped = zip(self._values, self._ids)
            sorted_pairs = sorted(zipped)
            tuples = zip(*sorted_pairs)
            # This will update remotes.
            self.values, self.ids = [ list(tuple) for tuple in  tuples]  
        
    def set_space_representation_type(self, space_representation_type):
        try:
            self._space_repr_type = parameter_space_representation_types(space_representation_type)
        except:
            print("Unsupported space type: " + str(space_representation_type))
        if self.tinc_client:
            self.tinc_client._send_parameter_space_type(self)

    def set_minimum(self, minimum):
        self._minimum = minimum 
        if self._interactive_widget:
            self._configure_widget()  
        if self.tinc_client:
            self.tinc_client._send_parameter_meta(self, fields=("minimum"))
        
    def set_maximum(self, maximum):
        self._maximum = maximum 
        if self._interactive_widget:
            self._configure_widget()
        if self.tinc_client:
            self.tinc_client._send_parameter_meta(self, fields= ("maximum"))  
    
    def _get_value_serialized(self):
        return struct.pack('f', self._value)
    
    def _set_value_from_message(self, message):
        value = ParameterValue()
        message.Unpack(value)
        
        # print(f"set {value.valueFloat}")
        if not self._value == value.valueFloat:
            self._value = self._data_type(value.valueFloat)

            if self._interactive_widget is not None:
                self._interactive_widget.children[0].value = self._value
                
            if self._control_widget is not None:
                self._control_widget.children[1].value = str(self._value)
            self._trigger_callbacks(self._value)
        return True

    def _set_space_from_message(self, message):
        values = ParameterSpaceValues()
        message.Unpack(values)
        self._ids = values.ids
        count = len(values.values)
        # print(f'setting space {count}')
        self._values = np.ndarray((count))
        self._space_data_type = None
        for i, v in enumerate(values.values):
            if self._space_data_type is None:
                self._space_data_type = v.nctype
            elif self._space_data_type != v.nctype:
                print("ERROR: inconsistent types in parameter space message")

            if v.nctype == VariantType.VARIANT_FLOAT:
                self._values[i] = v.valueFloat
            elif v.nctype == VariantType.VARIANT_DOUBLE:
                self._values[i] = v.valueDouble
            elif v.nctype == VariantType.VARIANT_INT8:
                self._values[i] = v.valueInt32
            elif v.nctype == VariantType.VARIANT_INT16:
                self._values[i] = v.valueInt32
            elif v.nctype == VariantType.VARIANT_INT32:
                self._values[i] = v.valueInt32
            elif v.nctype == VariantType.VARIANT_INT64:
                self._values[i] = v.valueInt64
            elif v.nctype == VariantType.VARIANT_UINT8:
                self._values[i] = v.valueUint32
            elif v.nctype == VariantType.VARIANT_UINT16:
                self._values[i] = v.valueUint32
            elif v.nctype == VariantType.VARIANT_UINT32:
                self._values[i] = v.valueUint32
            elif v.nctype == VariantType.VARIANT_UINT64:
                self._values[i] = v.valueUint64
            elif v.nctype == VariantType.VARIANT_STRING:
                self._values[i] = v.valueString
            elif v.nctype == VariantType.VARIANT_BOOL:
                self._values[i] = v.valueBool
            else:
                print("ERROR: Unexpected value type in parameter space message " + str(v.nctype))
        
        self._configure_widget()
        
        return True
    
    def _set_space_representation_type_from_message(self, message):
        value = ParameterValue()
        message.Unpack(value)
        try:
            self._space_repr_type = parameter_space_representation_types(value.valueInt32)
        except:
            print("ERROR setting parameter space type")
            return False
        return True

    def _set_min_from_message(self, message):
        value = ParameterValue()
        message.Unpack(value)
        # print(f"min {value.valueFloat}")
        self._minimum = value.valueFloat
        if self._interactive_widget:
            self._configure_widget()
        return True
        
    def _set_max_from_message(self, message):
        value = ParameterValue()
        message.Unpack(value)
        # print(f"max {value.valueFloat}")
        self._maximum = value.valueFloat
        if self._interactive_widget:
            self._configure_widget()
        return True
        
    def _set_from_internal_widget(self, value):
        if len(self.values) > 0:
            value = self._find_nearest(value)
            if value == self._value:
                return
            self._value = self._data_type(value)
        else:
            self._value = self._data_type(value)
        self._interactive_widget.children[0].value = self._data_type(value)
        
        if self._control_widget is not None:
            self._control_widget.children[1].value = str(self._value)
        if self.tinc_client:
            self.tinc_client._send_parameter_value(self)
        self._trigger_callbacks(value)

    def get_osc_address(self):
        # TODO sanitize names
        addr = "/"
        if not self.group == "":
            addr += self.group + "/"
        addr += self.id    
        return addr
    
    def get_space_stride(self):
        if len(self.values) < 2:
            return 1
        s = 1
        curIndex = 0
        val = self.values[0]
        next_val = self.values[1]
        while next_val == val:
            s += 1
            if (curIndex + s) >= len(self.values):
                # we are at the last index
                return s
            next_val = self.values[curIndex + s]
        return s

    def get_current_id(self):
        if type(self.values) == np.ndarray or type(self.values) == list:
            index = self.get_current_index()
        else:
            raise ValueError("Unsupported list type for values")
        return self.ids[index]
    
    '''
    Get all ids for current value, when value is repeated with different ids
    '''
    def get_current_ids(self):
        ids = []
        if len(self.ids) > 0:
            cur_val = self.value
            for i,val in enumerate(self.values):
                if val == cur_val:
                    ids.append(self.ids[i])
        return ids
    
    def get_ids_for_value(self, value):
        ids = []
        if len(self.ids) > 0:
            cur_val = value
            for i,val in enumerate(self.values):
                if val == cur_val:
                    ids.append(self.ids[i])
        return ids

    def get_current_index(self):
        if type(self.values) == list:
            try:
                return self.values.index(self.value)
            except:
                return 0
        elif type(self.values) == np.ndarray:
            return np.where (self.values == self.value)[0][0]
            
    def next(self):
        '''Move to the next value (by index) in the values list.
        If values list is empty or currently at the last item, there is no effect.
        '''
        if len(self._values) <=1:
            raise RuntimeError("Not enough values in space for next()")
        next_index = self.get_current_index() + 1
        if next_index < len(self._values):
            self.set_value(self._values[next_index])
            
    def previous(self):
        '''Move to the previous value (by index) in the values list.
        If values list is empty or currently at the first item, there is no effect.
        '''
        if len(self._values) <=1:
            raise RuntimeError("Not enough values in space for previous()")
        next_index = self.get_current_index() - 1
        if next_index >= 0:
            self.set_value(self._values[next_index])


    def interactive_widget(self):
        '''Return an interactive widget for jupyter notebook.
        Requires ipywidgets.
        '''
        if self._interactive_widget is None:
            self._interactive_widget = interactive(self._set_from_internal_widget,
                    value=widgets.FloatSlider(
                    value=self._value,
                    min=self.minimum,
                    max=self.maximum,
                    description=self.id,
                    disabled=False,
                    continuous_update=True,
                    orientation='horizontal',
                    readout=True
                ))
            self._configure_widget()
        return self._interactive_widget

    def interactive_control(self):
        '''Return an interactive control widget for jupyter notebook.
        Requires ipywidgets.
        '''
        if self._control_widget is None:
            def next_wrapper(value):
                self.next()
            def prev_wrapper(value):
                self.previous()
            next_button = widgets.Button(  description=">>" )
            next_button.on_click(next_wrapper)
            prev_button = widgets.Button(  description="<<" )
            prev_button.on_click(prev_wrapper)
            label = widgets.Label(value=str(self.value))

            self._control_widget = HBox([prev_button, label, next_button])
            # self._configure_widget()
        return self._control_widget
    
    def register_callback(self, f, synchronous = True):
        '''Register a function that will be called whenever the parameter's value changes.
        Note that what is registered is the function object, so if you redefine the function after registering,
        the registered function will still use the previously registered function.

        :param f: Function to be called.
        :param synchronous: if False, the callback will be called from a separate thread and will not block
        '''
        for i,cb in enumerate(self._value_callbacks):
            if f.__name__ == cb.__name__ \
                and (cb.__qualname__.count('.') == 0 and f != cb):
                # cb.__qualname__.count('.') == 0 - a way to tell if function is part of a class.
                if self._async_callbacks.count(self._value_callbacks[i]) > 0:
                    self._async_callbacks.remove(self._value_callbacks[i])
                self._value_callbacks[i] = f
                if not synchronous:
                    self._async_callbacks.append(f)
                return
                
        self._value_callbacks.append(f)
        if not synchronous:
            self._async_callbacks.append(f)
        else:
            # TODO ML add all API functions that call into _command functions in the TincClient
            import dis
            from tinc import DataPool, ParameterSpace, DiskBuffer
            bytecode = dis.Bytecode(f)
            for instr in bytecode:
                if instr.opname == 'LOAD_METHOD':
                    if instr.argval == 'get_slice':
                        print('''WARNING: calling certain Tinc functions inside callbacks can cause deadlocks and Timeout.
If this is happening use asynchronous callbacks by setting synchrouns to False when registering callback''' )
        
    def _find_nearest(self, value):
        # TODO assumes values are sorted ascending. Add checks and support for other models.
        if len(self._values) > 0:
            for i in range(len(self._values) - 1):
                if value < (self._values[i] + self._values[i + 1]) /2:
                    return self._data_type(self._values[i])
            return self._data_type(self._values[-1])
        else:
            return self._data_type(value)

    def _configure_widget(self):
        if self._interactive_widget is not None:
            widget = self._interactive_widget.children[0]
            if len(self._values) > 1:
                min_step = np.min(np.diff(self._values))
            else:
                min_step = (self._maximum - self._minimum) /100
            num_zeros = np.floor(np.abs(np.log10(min_step)))

            # Heuristics to determine display presicion
            temp_val = min_step * 10**(num_zeros)
            while np.abs(temp_val - int(temp_val)) > 0.000001 and num_zeros < 7:
                num_zeros += 1
                temp_val = min_step * 10**(num_zeros)
            format = f'.{int(num_zeros)}f'
            
            widget.min = self._minimum
            widget.max = self._maximum
            widget.readout_format = format
            widget.step = min_step
            
        # if self._control_widget is not None:
        #     label = self._control_widget.children[1]
            #label.value = str(self.get_value())

    def register_callback_async(self, f):
        self.register_callback(f, False)
    
    def remove_callback(self, f):
        if type(f) == str:
            for _f in self._value_callbacks:
                if _f.__name__ == f:
                    self.remove_callback(f)
            for _f in self._async_callbacks:
                if _f.__name__ == f:
                    self.remove_callback(f)
        # FIXME remove by name rather than by object
        if self._value_callbacks.count(f) > 0:
            self._value_callbacks.remove(f)
        if self._async_callbacks.count(f) > 0:
            self._async_callbacks.remove(f)

    def clear_callbacks(self):
        '''Remove all callbacks registered with object'''
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
        
    def __str__(self):
        details = f" ** Parameter {self.id} group: {self.group} ({type(self.value)})\n"
        details += f"    Default: {self.default}\n"
        return details

    def _init(self, default_value):
        self._data_type = str
        self.default = default_value
        if default_value is None:
            self.default = ""
        self._value = self.default

    def set_value(self, value):
        self._value = self._data_type(value)
        if self.tinc_client:
            self.tinc_client._send_parameter_value(self)
        if self._interactive_widget:
            self._interactive_widget.children[0].value = self._data_type(value)
        if self._control_widget is not None:
            self._control_widget.children[1].value = str(self._value)
        self._trigger_callbacks(self._value)

    def _set_value_from_message(self, message):
        value = ParameterValue()
        message.Unpack(value)
        
        # print(f"set {value.valueFloat}")
        if not self._value == value.valueString:
            self._value = self._data_type(value.valueString)

            if self._interactive_widget:
                self._interactive_widget.children[0].value = self._data_type(value.valueString)
        self._trigger_callbacks(self._value)
        return True

    def _set_space_from_message(self, message):
        values = ParameterSpaceValues()
        message.Unpack(values)
        self.ids = values.ids
        count = len(values.values)
        # print(f'setting space {count}')
        self.values = np.ndarray((count))
        for i, v in enumerate(values.values):
            self.values[i] = v.valueString
        return True

    def _set_min_from_message(self, message):
        # value = ParameterValue()
        # message.Unpack(value)
        # # print(f"min {value.valueFloat}")
        # self.minimum = value.valueString
        return True
        
    def _set_max_from_message(self, message):
        # value = ParameterValue()
        # message.Unpack(value)
        # # print(f"max {value.valueFloat}")
        # self.maximum = value.valueString
        return True
        
    def set_values(self, values):
        for v in values:
            if type(v) != str:
                raise ValueError("All values must be str for ParameterString")
        self._values = values
        self._value = values[self.get_current_index()]
        self._space_data_type = VariantType.VARIANT_STRING
        # TODO validate that space is string

        if self.tinc_client:
            self.tinc_client._send_parameter_space(self)
    
    def interactive_widget(self):
        text_field = widgets.Textarea(
                value=self._value,
                description=self.id,
                disabled=False,
                continuous_update=True,
#                 orientation='horizontal',
                readout=True,
#                 readout_format='.3f',
            )
        button = widgets.Button(  description="Apply" )

        def cb(button):
            self._set_from_internal_widget(text_field.value)
        
        button.on_click(cb)

        self._interactive_widget = HBox((text_field, button))
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
        
    def _set_value_from_message(self, message):
        value = ParameterValue()
        message.Unpack(value)
        
        # print(f"set {value.valueFloat}")
        if not self._value == value.valueInt32:
            self._value = self._data_type(value.valueInt32)

            if self._interactive_widget:
                self._interactive_widget.children[0].value = self._data_type(value.valueInt32)
        self._trigger_callbacks(self._value)
        return True

    def _set_space_from_message(self, message):
        values = ParameterSpaceValues()
        message.Unpack(values)
        self._ids = list(values.ids)
        count = len(values.values)
        # print(f'setting space {count}')
        self._values = np.ndarray((count))
        for i, v in enumerate(values.values):
            self.values[i] = v.valueInt32
        return True

    def _set_min_from_message(self, message):
        value = ParameterValue()
        message.Unpack(value)
        # print(f"min {value.valueFloat}")
        self._minimum = value.valueInt32
        return True
        
    def _set_max_from_message(self, message):
        value = ParameterValue()
        message.Unpack(value)
        # print(f"max {value.valueFloat}")
        self._maximum = value.valueInt32
        return True
    
    def interactive_widget(self):
        if self._interactive_widget is None:
            self._interactive_widget = interactive(self._set_from_internal_widget,
                    value=widgets.FloatSlider(
                    value=self._value,
                    min=self.minimum,
                    max=self.maximum,
                    description=self.id,
                    disabled=False,
                    continuous_update=True,
                    orientation='horizontal',
                    readout=True,
                    step =1
                ));
            self._configure_widget()
            
        return self._interactive_widget
    
    def _configure_widget(self):
        if self._interactive_widget is not None:
            widget = self._interactive_widget.children[0]
            if len(self._values) > 1:
                min_step = np.min(np.diff(self._values))
            else:
                min_step = 1
            num_zeros = np.floor(np.abs(np.log10(min_step)))

            # Heuristics to determine display precision
            temp_val = min_step * 10**(num_zeros)
            while np.abs(temp_val - int(temp_val)) > 0.000001 and num_zeros < 7:
                num_zeros += 1
                temp_val = min_step * 10**(num_zeros)
            format = f'.{int(num_zeros)}f'
            
            widget.min = self._minimum
            widget.max = self._maximum
            widget.readout_format = format
            widget.step = min_step
    
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
        
    def set_value(self, value):
        if value < self._minimum:
            value = self._minimum
        if value > self._maximum:
            value = self._maximum
        value = self._find_nearest(value)
            
        self._value = self._data_type(value)
        if self.tinc_client:
            self.tinc_client._send_parameter_value(self)
        if self._interactive_widget:
            self._interactive_widget.children[0].value = self.elements[value]
        self._trigger_callbacks(self._value)
        
    def _set_value_from_message(self, message):
        value = ParameterValue()
        message.Unpack(value)
        
        # print(f"set {value.valueUint64}")
        if not self._value == value.valueUint64:
            self._value = self._data_type(value.valueUint64)

            if self._interactive_widget:
                self._interactive_widget.children[0].value = self._data_type(value.valueUint64)
        self._trigger_callbacks(self._value)
        return True

    def _set_space_from_message(self, message):
        values = ParameterSpaceValues()
        message.Unpack(values)
        self._ids = values.ids
        count = len(values.values)
        # print(f'setting space {count}')
        self._values = np.ndarray((count))
        for i, v in enumerate(values.values):
            self._values[i] = v.valueUint64
        return True

    def _set_min_from_message(self, message):
        value = ParameterValue()
        message.Unpack(value)
        # print(f"min {value.valueFloat}")
        self._minimum = value.valueUint64
        return True
        
    def _set_max_from_message(self, message):
        value = ParameterValue()
        message.Unpack(value)
        # print(f"max {value.valueFloat}")
        self._maximum = value.valueUint64
        return True

    def set_elements(self, elements):
        self.elements = elements
        if self._interactive_widget is not None:
            self._configure_widget()
        
    def get_current_elements(self):
        b = self._value
        current = []
        for e in self.elements:
            if b & 1 == 1:
                current.append(e)
            b = b >> 1
        return current
    
    def interactive_widget(self):
        if self._interactive_widget is None:
            self._interactive_widget = interactive(self._set_from_internal_widget,
                    widget_value=widgets.Dropdown(
                        options = [],
                        description = self.id,
                        disabled = False
                ));
            self._configure_widget()
        return self._interactive_widget
    
    def _configure_widget(self):
        if self._interactive_widget is not None:
            widget = self._interactive_widget.children[0]
            widget.options = self.elements
            
    def _set_from_internal_widget(self, widget_value):
        # if len(self.values) > 0:
        #     value = self._find_nearest(value)
        #     if value == self._value:
        #         return
        #     self._value = value 
        # else:
        try:
            self._value = self.elements.index(widget_value)
            self._interactive_widget.children[0].value = widget_value
            if self.tinc_client:
                self.tinc_client._send_parameter_value(self)
            self._trigger_callbacks(self._value)
        except:
            print(f'Invalid value: {widget_value}')

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
        
    def _set_value_from_message(self, message):
        value = ParameterValue()
        message.Unpack(value)
        
        new_value = [v.valueFloat for v in value.valueList]
        # print(f"set {value.valueFloat}")
        if not self._value == new_value:
            self._value = new_value

            # if self._interactive_widget:
            #     self._interactive_widget.children[0].value = self._data_type(value.valueUint64)
        self._trigger_callbacks(new_value)
        return True

    def _set_space_from_message(self, message):
        print("No parameter space for ParameterColor")
        # values = ParameterSpaceValues()
        # message.Unpack(values)
        # self.ids = values.ids
        # count = len(values.values)
        # # print(f'setting space {count}')
        # self.values = np.ndarray((count))
        # for i, v in enumerate(values.values):
        #     self.values[i] = v.valueUint64
        return True

    def _set_min_from_message(self, message):
        print("Can't set minimum for ParameterColor")
        # value = ParameterValue()
        # message.Unpack(value)
        # # print(f"min {value.valueFloat}")
        # self.minimum = value.valueUint64
        return True
        
    def _set_max_from_message(self, message):
        print("Can't set maximum for ParameterColor")
        # value = ParameterValue()
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
        
    def _set_value_from_message(self, message):
        value = ParameterValue()
        message.Unpack(value)
        
        new_value = value.valueBool
        if not self._value == new_value:
            self._value = new_value

            # if self._interactive_widget:
            #     self._interactive_widget.children[0].value = self._data_type(value.valueUint64)

        self._trigger_callbacks(self._value)
        return True
        

#     def interactive_widget(self):
#         self._interactive_widget = interactive(self._set_from_internal_widget,
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
                self.tinc_client._send_parameter_value(self)
            
            self._trigger_callbacks(self._value)
            self._value = False
    
    def trigger(self):
        self.set_value(True)

    def _set_value_from_message(self, message):
        value = ParameterValue()
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
            self.tinc_client._send_parameter_value(self)
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
        #     self.tinc_client._send_parameter_space(self)

    def _set_value_from_message(self, message):
        value = ParameterValue()
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

    def _set_space_from_message(self, message):
        # TODO implement support for parameter space values for ParameterVec
        # values = ParameterSpaceValues()
        # message.Unpack(values)
        # self._ids = list(values.ids)
        # count = len(values.values)
        # # print(f'setting space {count}')
        # self._values = np.ndarray((count))
        # for i, v in enumerate(values.values):
        #     self.values[i] = v.valueInt32
        return True

    def _set_min_from_message(self, message):
        # TODO implement min
        # value = ParameterValue()
        # message.Unpack(value)
        # # print(f"min {value.valueFloat}")
        # self._minimum = value.valueInt32
        return True
        
    def _set_max_from_message(self, message):
        # TODO implement max
        # value = ParameterValue()
        # message.Unpack(value)
        # # print(f"max {value.valueFloat}")
        # self._maximum = value.valueInt32
        return True