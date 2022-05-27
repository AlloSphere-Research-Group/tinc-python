from enum import auto
import threading
import time
import socket
from tinc.variant import VariantType
from typing import List, Any
import struct
import socket # For gethostname()
from threading import Lock

# TINC imports
from .parameter import Parameter, ParameterString, ParameterInt, ParameterChoice, ParameterBool, ParameterColor, Trigger, ParameterVec
from .processor import ProcessorCpp, ProcessorScript, ComputationChain
from .datapool import DataPool, DataPoolJson
from .parameter_space import ParameterSpace
from .disk_buffer import *
from .cachemanager import *
from .message import Message
from . import tinc_protocol_pb2 as TincProtocol
#from google.protobuf import any_pb2 #, message

tinc_client_version = 1
tinc_client_revision = 0

commands = {
    "HANDSHAKE" : 0x01,
    "HANDSHAKE_ACK" : 0x02,
    "GOODBYE" : 0x03,
    "GOODBYE_ACK" : 0x04,
    "PING" : 0x05,
    "PONG" : 0x06,
    }

class TincTimeout(ValueError):
    def __init__(self, arg):
        self.strerror = arg
        self.args = {arg}


class TincClient(object):
    '''The TincClient class allows connecting to a TINC server to share parameters and data.

    :param server_addr: The IP address for the TINC server to connect to
    :param server_port: The port for the TINC server
    :param auto_connect: If true will connect to the server on creation of a TincClient object. If false, client can connect via the start() function.
    '''
    def __init__(self, server_addr: str = "localhost",
                 server_port: int = 34450, auto_connect = True):
        '''Constructor method
        '''
        
        self.connected = False
        self.parameters = []
        self.processors = []
        self.datapools = []
        self.disk_buffers = []
        self.parameter_spaces = []
        self.request_timeout = 10.0
        self.pending_requests = {}
        self.pending_requests_count = 1
        self.pending_replies = {}
        
        self.request_count_lock = Lock()
        self.pending_requests_lock = Lock()
        self.pending_lock = Lock()
        
        self._barrier_queues_lock = Lock()
        self._barrier_requests = []
        self._barrier_unlocks = []
        self.barrier_wait_granular_time_ms = 20
        
        self.server_version = 0
        self.server_revision = 0
        
        self._log = []
        
        self.debug = False
        
        self._server_status = TincProtocol.StatusTypes.UNKNOWN
        
        if auto_connect:
            self.start(server_addr, server_port)
    
    def __str__(self): 
        if self.socket:
            print("TINC Server")
            if self.connected:
                print("CONNECTED")
                for param in self.parameters:
                    param.print()
                for ps in self.parameter_spaces:
                    ps.print()
                for db in self.disk_buffers:
                    db.print()
                for p in self.processors:
                    p.print()
                for dp in self.datapools:
                    dp.print()
                
            elif self.running:
                print("Attempting to connect to app. App is not reponding.")
            else:
                print("NOT CONNECTED")
        else:
            print("NOT CONNECTED")
    def __del__(self):
        self.stop()
        print("Stopped")
        
    def start(self, server_addr = "localhost", server_port = 34450):
        '''Start the TINC client, attempting to connect to the TINC server at the provided address and port

        :param server_addr: The IP address for the TINC server to connect to
        :param server_port: The port for the TINC server
        '''
        # self.pserver = pserver
        self.serverAddr = server_addr
        self.serverPort = server_port
        
        self.running = True
        self.x = threading.Thread(target=self._server_thread_function, args=(self.serverAddr,self.serverPort))
        self.x.start()  
        
    def stop(self):
        '''Stop the TINC client. Disconnects from TINC server
        '''
        if self.running:
            self._send_goodbye()
            self.running = False
            self.connected = False
            self.x.join()
            self.socket.close()
            self.socket = None
        
        self.server_version = 0
        self.server_revision = 0
        
    def server_status(self):
        return self._server_status

    def barrier(self, group = 0, timeout_sec = 0):
        with self._barrier_queues_lock:
            # first flush all requests that match unlocks
            matched_unlocks = []
            for unlock in self._barrier_unlocks:
                if self._barrier_requests.count(unlock) > 0:
                    self._barrier_requests.remove(unlock)
                    matched_unlocks.append(unlock)
            for matched in matched_unlocks:
                if self._barrier_unlocks.count(matched) > 0:
                    self._barrier_requests.remove(matched)
            
            print("-----",len(self._barrier_requests))
            if len(self._barrier_requests)  > 1:
                print("Unexpected inconsistent state in barrier. Aborting and flushing barriers.")
                self._barrier_requests.clear()
                self._barrier_unlocks.clear()
                return False
            
        
        timems = 0.0
        current_consecutive = 0
        while timems < (timeout_sec * 1000) or timeout_sec == 0:
            if (self._barrier_queues_lock.acquire(False)):
                if len(self._barrier_requests) > 0:
                    current_consecutive = self._barrier_requests[0]
                    
                    msg = TincProtocol.TincMessage()
                    msg.messageType  = TincProtocol.BARRIER_ACK_LOCK
                    msg.objectType = TincProtocol.GLOBAL
                    comm = TincProtocol.Command()
                    comm.message_id = current_consecutive
                    msg.details.Pack(comm)
                    self._send_message(msg)
                    self._barrier_requests.remove(current_consecutive)
                    self._barrier_queues_lock.release()
                    break
                self._barrier_queues_lock.release()
            time.sleep(self.barrier_wait_granular_time_ms* 0.001)
            timems += self.barrier_wait_granular_time_ms
                        
        if timems > (timeout_sec * 1000) and timeout_sec != 0.0:
            # Timeout.
            return False
        
        # Now wait for unlock
        timems = 0.0
        while timems < (timeout_sec * 1000) or timeout_sec == 0:
            if (self._barrier_queues_lock.acquire(False)):
                if self._barrier_unlocks.count(current_consecutive) > 0:
                    self._barrier_unlocks.remove(current_consecutive)
                    self._barrier_queues_lock.release()
                    break
                
                self._barrier_queues_lock.release()
            
            time.sleep(self.barrier_wait_granular_time_ms* 0.001)
            timems += self.barrier_wait_granular_time_ms
            
        print("Exit client barrier")
        return timems < (timeout_sec * 1000) or timeout_sec == 0
                
    def wait_for_server_available(self, timeout = 3000.0):
        '''After client is started this function can be called to ensure server has accepted connection.

        :param timeout: timeout in seconds
        '''
        time_count = 0.0
        wait_granularity = 0.1
        while self._server_status != TincProtocol.StatusTypes.AVAILABLE:
            time.sleep(wait_granularity)
            time_count += wait_granularity
            if time_count > timeout:
                raise TincTimeout("Server still busy after timeout")
        
    # Access to objects by id
    def get_parameter(self, parameter_id, group = None):
        '''Returns a :class:`tinc.parameter.Parameter`  (or similar) with matching name and group that is registered with the TINC client.
        The parameter could have been registered in the current instance of the client, or on the server.

        :param parameter_id: The name of the parameter
        :param group: group name to match. If None, the first parameter_id match is returned'''
        for p in self.parameters:
            if p.id == parameter_id and group is None:
                return p
            elif p.id == parameter_id and p.group == group:
                return p
        return None
    
    def get_parameters(self, group = None):
        '''Returns all the parameters registered with the client that match the group

        :param group: the name of the group to match. If none, all parameters are returned
        :type group: str, None, optional
        '''
        params = []
        for p in self.parameters:
            if group is None or p.group == group:
                params.append(p)
        return params
    
    def get_processor(self, processor_id):
        '''Get :class:`tinc.processor.Processor` registered with client.

        :param processor_id: the name of the processor to match.
        :return: None is there is no match 
        '''
        for p in self.processors:
            if p.id == processor_id:
                return p
        return None
    
    def get_disk_buffer(self, db_id):
        '''Get :class:`tinc.disk_buffer.DiskBuffer` registered with client.

        :param db_id: the name of the disk buffer to match.
        :return: None is there is no match 
        '''
        for db in self.disk_buffers:
            if db.id == db_id:
                return db
        return None
    
    def get_datapool(self, datapool_id):
        '''Get :class:`tinc.data_pool.DataPool` registered with client.

        :param datapool_id: the name of the data pool to match.
        :return: None is there is no match 
        '''
        for dp in self.datapools:
            if dp.id == datapool_id:
                return dp
        return None
    
    def get_parameter_space(self, ps_id):
        '''Get :class:`tinc.parameter_space.ParameterSpace` registered with client.

        :param ps_id: the name of the parameter space to match.
        :return: None is there is no match 
        '''
        for ps in self.parameter_spaces:
            if ps.id == ps_id:
                return ps
        return None
            
    # Network message handling
    
    def create_parameter(self, parameter_type, param_id, group = None, min_value = None, max_value = None, space = None, default_value= None, space_representation_type = None):
        new_param = parameter_type(param_id, group, default_value = default_value, tinc_client = self)

        new_param = self.register_parameter(new_param)
        
        if not min_value is None:
            # avoid callbacks
            new_param._minimum = min_value
        if not max_value is  None:
            # avoid callbacks
            new_param._maximum = max_value
        if not space_representation_type is None:
            new_param.space_representation_type = space_representation_type
        if type(space) == dict:
            new_param.ids = space.values()
            new_param.values = space.keys()
        elif type(space) == list:
            new_param.ids = []
            new_param.values = space
            
        if self.connected:
            self._register_parameter_on_server(new_param)
            self._send_parameter_meta(new_param)
        
        return new_param
    
    def remove_parameter(self, param_id, group = None):
        if not type(param_id) == str:
            group = param_id.group
            param_id = param_id.id
        # TODO complete implementation
        return
    
    def register_parameter(self, new_param):
        for p in self.parameters:
            if p.id == new_param.id and p.group == new_param.group:
                if self.debug:
                    print(f"Parameter already registered: {new_param.id}")
                return p
        self.parameters.append(new_param)
        return new_param
    
    def _send_parameter_value(self, param):
        if not self.connected:
            return
        msg = TincProtocol.TincMessage()
        msg.messageType  = TincProtocol.CONFIGURE
        msg.objectType = TincProtocol.PARAMETER
        config = TincProtocol.ConfigureParameter()
        config.id = param.get_osc_address()
        config.configurationKey = TincProtocol.ParameterConfigureType.VALUE
        value = TincProtocol.ParameterValue()
        # TODO implement all types
        if type(param) == Parameter:
            value.valueFloat = param.value
        elif type(param) == ParameterString:
            value.valueString = param.value
        elif type(param) == ParameterChoice:
            value.valueUint64 = param.value
        elif type(param) == ParameterInt:
            value.valueInt32 = param.value
        elif type(param) == ParameterColor:
            r = TincProtocol.ParameterValue()
            g = TincProtocol.ParameterValue()
            b = TincProtocol.ParameterValue()
            a = TincProtocol.ParameterValue()
            r.valueFloat = param.value[0]
            g.valueFloat = param.value[1]
            b.valueFloat = param.value[2]
            a.valueFloat = param.value[3]
            value.valueList.extend([r,g,b,a])
        elif type(param) == ParameterVec:
            for v in param.value:
                v_ = TincProtocol.ParameterValue()
                v_.valueFloat = v
                value.valueList.extend([v_])
        elif type(param) == ParameterBool or type(param) == Trigger:
            value.valueBool = param.value
            
        config.configurationValue.Pack(value)
        msg.details.Pack(config)
        self._send_message(msg)
        
    def _send_parameter_meta(self, param, fields = None):
        if fields is None:
            fields = ("minimum", "maximum", "space", "space_representation_type")
        # Minimum
        if "minimum" in fields:
            msg = TincProtocol.TincMessage()
            msg.messageType  = TincProtocol.CONFIGURE
            msg.objectType = TincProtocol.PARAMETER
            config = TincProtocol.ConfigureParameter()
            config.id = param.get_osc_address()
            config.configurationKey = TincProtocol.ParameterConfigureType.MIN
            value = TincProtocol.ParameterValue()
            # TODO implement all types
            if type(param) == Parameter:
                value.valueFloat = param.minimum
                config.configurationValue.Pack(value)
                msg.details.Pack(config)
                self._send_message(msg)
            elif type(param) == ParameterString:
                pass
            elif type(param) == ParameterChoice:
                value.valueUint64 = param.minimum
                config.configurationValue.Pack(value)
                msg.details.Pack(config)
                self._send_message(msg)
            elif type(param) == ParameterInt:
                value.valueInt32 = param.minimum
                config.configurationValue.Pack(value)
                msg.details.Pack(config)
                self._send_message(msg)
            elif type(param) == ParameterColor:
                pass
            elif type(param) == ParameterBool or type(param) == Trigger:
                pass
        
        if "maximum" in fields:
            msg = TincProtocol.TincMessage()
            msg.messageType  = TincProtocol.CONFIGURE
            msg.objectType = TincProtocol.PARAMETER
            config = TincProtocol.ConfigureParameter()
            config.id = param.get_osc_address()
            config.configurationKey = TincProtocol.ParameterConfigureType.MAX
            value = TincProtocol.ParameterValue()
            # TODO implement all types
            if type(param) == Parameter:
                value.valueFloat = param.maximum
                config.configurationValue.Pack(value)
                msg.details.Pack(config)
                self._send_message(msg)
            elif type(param) == ParameterString:
                pass
            elif type(param) == ParameterChoice:
                value.valueUint32 = param.maximum
                config.configurationValue.Pack(value)
                msg.details.Pack(config)
                self._send_message(msg)
            elif type(param) == ParameterInt:
                value.valueInt32 = param.maximum
                config.configurationValue.Pack(value)
                msg.details.Pack(config)
                self._send_message(msg)
            elif type(param) == ParameterColor:
                pass
            elif type(param) == ParameterBool or type(param) == Trigger:
                pass
        
        if "space_representation_type" in fields:
            self._send_parameter_space_type(param)
        if "space" in fields:
            self._send_parameter_space(param)
        
    def _send_parameter_space_type(self, param):
        msg = TincProtocol.TincMessage()
        msg.messageType  = TincProtocol.CONFIGURE
        msg.objectType = TincProtocol.PARAMETER
        config = TincProtocol.ConfigureParameter()
        config.id = param.get_osc_address()
        config.configurationKey = TincProtocol.ParameterConfigureType.SPACE_TYPE
        type_value = TincProtocol.ParameterValue()
        type_value.valueInt32 = int(param.space_representation_type)
        config.configurationValue.Pack(type_value)
        msg.details.Pack(config)
        self._send_message(msg)
        
    def _send_parameter_space(self, param):
        if not self.connected:
            return
        msg = TincProtocol.TincMessage()
        msg.messageType  = TincProtocol.CONFIGURE
        msg.objectType = TincProtocol.PARAMETER
        config = TincProtocol.ConfigureParameter()
        config.id = param.get_osc_address()
        config.configurationKey = TincProtocol.ParameterConfigureType.SPACE
        space_values = TincProtocol.ParameterSpaceValues()
        if len(param.ids) != len(param.values) and len(param.ids) != 0:
            print("ERROR parameter ids-values mismatch, not sending to remote")
            return
        # TODO implement all types
        if type(param) == Parameter:
            packed_vals = []
            for v in param.values:
                new_val = TincProtocol.ParameterValue()
                new_val.valueFloat = v
                packed_vals.append(new_val)
            if len(param.ids) > 0: 
                space_values.ids.extend(param.ids)
            space_values.values.extend(packed_vals)
            
            config.configurationValue.Pack(space_values)
            msg.details.Pack(config)
            self._send_message(msg)
        elif type(param) == ParameterString:
            pass
        elif type(param) == ParameterChoice:
            pass
        elif type(param) == ParameterInt:
            packed_vals = []
            for v in param.values:
                new_val = TincProtocol.ParameterValue()
                new_val.valueInt32 = int(v)
                packed_vals.append(new_val)
            space_values.ids.extend(param.ids)
            space_values.values.extend(packed_vals)
            
            config.configurationValue.Pack(space_values)
            msg.details.Pack(config)
            self._send_message(msg)
        elif type(param) == ParameterColor:
            pass
        elif type(param) == ParameterBool or type(param) == Trigger:
            pass
        
    def _register_parameter_on_server(self, param):
        details = TincProtocol.RegisterParameter()
        details.id = param.id
        details.group = param.group
        
        if type(param) == Parameter:
            details.dataType = TincProtocol.PARAMETER_FLOAT
            details.defaultValue.valueFloat = param.default
        if type(param) == ParameterString:
            details.dataType = TincProtocol.PARAMETER_STRING
            details.defaultValue.valueString = param.default
        if type(param) == ParameterInt:
            details.dataType = TincProtocol.PARAMETER_INT32
            details.defaultValue.valueInt32 = param.default
        if type(param) == ParameterChoice:
            details.dataType = TincProtocol.PARAMETER_CHOICE
            details.defaultValue.valueUint64 = param.default
        if type(param) == ParameterBool:
            details.dataType = TincProtocol.PARAMETER_BOOL
            details.defaultValue.valueBool = param.default
        if type(param) == Trigger:
            details.dataType = TincProtocol.PARAMETER_TRIGGER
            details.defaultValue.valueBool = False
            
        msg = TincProtocol.TincMessage()
        msg.messageType = TincProtocol.MessageType.REGISTER
        msg.objectType = TincProtocol.ObjectType.PARAMETER
        msg.details.Pack(details)
        
        self._send_message(msg)
        
    def _register_parameter_from_message(self, details):
        if details.Is(TincProtocol.RegisterParameter.DESCRIPTOR):
            
            details_unpacked = TincProtocol.RegisterParameter()
            details.Unpack(details_unpacked)
            name = details_unpacked.id
            group = details_unpacked.group
            param_type = details_unpacked.dataType
            
            if self.debug:
                print(f"Register parameter {name} {group} {param_type}")
    
            if param_type == TincProtocol.PARAMETER_FLOAT : 
                new_param = Parameter(name, group, default_value = details_unpacked.defaultValue.valueFloat, tinc_client =self)
            elif param_type == TincProtocol.PARAMETER_BOOL: 
                new_param = ParameterBool(name, group, default_value = details_unpacked.defaultValue.valueBool, tinc_client =self)
            elif param_type == TincProtocol.PARAMETER_STRING :
                new_param = ParameterString(name, group, default_value = details_unpacked.defaultValue.valueString, tinc_client =self)
            elif param_type == TincProtocol.PARAMETER_INT32 : 
                new_param = ParameterInt(name, group, default_value = details_unpacked.defaultValue.valueInt32, tinc_client =self)
            elif param_type == TincProtocol.PARAMETER_VEC3F :
                new_param = ParameterVec(name, group, 3, tinc_client=self)
            elif param_type == TincProtocol.PARAMETER_VEC4F :
                new_param = ParameterVec(name, group, 4, tinc_client=self)
            elif param_type == TincProtocol.PARAMETER_COLORF :
                l = [v.valueFloat for v in details_unpacked.defaultValue.valueList]
                new_param = ParameterColor(name, group, default_value = l, tinc_client =self)
            elif param_type == TincProtocol.PARAMETER_POSED :
                new_param = None
                pass
            elif param_type == TincProtocol.PARAMETER_MENU :
                #new_param = ParameterM(name, group, default_value = details_unpacked.defaultValue.valueUint64, tinc_client =self)
                
                new_param = None
                pass
            elif param_type == TincProtocol.PARAMETER_CHOICE :
                new_param = ParameterChoice(name, group, default_value = details_unpacked.defaultValue.valueUint64, tinc_client =self)
                pass
            elif param_type == TincProtocol.PARAMETER_TRIGGER :
                new_param = Trigger(name, group)
                pass
            elif param_type == TincProtocol.PARAMETER_INT64 :
                #new_param = ParameterM(name, group, default_value = details_unpacked.defaultValue.valueUint64, tinc_client =self)
                
                new_param = None
                pass
            elif param_type == TincProtocol.PARAMETER_INT16 :
                #new_param = ParameterM(name, group, default_value = details_unpacked.defaultValue.valueUint64, tinc_client =self)
                
                new_param = None
                pass
            elif param_type == TincProtocol.PARAMETER_INT8 :
                #new_param = ParameterM(name, group, default_value = details_unpacked.defaultValue.valueUint64, tinc_client =self)
                
                new_param = None
                pass
            elif param_type == TincProtocol.PARAMETER_UINT64 :
                #new_param = ParameterM(name, group, default_value = details_unpacked.defaultValue.valueUint64, tinc_client =self)
                
                new_param = None
                pass
            elif param_type == TincProtocol.PARAMETER_UINT32 :
                #new_param = ParameterM(name, group, default_value = details_unpacked.defaultValue.valueUint64, tinc_client =self)
                
                new_param = None
                pass
            elif param_type == TincProtocol.PARAMETER_UINT16 :
                #new_param = ParameterM(name, group, default_value = details_unpacked.defaultValue.valueUint64, tinc_client =self)
                
                new_param = None
                pass
            elif param_type == TincProtocol.PARAMETER_UINT8 :
                #new_param = ParameterM(name, group, default_value = details_unpacked.defaultValue.valueUint64, tinc_client =self)
                
                new_param = None
                pass
            elif param_type == TincProtocol.PARAMETER_DOUBLE :
                #new_param = ParameterM(name, group, default_value = details_unpacked.defaultValue.valueUint64, tinc_client =self)
                
                new_param = None
                pass
            else:
                new_param = None
                
            if new_param:
                self.register_parameter(new_param)
                if self.debug:
                    print("Parameter already registered.")
            else:
                print(f"Unsupported parameter type for id: {name} group: {group}")
        else:
            print("ERROR: Unexpected payload in REGISTER PARAMETER")
                
    def _configure_parameter_from_message(self, details):
        if not details.Is(TincProtocol.ConfigureParameter.DESCRIPTOR):
            print("ERROR unexpected paylod in Configure parameter. Aborting.")
            return
        param_details = TincProtocol.ConfigureParameter()
        details.Unpack(param_details)
  
        param_osc_address = param_details.id
        param_command = param_details.configurationKey
        
        configured = True
        if self.debug:
            print(f"_configure_parameter_from_message {param_osc_address} {param_command}")
        for param in self.parameters:
            if param.get_osc_address() == param_osc_address:
                if param_command == TincProtocol.ParameterConfigureType.VALUE:
                    configured = configured and param._set_value_from_message(param_details.configurationValue)
                elif param_command == TincProtocol.ParameterConfigureType.MIN:
                    configured = configured and param._set_min_from_message(param_details.configurationValue)
                elif param_command == TincProtocol.ParameterConfigureType.MAX:
                    configured = configured and param._set_max_from_message(param_details.configurationValue)
                elif param_command == TincProtocol.ParameterConfigureType.SPACE:
                    configured = configured and param._set_space_from_message(param_details.configurationValue)
                elif param_command == TincProtocol.ParameterConfigureType.SPACE_TYPE:
                    configured = configured and param._set_space_representation_type_from_message(param_details.configurationValue)
                else:
                    print("Unrecognized Parameter Configure command")
        
        if self.debug:
            print("_configure_parameter_from_message done")
        if not configured:
            print("Parameter configuration failed")
            
    # ParameterSpace messages ------------------
    def register_parameter_space(self, new_ps):
        found = False
        for ps in self.parameter_spaces:
            if ps.id == new_ps.id:
                if self.debug:
                    print(f"ParameterSpace already registered: '{new_ps.id}'")
                found = True
                break
        if not found:
            self.parameter_spaces.append(new_ps)
            #print(f"REGISTER ParameterSpace: '{new_ps}'")
    
    def _register_parameter_space_from_message(self, details):
        # print('register ps')
        if details.Is(TincProtocol.RegisterParameterSpace.DESCRIPTOR):
            ps_details = TincProtocol.RegisterParameterSpace()
            details.Unpack(ps_details)
            ps_id = ps_details.id
            self.register_parameter_space(ParameterSpace(ps_id, tinc_client = self))
                
    def _configure_parameter_space_from_message(self, details):
        param_details = TincProtocol.ConfigureParameterSpace()
        details.Unpack(param_details)
  
        ps_id = param_details.id
        
        configured = True
        if self.debug:
            print("Processing _configure_parameter_space_from_message")
        for ps in self.parameter_spaces:
            if ps_id == ps.id:
                ps_command = param_details.configurationKey
                if ps_command == TincProtocol.ParameterSpaceConfigureType.ADD_PARAMETER:
                    param_value = TincProtocol.ParameterValue()
                    param_details.configurationValue.Unpack(param_value)
                    param_id = param_value.valueString
                    for p in self.parameters:
                        if p.get_osc_address() == param_id:
                            if self.debug:
                                print(f"Registering {param_id} for {ps}")
                            ps.register_parameter(p)
                            configured = True
                            break
                elif ps_command == TincProtocol.ParameterSpaceConfigureType.REMOVE_PARAMETER:
                    param_value = TincProtocol.ParameterValue()
                    param_details.configurationValue.Unpack(param_value)
                    param_id = param_value.valueString
                    for p in self.parameters:
                        if p.get_osc_address() == param_id:
                            ps.remove_parameter(p)
                            configured = True
                            break
                elif ps_command == TincProtocol.ParameterSpaceConfigureType.CURRENT_TEMPLATE:
                    template_val = TincProtocol.ParameterValue()
                    param_details.configurationValue.Unpack(template_val)
                    if template_val.nctype == VariantType.VARIANT_STRING:
                        # Use internal member to avoid checks and warnings in the setter function
                        ps._path_template = template_val.valueString
                    else:
                        print("ERROR: Unexpected data type for TincProtocol.ParameterSpaceConfigureType.CURRENT_TEMPLATE")
                elif ps_command == TincProtocol.ParameterSpaceConfigureType.ROOT_PATH:
                    root_value = TincProtocol.ParameterValue()
                    param_details.configurationValue.Unpack(root_value)
                    if root_value.nctype == VariantType.VARIANT_STRING:
                        # Use internal member to avoid checks and warnings in the setter function
                        ps._local_root_path = root_value.valueString
                    else:
                        print("ERROR: Unexpected data type for TincProtocol.ParameterSpaceConfigureType.ROOT_PATH")
                elif ps_command == TincProtocol.ParameterSpaceConfigureType.CACHE_PATH:
                    dist_path = TincProtocol.DistributedPath()
                    param_details.configurationValue.Unpack(dist_path)
                    if ps._cache_manager is None:
                        ps._cache_manager = CacheManager(dist_path.relativePath)
                        if dist_path.filename != ps._cache_manager._metadata_file:
                            print(f"Unexpected cache filename: {dist_path.filename}. Expected: {ps._cache_manager._metadata_file}")
                            
                        ps._cache_manager._cache_root = dist_path.rootPath
                        ps._cache_manager._cache_dir = dist_path.relativePath
                        ps._cache_manager._metadata_file = dist_path.filename
                    else:
                        ps._cache_manager._cache_root = dist_path.rootPath
                        ps._cache_manager._cache_dir = dist_path.relativePath
                        ps._cache_manager._metadata_file = dist_path.filename
                elif ps_command == TincProtocol.ParameterSpaceConfigureType.PS_DOCUMENTATION:
                    ps.documentation = str(param_details.configurationValue)
                else:
                    print("Unrecognized ParameterSpace Configure command " + str(ps_command))
                
        if not configured:
            print("ParameterSpace configuration failed")
        
    def register_processor(self, message):
        if message.Is(TincProtocol.RegisterProcessor.DESCRIPTOR):
            proc_details = TincProtocol.RegisterProcessor()
            message.Unpack(proc_details)
            processor_type = proc_details.type
            proc_id  = proc_details.id
            # print(name)
            input_dir = proc_details.inputDirectory
            # print(input_dir)
            input_files = proc_details.inputFiles
            # print(input_files)
            output_dir = proc_details.outputDirectory
            # print(output_dir)
            output_files = proc_details.outputFiles
            # print(output_files)
            running_dir = proc_details.runningDirectory
            # print(running_dir)
            
            if processor_type == TincProtocol.CPP:
                new_processor = ProcessorCpp(proc_id, input_dir, input_files, output_dir, output_files, running_dir)
            elif processor_type ==  TincProtocol.DATASCRIPT:
                new_processor = ProcessorScript(proc_id, input_dir, input_files, output_dir, output_files, running_dir)
            elif processor_type == TincProtocol.CHAIN:
                new_processor = ComputationChain(proc_id, input_dir, input_files, output_dir, output_files, running_dir)
            else:
                new_processor = None
                print(f"Unexpected processor type {processor_type}")
            
            found = False
            for proc in self.processors:
                if proc.id == proc_id:
                    if type(proc).__name__ == type(new_processor).__name__:
                        proc.id = proc_id
                        proc.input_dir = input_dir
                        proc.output_dir = output_dir
                        proc.running_dir = running_dir
                        print(f"Updated processor '{proc_id}'")
                        found = True
                        break
                    else:
                        print(f"ERROR processor type mismatch! {proc_id}")
                
            if not found and new_processor:
                new_processor.documentation = proc_details.documentation
                self.processors.append(new_processor)
                #print(f"Registered processor '{proc_id}'")
        else:
            print("Unexpected payload in Register Processor")
        
    def _configure_processor(self, details):
        if details.Is(TincProtocol.ConfigureProcessor.DESCRIPTOR):
            proc_details = TincProtocol.ConfigureProcessor()
            details.Unpack(proc_details)
            proc_id= proc_details.id
            count = proc_details.configurationKey
            for proc in self.processors:
                if proc.id == proc_id:
                    proc.configuration.update({proc_details.configurationKey: proc_details.configurationValue})
                
    def _register_datapool_from_message(self, details):
        if details.Is(TincProtocol.RegisterDataPool.DESCRIPTOR):
            
            dp_details = TincProtocol.RegisterDataPool()
            details.Unpack(dp_details)
            dp_id = dp_details.id
            ps_id = dp_details.parameterSpaceId
            slice_cache_dir = dp_details.cacheDirectory
            
            # print(f"Register Datapool {dp_id}")
            found = False
            for dp in self.datapools:
                if dp.id == dp_id:
                    if self.debug:
                        print(f"DataPool already registered: '{dp_id}'")
                    found = True
                    break
            
            if not found:
                ps = self.get_parameter_space(ps_id)
                if dp_details.type ==  TincProtocol.DataPoolTypes.DATAPOOLTYPE_JSON:
                    new_datapool = DataPoolJson(dp_id, ps, slice_cache_dir, tinc_client=self)
                elif dp_details.type ==  TincProtocol.DataPoolTypes.DATAPOOLTYPE_NETCDF:
                    print("Warning: Remote DataPool Netcdf not fully supported")
                    # TODO implement
                    new_datapool = DataPool(dp_id, ps, slice_cache_dir, tinc_client=self)
                else:
                    new_datapool = DataPool(dp_id, ps, slice_cache_dir, tinc_client=self)
                new_datapool.documentation = dp_details.documentation
                self.datapools.append(new_datapool)
        else:
            print("Unexpected payload in Register Datapool")
            
    def _configure_datapool(self, details):
        if details.Is(TincProtocol.ConfigureDataPool.DESCRIPTOR):
            dp_details = TincProtocol.ConfigureDataPool()
            details.Unpack(dp_details)
            dp_id = dp_details.id
            for dp in self.datapools:
                if dp.id == dp_id:
                    if dp_details.configurationKey == TincProtocol.DataPoolConfigureType.SLICE_CACHE_DIR:
                        if dp_details.configurationValue.Is(TincProtocol.ParameterValue.DESCRIPTOR):
                            value = TincProtocol.ParameterValue()
                            dp_details.configurationValue.Unpack(value)
                            dp.slice_cache_dir = value.valueString
                    elif dp_details.configurationKey == TincProtocol.DataPoolConfigureType.DP_DOCUMENTATION:
                        # FIXME ensure value is string
                        dp.documentation = dp_details.configurationValue
        else:
            print("Unexpected payload in Configure Datapool")
        
    # Disk buffer messages ------------------
    def register_disk_buffer(self, db):
        # TODO is this enough checking, or should we check for ids as well?
        if db in self.disk_buffers:
            return db
        self.disk_buffers.append(db)
        self._register_disk_buffer_on_server(db)

    def _register_disk_buffer_from_message(self, details):
        
        if details.Is(TincProtocol.RegisterDiskBuffer.DESCRIPTOR):
            
            db_details = TincProtocol.RegisterDiskBuffer()
            details.Unpack(db_details)
            disk_buffer_id= db_details.id
            
            found = False
            for db in self.disk_buffers:
                if db.id == disk_buffer_id:
                    if self.debug:
                        if not db_details.type == db.type:
                            print(f"DiskBuffer registered: '{disk_buffer_id}' ERROR: type mismatch")
                        else:
                            print(f"DiskBuffer already registered: '{disk_buffer_id}'")
                    found = True
                    break
        
            if not found:
                new_db = None
                distributed_path = db_details.path
                if db_details.type == TincProtocol.JSON:
                    new_db = DiskBufferJson(disk_buffer_id,
                                        distributed_path.filename, distributed_path.relativePath, distributed_path.rootPath,
                                        tinc_client= self)
                elif db_details.type == TincProtocol.NETCDF:
                    new_db = DiskBufferNetCDFData(disk_buffer_id,
                                        distributed_path.filename, distributed_path.relativePath, distributed_path.rootPath,
                                        tinc_client= self)
                elif db_details.type == TincProtocol.IMAGE:
                    new_db = DiskBufferImage(disk_buffer_id,
                                        distributed_path.filename, distributed_path.relativePath, distributed_path.rootPath,
                                        tinc_client= self)
                elif db_details.type == TincProtocol.BINARY:
                    new_db = DiskBufferBinary(disk_buffer_id,
                                        distributed_path.filename, distributed_path.relativePath, distributed_path.rootPath,
                                        tinc_client= self)
                elif db_details.type == TincProtocol.TEXT:
                    new_db = DiskBufferText(disk_buffer_id,
                                        distributed_path.filename, distributed_path.relativePath, distributed_path.rootPath,
                                        tinc_client= self)
                if new_db is not None:
                    new_db.documentation = db_details.documentation
                    self.disk_buffers.append(new_db)
                else:
                    self._log.append("Disk buffer type not recognized. Not creating DiskBuffer")
        else:
            print("Unexpected payload in Register DiskBuffer")
    
    def _register_disk_buffer_on_server(self, db):
        details = TincProtocol.RegisterDiskBuffer()
        details.id = db.id
        
        if type(db) == DiskBufferImage:
            details.type = TincProtocol.IMAGE
        elif type(db) == DiskBufferJson:
            details.type = TincProtocol.JSON
        elif type(db) == DiskBufferNetCDFData:
            details.type = TincProtocol.NETCDF
        elif type(db) == DiskBufferText:
            details.type = TincProtocol.TEXT
        elif type(db) == DiskBufferBinary:
            details.type = TincProtocol.BINARY
        else:
            print("Unsupported Diskbuffer type. Not registered on server.")
            return
            
        details.path.filename = db.get_base_filename()
        details.path.relativePath = db.get_relative_path()
        details.path.rootPath = db.get_root_path()

        msg = TincProtocol.TincMessage()
        msg.messageType = TincProtocol.MessageType.REGISTER
        msg.objectType = TincProtocol.ObjectType.DISK_BUFFER
        msg.details.Pack(details)
        
        self._send_message(msg)
        db.tinc_client = self


    def _configure_disk_buffer(self, details):
        if self.debug:
            print("Processing Configure disk buffer")
        if details.Is(TincProtocol.ConfigureDiskBuffer.DESCRIPTOR):
            db_details = TincProtocol.ConfigureDiskBuffer()
            details.Unpack(db_details)
            db_id = db_details.id
            for db in self.disk_buffers:
                if db.id == db_id:
                    if db_details.configurationKey == TincProtocol.DiskBufferConfigureType.CURRENT_FILE:
                        if db_details.configurationValue.Is(TincProtocol.ParameterValue.DESCRIPTOR):
                            value = TincProtocol.ParameterValue()
                            db_details.configurationValue.Unpack(value)
                            
                            if value.valueString == '':
                                db._data = None
                                db._filename = ''
                            else:
                                db.load_data(value.valueString, False)

                    elif db_details.configurationKey == TincProtocol.DiskBufferConfigureType.DB_DOCUMENTATION:
                        db.documentation = db_details.configurationValue
        else:
            print("Unexpected payload in Configure Datapool")
            
    def _send_disk_buffer_current_filename(self, disk_buffer, filename):
        if not self.connected:
            return
        msg = TincProtocol.TincMessage()
        msg.messageType  = TincProtocol.CONFIGURE
        msg.objectType = TincProtocol.DISK_BUFFER
        config = TincProtocol.ConfigureDiskBuffer()
        config.id = disk_buffer.id
        config.configurationKey = TincProtocol.DiskBufferConfigureType.CURRENT_FILE
        value = TincProtocol.ParameterValue()
        value.valueString = filename
        config.configurationValue.Pack(value)
        msg.details.Pack(config)
        print("sent disk buffer filename: " + filename)
        self._send_message(msg)

# ------------------------------------------------------
    def _process_object_command_reply(self, message):
        command_details = TincProtocol.Command()
        
        self._log.append("Reply")
        if message.details.Is(TincProtocol.Command.DESCRIPTOR):
            message.details.Unpack(command_details)
            
            message_id = command_details.message_id
            # TODO we should verify the object id somehow
            if self.debug:
                print(f"**** Got reply for id {message_id} before lock")
            
            try:
                with self.pending_requests_lock:
                    
                    if self.debug:
                        print(f"**** Got reply for id {message_id} after lock")
                    self._log.append(f"Got reply for id {message_id}")
                    command_data = self.pending_requests.pop(message_id)
                with self.pending_lock:
                    self.pending_replies[message_id] = [command_details.details, command_data]
            except KeyError:
                print(f"Unexpected command reply: {message_id}")
        else:
            self._log.append("Unsupported payload in Command reply")
            print("Unsupported payload in Command reply")
        
        
    def _process_register_command(self, message):
        if self.debug:
            print(f"_process_register_command {message.objectType}")
        if message.objectType == TincProtocol.ObjectType.PARAMETER:
            self._register_parameter_from_message(message.details)
        elif message.objectType == TincProtocol.ObjectType.PROCESSOR:
            self.register_processor(message.details)
        elif message.objectType == TincProtocol.ObjectType.DISK_BUFFER:
            self._register_disk_buffer_from_message(message.details)
        elif message.objectType == TincProtocol.ObjectType.DATA_POOL:
            self._register_datapool_from_message(message.details)
        elif message.objectType == TincProtocol.ObjectType.PARAMETER_SPACE:
            self._register_parameter_space_from_message(message.details)
        else:
            print("Unexpected Register command")
    
    def _process_request_command(self, message):
        pass
    
    def _process_remove_command(self, message):
        pass
    
    def _process_configure_command(self, message):
        if self.debug:
            print(f"_process_configure_command {message.objectType}")
            
        if message.objectType == TincProtocol.PARAMETER:
            self._configure_parameter_from_message(message.details)
        elif message.objectType == TincProtocol.PROCESSOR:
            self._configure_processor(message.details)
        elif message.objectType == TincProtocol.DISK_BUFFER:
            self._configure_disk_buffer(message.details)
        elif message.objectType == TincProtocol.DATA_POOL:
            self._configure_datapool(message.details)
        elif message.objectType == TincProtocol.PARAMETER_SPACE:
            self._configure_parameter_space_from_message(message.details)
        else:
            print("Unexpected Configure command")
            
    def _process_command_command(self, message):
        # TODO implement
        pass
        
    def _process_ping_command(self, message):
        # TODO implement
        pass
    
    def _process_pong_command(self, message):
        # TODO implement
        pass

    def _process_barrier_request(self, message):
        command_details = TincProtocol.Command()
        if message.details.Is(TincProtocol.Command.DESCRIPTOR):
            message.details.Unpack(command_details)
            with self._barrier_queues_lock:
                print(f"_process_barrier_request added barrier {command_details.message_id}")
                self._barrier_requests.append(command_details.message_id)
    
    def _process_barrier_unlock(self, message):
        command_details = TincProtocol.Command()
        if message.details.Is(TincProtocol.Command.DESCRIPTOR):
            message.details.Unpack(command_details)
            with self._barrier_queues_lock:
                print(f"_process_barrier_unlock added barrier unlock {command_details.message_id}")
                self._barrier_unlocks.append(command_details.message_id)
    
    def _process_status(self, message):
        details = message.details
        if details.Is(TincProtocol.StatusMessage.DESCRIPTOR):
            status_details = TincProtocol.StatusMessage()
            details.Unpack(status_details)
            self._server_status =  status_details.status
    
    def _process_working_path(self, message):
        details = message.details
        if details.Is(TincProtocol.TincPath.DESCRIPTOR):
            path_details = TincProtocol.TincPath()
            details.Unpack(path_details)
            self._working_path =  path_details.path
            print("Set working path to " + self._working_path)
        
    # Send request commands
        
    def request_parameters(self):
        tp = TincProtocol.TincMessage()
        tp.messageType  = TincProtocol.REQUEST
        tp.objectType = TincProtocol.PARAMETER
        obj_id = TincProtocol.ObjectId()
        obj_id.id = ""
        tp.details.Pack(obj_id)
        self._send_message(tp)

    def request_processors(self):
        tp = TincProtocol.TincMessage()
        tp.messageType  = TincProtocol.REQUEST
        tp.objectType = TincProtocol.PROCESSOR
        obj_id = TincProtocol.ObjectId()
        obj_id.id = ""
        tp.details.Pack(obj_id)
        self._send_message(tp)
        
    def request_disk_buffers(self):
        tp = TincProtocol.TincMessage()
        tp.messageType  = TincProtocol.REQUEST
        tp.objectType = TincProtocol.DISK_BUFFER
        obj_id = TincProtocol.ObjectId()
        obj_id.id = ""
        tp.details.Pack(obj_id)
        self._send_message(tp)
    
    def request_data_pools(self):
        tp = TincProtocol.TincMessage()
        tp.messageType  = TincProtocol.REQUEST
        tp.objectType = TincProtocol.DATA_POOL
        obj_id = TincProtocol.ObjectId()
        obj_id.id = ""
        tp.details.Pack(obj_id)
        self._send_message(tp)
    
    def request_parameter_spaces(self):
        tp = TincProtocol.TincMessage()
        tp.messageType  = TincProtocol.REQUEST
        tp.objectType = TincProtocol.PARAMETER_SPACE
        obj_id = TincProtocol.ObjectId()
        obj_id.id = ""
        tp.details.Pack(obj_id)
        self._send_message(tp)
        
    def _get_command_id(self):
        self.request_count_lock.acquire()
        command_id = self.pending_requests_count
        self.pending_requests_count += 1
        if self.pending_requests_count == 4294967295:
            self.pending_requests_count = 0
        self.request_count_lock.release()
        return command_id
    
    def _wait_for_reply(self, request_number, timeout_sec= 30):
        start_time = time.time()
        self.pending_lock.acquire()
        while not request_number in self.pending_replies:
            self.pending_lock.release()
            time.sleep(0.05)
            if (time.time() - start_time) > timeout_sec:
                raise TincTimeout("Timeout.")
            self.pending_lock.acquire()
        reply = self.pending_replies.pop(request_number)
        self.pending_lock.release()
   
        return reply
    
    def _command_parameter_choice_elements(self, parameter, timeout=30):
        
        parameter_addr = parameter.get_osc_address()
        msg = TincProtocol.TincMessage()
        msg.messageType  = TincProtocol.COMMAND
        msg.objectType = TincProtocol.PARAMETER
        command = TincProtocol.Command()
        command.id.id = parameter_addr
        request_number = self._get_command_id()
        command.message_id = request_number
        
        slice_details = TincProtocol.ParameterRequestChoiceElements()
                
        command.details.Pack(slice_details)
        msg.details.Pack(command)
        
        # TODO check possible race condiiton in pending_requests count. Does the GIL make it safe?
        self.pending_requests[request_number] = [parameter]

        self._send_message(msg)
        
        if self.debug:
            print(f"Sent command: {request_number}")
        try:
            command_details, user_data = self._wait_for_reply(request_number, timeout)
        except TincTimeout as tm:
            self.pending_requests.pop(request_number)
            raise tm

        if command_details.Is(TincProtocol.ParameterRequestChoiceElementsReply.DESCRIPTOR):
            slice_reply = TincProtocol.ParameterRequestChoiceElementsReply()
            command_details.Unpack(slice_reply)
            print(slice_reply.elements)
            user_data[0].set_elements(slice_reply.elements)
            
    def _command_parameter_space_get_current_relative_path(self, ps, timeout=30):
        
        msg = TincProtocol.TincMessage()
        msg.messageType  = TincProtocol.COMMAND
        msg.objectType = TincProtocol.PARAMETER_SPACE
        command = TincProtocol.Command()
        command.id.id = ps.id
        request_number = self._get_command_id()
        command.message_id = request_number
        
        slice_details = TincProtocol.ParameterSpaceRequestCurrentPath()
                
        command.details.Pack(slice_details)
        msg.details.Pack(command)
        
        # TODO check possible race conditon in pending_requests count. Does the GIL make it safe?
        self.pending_requests[request_number] = [ps]

        self._send_message(msg)
          
        try:
            command_details, user_data = self._wait_for_reply(request_number, timeout)
        except TincTimeout as tm:
            self.pending_requests.pop(request_number)
            raise tm

        if command_details.Is(TincProtocol.ParameterSpaceRequestCurrentPathReply.DESCRIPTOR):
            slice_reply = TincProtocol.ParameterSpaceRequestCurrentPathReply()
            command_details.Unpack(slice_reply)
            return slice_reply.path
        
    def _command_parameter_space_get_root_path(self, ps, timeout=30):
        
        msg = TincProtocol.TincMessage()
        msg.messageType  = TincProtocol.COMMAND
        msg.objectType = TincProtocol.PARAMETER_SPACE
        command = TincProtocol.Command()
        command.id.id = ps.id
        request_number = self._get_command_id()
        command.message_id = request_number
        
        slice_details = TincProtocol.ParameterSpaceRequestRootPath()
                
        command.details.Pack(slice_details)
        msg.details.Pack(command)
        
        # TODO check possible race condiiton in pending_requests count. Does the GIL make it safe?
        self.pending_requests[request_number] = [ps]

        self._send_message(msg)
            
        try:
            command_details, user_data = self._wait_for_reply(request_number, timeout)
        except TincTimeout as tm:
            self.pending_requests.pop(request_number)
            raise tm
            
        if command_details.Is(TincProtocol.ParameterSpaceRequestRootPathReply.DESCRIPTOR):
            slice_reply = TincProtocol.ParameterSpaceRequestRootPathReply()
            command_details.Unpack(slice_reply)
            return slice_reply.path
        
    def _command_datapool_slice_file(self, datapool_id, field, sliceDimensions, timeout=30):
        
        msg = TincProtocol.TincMessage()
        msg.messageType  = TincProtocol.COMMAND
        msg.objectType = TincProtocol.DATA_POOL
        command = TincProtocol.Command()
        command.id.id = datapool_id
        command.message_id =  self._get_command_id()
        request_number = command.message_id
        
        slice_details = TincProtocol.DataPoolCommandSlice()
        slice_details.field = field
        
        if type(sliceDimensions) == str:
            slice_details.dimension[:] = [sliceDimensions]
        elif type(sliceDimensions) == list and len(sliceDimensions) > 0:
            for dim in sliceDimensions:
                slice_details.dimension.append(dim)
                
        command.details.Pack(slice_details)
        msg.details.Pack(command)
        
        if self.debug:
            print(f"command datapools send command {command.message_id}")
        # TODO check possible race condiiton in pending_requests count
        self.pending_requests[command.message_id] = [datapool_id]

        self._send_message(msg)
            
        # print(f"Sent command: {request_number}")
        try:
            command_details, user_data = self._wait_for_reply(request_number, timeout)
        except TincTimeout as tm:
            self.pending_requests.pop(request_number)
            raise tm
            
        if command_details.Is(TincProtocol.DataPoolCommandSliceReply.DESCRIPTOR):
            slice_reply = TincProtocol.DataPoolCommandSliceReply()
            command_details.Unpack(slice_reply)
            return slice_reply.filename
        else:
            return None
        
    def _command_datapool_get_files(self, datapool_id, timeout=30):
        
        msg = TincProtocol.TincMessage()
        msg.messageType  = TincProtocol.COMMAND
        msg.objectType = TincProtocol.DATA_POOL
        command = TincProtocol.Command()
        command.id.id = datapool_id
        command.message_id =  self._get_command_id()
        request_number = command.message_id
        
        command_details = TincProtocol.DataPoolCommandCurrentFiles()
                
        command.details.Pack(command_details)
        msg.details.Pack(command)
        
        # TODO check possible race condiiton in pending_requests count
        if self.debug:
            print(f"command datapools send command {command.message_id}")
        self.pending_requests[command.message_id] = [datapool_id]

        self._send_message(msg)
            
        if self.debug:
            print(f"Sent datapool get files command: {request_number}")
        try:
            command_details, user_data = self._wait_for_reply(request_number, timeout)
        except TincTimeout as tm:
            self.pending_requests.pop(request_number)
            raise tm
        
        if command_details.Is(TincProtocol.DataPoolCommandCurrentFilesReply.DESCRIPTOR):
            command_reply = TincProtocol.DataPoolCommandCurrentFilesReply()
            command_details.Unpack(command_reply)
            return command_reply.filenames
        else:
            return None
        
    def synchronize(self):
        self.send_metadata()
        
        self.request_parameters()
        self.request_parameter_spaces()
        self.request_processors()
        self.request_disk_buffers()
        self.request_data_pools()

    def _send_goodbye(self):
        if not self.connected:
            return
        tp = TincProtocol.TincMessage()
        tp.messageType  = TincProtocol.GOODBYE
        tp.objectType = TincProtocol.GLOBAL
        self._send_message(tp)
        
    def _process_goodbye(self, client_address, address: str, *args: List[Any]):
        # TODO we need to define behavior. Should client stay alive and then
        # restore the state on the server if it comes up again?
        print("Got GOODBYE message, stopping TincClient")
        self.stop()

    def _send_message(self, msg):
        size = msg.ByteSize()
        ser_size = struct.pack('N', size)
        if not self.socket:
            if self.debug:
                print("No server connected. Message not sent")
            return
        try:
            num_bytes = self.socket.send(ser_size + msg.SerializeToString())
            if self.debug:
                print(f'message sent {num_bytes} bytes')
        except BrokenPipeError as e:
            # Disconnect
            self.running = False
            self.connected = False
            self.x.join()
            self.socket.close()
            self.socket = None
            print("Broken pipe to server. Client is disconnected")
            if self.debug:
                print(e.strerror)

        
    # Server ---------------
    def _server_thread_function(self, ip: str, port: int):
#         print("Starting on port " + str(port))
        al_message = b''
        pc_message = TincProtocol.TincMessage()
        
        failed_attempts = 0
        while self.running:
            if not self.connected:
                self.socket = None
                try:
                    # Attempt a connection
                    if failed_attempts == 1:
                        if self.debug:
                            print(f"Attempt connection. {ip}:{port}")
                    failed_attempts += 1
                    if failed_attempts == 100:
                        print("Connection failed.")
                        self.stop()
                        return
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.setblocking(True)
                    s.connect((ip, port))
                except:
                    # Connection was not possible, try later
                    time.sleep(1.0)
                    continue
                    
                s.settimeout(10.0)
                if self.debug:
                    print("Connected, sending handshake.")
                hs_message = bytearray()
                hs_message.append(commands['HANDSHAKE'])
                hs_message += struct.pack("L", tinc_client_version)
                hs_message += struct.pack("L", tinc_client_revision)
                s.send(hs_message)
                
                hs_message = Message(s.recv(5))
                command = hs_message.get_byte()
                if command == commands['HANDSHAKE_ACK']:
                    self.server_version = 0
                    self.server_revision = 0
                    if len(hs_message.remaining_bytes()) > 3:
                        self.server_version = hs_message.get_uint16()
                        
                    if len(hs_message.remaining_bytes()) > 1:
                        self.server_revision = hs_message.get_uint16()
                    if self.server_version != tinc_client_version:
                        raise ValueError("Tinc protocol version mismatch")
                    if self.server_revision != tinc_client_revision:
                        print("WARNING: protocol revision mismatch")
                    
                    self.connected = True
                    self.socket = s
                    failed_attempts = 0
                    self.synchronize()
                    print(f"Connected to {ip}:{port}. Server version {self.server_version} revision {self.server_revision}")
                else:
                    print("Expected HANDSHAKE_ACK. CLosing connection. Got {message[0]}")
            else:
                new_message = b''
                try:
                    new_message = self.socket.recv(1024)
                    
                except ConnectionResetError:
                    print("Connection closed.")
                    self.socket = None
                    self.connected = False;
                    
                except ConnectionAbortedError:
                    print("Connection closed.")
                    self.connected = False;
                except socket.timeout:
                    continue
                
                al_message = al_message + new_message
                while len(al_message) > 8:
                    message_size = struct.unpack("N", al_message[:8])[0]
                    if self.debug:
                        print(f'received raw {message_size}')
                    if len(al_message) < message_size + 8:
                        break
                    
                    num_bytes = pc_message.ParseFromString(al_message[8:8+message_size])
                    
                    #print(f'unpacked {num_bytes}')
                    if num_bytes > 0:
                        if self.debug:
                            print(f"Processing message bytes:{num_bytes}")
                        
                        if pc_message.messageType == TincProtocol.REQUEST:
                            self._process_request_command(pc_message)
                        elif pc_message.messageType == TincProtocol.REMOVE:
                            self._process_remove_command(pc_message)
                        elif pc_message.messageType == TincProtocol.REGISTER:
                            self._process_register_command(pc_message)
                        elif pc_message.messageType == TincProtocol.CONFIGURE:
                            self._process_configure_command(pc_message)
                        elif pc_message.messageType == TincProtocol.COMMAND:
                            self._process_command_command(pc_message)
                        elif pc_message.messageType == TincProtocol.COMMAND_REPLY:
                            self._process_object_command_reply(pc_message)
                        elif pc_message.messageType == TincProtocol.PING:
                            self._process_ping_command(pc_message)
                        elif pc_message.messageType == TincProtocol.PONG:
                            self._process_pong_command(pc_message)
                        elif pc_message.messageType == TincProtocol.GOODBYE:
                            self._process_goodbye(pc_message)
                        elif pc_message.messageType == TincProtocol.BARRIER_REQUEST:
                            self._process_barrier_request(pc_message)
                        elif pc_message.messageType == TincProtocol.BARRIER_UNLOCK:
                            self._process_barrier_unlock(pc_message)
                        elif pc_message.messageType == TincProtocol.STATUS:
                            self._process_status(pc_message)
                        elif pc_message.messageType == TincProtocol.TINC_WORKING_PATH:
                            self._process_working_path(pc_message)
                        else:
                            print("Unknown message")
                        al_message = al_message[message_size + 8:]
                        if self.debug:
                            print(f"Processed Byte_size {message_size}:{pc_message.ByteSize()}" )
                    else:
                        break
                            

                        
        print("Closed TINC client")                

    def send_metadata(self): 
        msg = TincProtocol.TincMessage()
        msg.messageType  = TincProtocol.TINC_CLIENT_METADATA
        msg.objectType = TincProtocol.GLOBAL
        metadata = TincProtocol.ClientMetaData()
        metadata.clientHost = socket.gethostname()
        
        msg.details.Pack(metadata)

        self._send_message(msg)

    def print(self): 
        '''Print details about this TincClient object. Prints details of all registered objects.
        '''
        print(str(self))
              
