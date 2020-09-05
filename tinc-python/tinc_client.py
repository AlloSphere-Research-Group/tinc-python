import threading
import time
import socket
from typing import List, Any
import struct
from threading import Lock

from parameter import Parameter, ParameterString, ParameterInt, ParameterBool
from processor import CppProcessor, ScriptProcessor, ComputationChain
from parameter_server import ParameterServer
from datapool import DataPool
from parameter_space import ParameterSpace
from message import Message

commands = {
    "HANDSHAKE" : 0x01,
    "HANDSHAKE_ACK" : 0x02,
    "GOODBYE" : 0x03,
    "GOODBYE_ACK" : 0x04,
    "PING" : 0x05,
    "PONG" : 0x06,
    
    # Requests from client
    'REQUEST_PARAMETERS': 0x21,
    'REQUEST_PROCESSORS': 0x22,
    'REQUEST_DISK_BUFFERS': 0x23,
    'REQUEST_DATA_POOLS': 0x24,
    'REQUEST_PARAMETER_SPACES': 0x25,
    
    # Imcoming from server
    'REGISTER_PARAMETER': 0x41,
    'REGISTER_PROCESSOR': 0x42,
    'REGISTER_DISK_BUFFER': 0x43,
    'REGISTER_DATA_POOL': 0x44,
    'REGISTER_PARAMETER_SPACE': 0x45,
    
    'REMOVE_PARAMETER' :0x61,
    'REMOVE_PROCESSOR' :0x62,
    'REMOVE_DISK_BUFFER' :0x63,
    'REMOVE_DATA_POOL' :0x64,
    'REMOVE_PARAMETER_SPACE' :0x65,

    'CONFIGURE_PARAMETER' :0x81,
    'CONFIGURE_PROCESSOR' :0x82,
    'CONFIGURE_DISK_BUFFER' :0x83,
    'CONFIGURE_DATA_POOL' :0x84,
    'CONFIGURE_PARAMETER_SPACE' :0x85,
    
    'OBJECT_COMMAND': 0xA0,
    'OBJECT_COMMAND_REPLY' : 0xA1,
    'OBJECT_COMMAND_ERROR' : 0xA2
    }

# TODO complete
parameter_types = {
    'PARAMETER_FLOAT' : 0x01,
    'PARAMETER_BOOL' : 0x02,
    'PARAMETER_STRING' : 0x03,
    'PARAMETER_INT32' : 0x04,
    'PARAMETER_VEC3F' : 0x05,
    'PARAMETER_VEC4F' : 0x06,
    'PARAMETER_COLORF' : 0x07,
    'PARAMETER_POSED' : 0x08,
    'PARAMETER_CHOICE' : 0x09,
    'PARAMETER_TRIGGER' : 0x10
    }

processor_types = {
    'CPP' : 0x01,
    'SCRIPT' : 0x02,
    'CHAIN' : 0x03
    
    }

parameter_update_commands = {
    'CONFIGURE_PARAMETER_VALUE' : 0x01,
    'CONFIGURE_PARAMETER_MIN' : 0x02,
    'CONFIGURE_PARAMETER_MAX' : 0x03
    }

data_pool_commands = {
    'CREATE_DATA_SLICE' : 0x01
    }

class TincClient(object):
    def __init__(self, server_addr: str = "localhost",
                 server_port: int = 34450):
        
        self.connected = False
        self.parameters = []
        self.processors = []
        self.datapools = []
        self.disk_buffers = []
        self.parameter_spaces = []
        self.request_timeout = 10.0
        self.pending_requests = {}
        self.pending_requests_count = 0
        self.pending_replies = {}
        self.request_count_lock = Lock()
     
        self.start(server_addr, server_port)
        
    def __del__(self):
        self.stop()
        
    def start(self, server_addr, server_port):
        
        # self.pserver = pserver
        self.serverAddr = server_addr
        self.serverPort = server_port
        
        self.running = True
        self.x = threading.Thread(target=self.server_thread_function, args=(self.serverAddr,self.serverPort))
        self.x.start()
        
        
    def stop(self):
        if self.running:
            self.running = False
            self.x.join()
            self.socket = None
            self.connected = False
    
    # Access to objects by id
    
    def get_parameter(self, parameter_id):
        for p in self.parameters:
            if p.id == parameter_id:
                return p
        return None
    
    def get_processor(self, processor_id):
        for p in self.processors:
            if p.id == processor_id:
                return p
        return None
    
    def get_disk_buffer(self, db_id):
        for db in self.disk_buffers:
            if db.id == db_id:
                return db
        return None
    
    def get_datapool(self, datapool_id):
        for dp in self.datapools:
            if dp.id == datapool_id:
                return dp
        return None
    
    def get_parameter_space(self, ps_id):
        for ps in self.parameter_spaces:
            if ps.id == ps_id:
                return ps
        return None
            
    # Network message handling
    
    def handle_ping(self):
        if self.socket:
            message = Message()
            message.append(commands['PONG'])
            message.append(0x00)
            self.socket.send(message.data)
        else:
            print("NOT CONNECTED")
        
    def register_parameter(self, message):        
        name = message.get_string()
        group = message.get_string()
        param_type = message.get_byte()

        if param_type == parameter_types['PARAMETER_FLOAT'] : 
            default = message.get_float()
            minValue = message.get_float()
            maxValue = message.get_float()
            new_param = Parameter(self, name, group, default, minValue, maxValue)
            pass
        elif param_type == parameter_types['PARAMETER_BOOL'] :
            default = message.get_float()
            new_param = ParameterBool(self, name, group, default)
            pass
        elif param_type == parameter_types['PARAMETER_STRING'] :
            default = message.get_string()
            minValue = message.get_string()
            maxValue = message.get_string()
            new_param = Parameter(self, name, group, default, minValue, maxValue)
            pass
        elif param_type == parameter_types['PARAMETER_INT32'] : 
            default = message.get_int32()
            minValue = message.get_int32()
            maxValue = message.get_int32()
            new_param = Parameter(self, name, group, default, minValue, maxValue)
            pass
        elif param_type == parameter_types['PARAMETER_VEC3F'] :
            pass
        elif param_type == parameter_types['PARAMETER_VEC4F'] :
            pass
        elif param_type == parameter_types['PARAMETER_COLORF'] :
            pass
        elif param_type == parameter_types['PARAMETER_POSED'] :
            pass
        elif param_type == parameter_types['PARAMETER_CHOICE'] :
            pass
        elif param_type == parameter_types['PARAMETER_TRIGGER'] :
            pass
        else:
            new_param = None
            
        if new_param:
            param_found = False
            for p in self.parameters:
                if p.id == new_param.id:
                    param_found = True
                    break
            if not param_found:
                
                self.parameters.append(new_param)
                
    def configure_parameter(self, message):
        param_osc_address = message.get_string()
        for param in self.parameters:
            if param.get_osc_address() == param_osc_address:
                param_command = message.get_byte()
                if param_command == parameter_update_commands['CONFIGURE_PARAMETER_VALUE']:
                    param.set_value_from_message(message)
                elif param_command == parameter_update_commands['CONFIGURE_PARAMETER_MIN']:
                    param.set_min_from_message(message)
                elif param_command == parameter_update_commands['CONFIGURE_PARAMETER_MAX']:
                    param.set_max_from_message(message)
                
    def send_parameter_value(self, param):
        message = Message()
        message.append(commands['CONFIGURE_PARAMETER'])
        message.insert_string(param.get_osc_address())
        message.append(parameter_update_commands['CONFIGURE_PARAMETER_VALUE'])
        message.append(param.get_value_serialized())
        self.socket.send(message.data)

        
    def register_processor(self, message):
        processor_type = message.get_byte()
        
        name = message.get_string()
        # print(name)
        input_dir = message.get_string()
        # print(input_dir)
        input_files = message.get_vector_string()
        # print(input_files)
        output_dir = message.get_string()
        # print(output_dir)
        output_files = message.get_vector_string()
        # print(output_files)
        running_dir = message.get_string()
        # print(running_dir)
        
        if processor_type == processor_types['CPP']:
            new_processor = CppProcessor(name, input_dir, input_files, output_dir, output_files, running_dir)
        elif processor_type == processor_types['SCRIPT']:
            new_processor = ScriptProcessor(name, input_dir, input_files, output_dir, output_files, running_dir)
        elif processor_type == processor_types['CHAIN']:
            new_processor = ComputationChain(name, input_dir, input_files, output_dir, output_files, running_dir)
        else:
            new_processor = None
            print(f"Unexpected processor type {processor_type}")
        
        found = False
        for proc in self.processors:
            if proc.name == name:
                if type(proc).__name__ == processor_type:
                    self.name = name
                    self.input_dir = input_dir
                    self.output_dir = output_dir
                    self.running_dir = running_dir
                    print(f"Updated processor '{name}'")
                    found = True
                    break
                else:
                    print(f"ERROR processor type mismatch! {name}")
            
        if not found and new_processor:
            self.processors.append(new_processor)
            print(f"Registered processor '{name}'")
        
    def configure_processor(self, message):
        proc_id= message.get_string()
        count = message.get_byte()
        config = {}
        print(f"got {count} configs")
        for i in range(count):
            name= message.get_string()
            value = message.get_variant()
            config[name] = value
        
        for proc in self.processors:
            if proc.name == proc_id:
                proc.configuration.update(config)
    
    def processor_update(self, client_address: str , address: str, *args: List[Any]):
        name = args[0]
        config_key = args[1]
        config_value = args[2]
        
        for proc in self.processors:
            if proc.name == name:
                proc.configuration[config_key] = config_value
                print(f"Config [{config_key}] = {config_value}")
                
    def register_datapool(self, message):
        dp_id = message.get_string()
        ps_id = message.get_string()
        slice_cache_dir = message.get_string()
        
        found = False
        for dp in self.datapools:
            if dp.id == dp_id:
                print(f"DataPool already registered: '{dp_id}'")
                found = True
                break
        
        if not found:
            new_datapool = DataPool(self, dp_id, ps_id, slice_cache_dir)
            self.datapools.append(new_datapool)
            
    def register_disk_buffer(self, message):
        disk_buffer_id= message.get_string()
        
        found = False
        for db in self.disk_buffers:
            if db.id == disk_buffer_id:
                print(f"DiskBuffer already registered: '{disk_buffer_id}'")
                found = True
                break
        
        if not found:
            new_db = DiskBuffer(disk_buffer_id)
            self.disk_buffers.append(new_db)
            
    def register_parameter_space(self, message):
        ps_id = message.get_string()
        
        found = False
        for ps in self.parameter_spaces:
            if ps.id == ps_id:
                print(f"ParameterSpace already registered: '{ps_id}'")
                found = True
                break
        
        if not found:
            new_ps = ParameterSpace(ps_id)
            self.parameter_spaces.append(new_ps)
        

    def process_object_command_reply(self, message):
        command_id = message.get_uint32()
        try:
            command_data = self.pending_requests.pop(command_id)
            self.pending_replies[command_id] = [message, command_data]
        except KeyError:
            print(f"Unexpected command reply: {command_id}")
        
    # Send request commands
    
    def send_request_command(self, command, data = b'\x00'):
        if self.socket:
            message = Message()
            message.append(commands[command])
            message.append(data)
            self.socket.send(message.data)
        else:
            print("Not connected.")
    
        
    def request_parameters(self):
        self.send_request_command('REQUEST_PARAMETERS')

    def request_processors(self):
        self.send_request_command('REQUEST_PROCESSORS')
        
    def request_disk_buffers(self):
        self.send_request_command('REQUEST_DISK_BUFFERS')
    
    def request_data_pools(self):
        self.send_request_command('REQUEST_DATA_POOLS')
    
    def request_parameter_spaces(self):
        self.send_request_command('REQUEST_PARAMETER_SPACES')
        
    def request_datapool_slice_file(self, datapool_id, field, sliceDimensions):
        self.request_count_lock.acquire()
        request_number = self.pending_requests_count
        self.pending_requests_count += 1
        if self.pending_requests_count == 4294967295:
            self.pending_requests_count = 0
        self.request_count_lock.release()
        
        message = Message()
        message.append(commands['OBJECT_COMMAND'])
        message.insert_as_uint32(request_number)
        
        message.append(data_pool_commands['CREATE_DATA_SLICE'])
        message.insert_string(datapool_id)
        message.insert_string(field)
        
        if type(sliceDimensions) == str:
            message.append(b'\x01')
            message.insert_string(sliceDimensions)
        elif type(sliceDimensions) == list and len(sliceDimensions) > 0:
            message.append(chr(len(sliceDimensions)))
            for dim in sliceDimensions:
                message.insert_vector_string(dim)
                
        # TODO check possible race condiiton in pending_requests count
        self.pending_requests[request_number] = [datapool_id]
        print(f"Sent command: {request_number}")

        if self.socket:
            self.socket.send(message.data)
        else:
            print("Not connected.")
            
        # FIXME implement timeout
        while not request_number in self.pending_replies:
            time.sleep(0.1)
            
        message, user_data = self.pending_replies.pop(request_number)
        slice_name = message.get_string()
        return slice_name
        
    def synchronize(self):
        self.request_parameters()
        self.request_processors()
        self.request_disk_buffers()
        self.request_data_pools()
        self.request_parameter_spaces()
        
    def quit_message(self, client_address, address: str, *args: List[Any]):
        print("Got /quit message, closing parameter server")
        self.stop()

    # Server ---------------
    def server_thread_function(self, ip: str, port: int):
#         print("Starting on port " + str(port))
        while self.running:
            if not self.connected:
                self.socket = None
                try:
                    # Attempt a connection
                    print(f"Attempt connection. {ip}:{port}")
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.setblocking(True)
                    s.connect((ip, port))
                    
                except:
                    # Connection was not possible, try later
                    time.sleep(1.0)
                    continue
                    
                print("Connected, sending handshake.")
                message = bytearray()
                message.append(commands['HANDSHAKE'])
                message.append(0x00)
                s.send(message)
                
                message = Message(s.recv(1024))
                command = message.get_byte()
                if command == commands['HANDSHAKE_ACK']:
                
                    self.connected = True
                    self.socket = s
                    print("Got HANDSHAKE_ACK.")
                else:
                    print("Expected HANDSHAKE_ACK. CLosing connection. Got {message[0]}")
            else:
                try:
                    message = Message(self.socket.recv(1024))
                except ConnectionResetError:
                    print("Connection closed.")
                    self.socket = None
                    self.connected = False;
                while not message.empty():
                    # print(message.data)
                    command = message.get_byte()
                    if command == commands['PING']:
                        self.handle_ping() 
                    # if message[0] == commands['SERVER_REQUEST_LISTENER_INFO']:
                    #     self.send_listener_info()
                    # elif message[0] == commands['SERVER_REGISTER_LISTENER']:
                    #     self.register_listener()
                    #     pass
                    elif command == commands['REGISTER_PARAMETER']:
                        # TODO finish
                        self.register_parameter(message)
                    elif command == commands['CONFIGURE_PARAMETER']:
                        self.configure_parameter(message)
                    elif command == commands['REGISTER_PROCESSOR']:
                        self.register_processor(message)
                    elif command == commands['CONFIGURE_PROCESSOR']:
                        self.configure_processor(message)
                    elif command == commands['REGISTER_DATA_POOL']:
                        self.register_datapool(message)
                    elif command == commands['REGISTER_DISK_BUFFER']:
                        self.register_disk_buffer(message)
                    elif command == commands['REGISTER_PARAMETER_SPACE']:
                        self.register_parameter_space(message)
                    #     pass
                    # elif message[0] == commands['SERVER_REGISTER_BUNDLE_PARAMETER']:
                    #     self.register_bundle_parameter()
                    #     pass
                    # elif message[0] == commands['SERVER_PROCESSOR_CONFIGURATION']:
                    #     self.processor_update()
                    #     pass
                    # elif message[0] == commands['SERVER_REQUEST_LISTENER_INFO']:
                        
                    #     pass
                    elif command == commands['OBJECT_COMMAND_REPLY']:
                        self.process_object_command_reply(message)
                    elif command == commands['OBJECT_COMMAND_ERROR']:
                        print("OBJECT_COMMAND_ERROR not implemented")
                        pass

        print("Closed command server")                

    def print(self):    
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
                print("Attempting to connect to app.")
            else:
                print("NOT CONNECTED")
        else:
            print("NOT CONNECTED")
              
