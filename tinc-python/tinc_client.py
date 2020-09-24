import threading
import time
import socket
from typing import List, Any
import struct
from threading import Lock

from parameter import Parameter, ParameterString, ParameterInt, ParameterChoice, ParameterBool, ParameterColor
from processor import CppProcessor, ScriptProcessor, ComputationChain
from parameter_server import ParameterServer
from datapool import DataPool
from parameter_space import ParameterSpace
from disk_buffer import DiskBuffer
from message import Message
import tinc_protocol_pb2 as TincProtocol
from google.protobuf import any_pb2, message

tinc_client_version = 1
tinc_client_revision = 1

commands = {
    "HANDSHAKE" : 0x01,
    "HANDSHAKE_ACK" : 0x02,
    "GOODBYE" : 0x03,
    "GOODBYE_ACK" : 0x04,
    "PING" : 0x05,
    "PONG" : 0x06,
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
        self.pending_requests_count = 1
        self.pending_replies = {}
        self.request_count_lock = Lock()
        
        self.server_version = 0
        self.server_revision = 0
     
        self.start(server_addr, server_port)
        
    def __del__(self):
        self.stop()
        print("Stopped")
        
    def start(self, server_addr = "localhost", server_port = 34450):
        
        # self.pserver = pserver
        self.serverAddr = server_addr
        self.serverPort = server_port
        
        self.running = True
        self.x = threading.Thread(target=self.server_thread_function, args=(self.serverAddr,self.serverPort))
        self.x.start()
        
        
    def stop(self):
        if self.running:
            self.running = False
            self.connected = False
            self.socket.close()
            self.x.join()
            self.socket = None
        
        self.server_version = 0
        self.server_revision = 0
    
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
        pass
        # if self.socket:
        #     message = Message()
        #     message.append(commands['PONG'])
        #     message.append(0x00)
        #     raise ValueError
        #     self.socket.send(message.data)
        # else:
        #     print("NOT CONNECTED")
        
    def register_parameter(self, details):
        if details.Is(TincProtocol.RegisterParameter.DESCRIPTOR):
            # print("Register parameter")
            
            details_unpacked = TincProtocol.RegisterParameter()
            details.Unpack(details_unpacked)
            name = details_unpacked.id
            group = details_unpacked.group
            param_type = details_unpacked.dataType
    
            if param_type == TincProtocol.PARAMETER_FLOAT : 
                new_param = Parameter(self, name, group, details_unpacked.defaultValue.valueFloat )
            elif param_type == TincProtocol.PARAMETER_BOOL: 
                new_param = ParameterBool(self, name, group, details_unpacked.defaultValue.valueFloat)
                    
            elif param_type == TincProtocol.PARAMETER_STRING :
                new_param = ParameterString(self, name, group, details_unpacked.defaultValue.valueString)
            elif param_type == TincProtocol.PARAMETER_INT32 : 
                new_param = ParameterInt(self, name, group, details_unpacked.defaultValue.valueInt32)
            elif param_type == TincProtocol.PARAMETER_VEC3F :
                new_param = None
                pass
            elif param_type == TincProtocol.PARAMETER_VEC4F :
                new_param = None
                pass
            elif param_type == TincProtocol.PARAMETER_COLORF :
                l = [v.valueFloat for v in details_unpacked.defaultValue.valueList]
                new_param = ParameterColor(self, name, group, l)
                pass
            elif param_type == TincProtocol.PARAMETER_POSED :
                new_param = None
                pass
            elif param_type == TincProtocol.PARAMETER_CHOICE :
                new_param = ParameterChoice(self, name, group, details_unpacked.defaultValue.valueUint64)
                pass
            elif param_type == TincProtocol.PARAMETER_TRIGGER :
                new_param = None
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
                else:
                    pass
                    # print("Parameter already registered.")
            else:
                print("Unsupported parameter type")
        else:
            print("ERROR: Unexpected payload in REGISTER PARAMETER")
                
    def configure_parameter(self, details):
        param_details = TincProtocol.ConfigureParameter()
        details.Unpack(param_details)
  
        param_osc_address = param_details.id
        
        configured = True
        for param in self.parameters:
            if param.get_osc_address() == param_osc_address:
                param_command = param_details.configurationKey
                if param_command == TincProtocol.ParameterConfigureType.VALUE:
                    configured = configured and param.set_value_from_message(param_details.configurationValue)
                elif param_command == TincProtocol.ParameterConfigureType.MIN:
                    configured = configured and param.set_min_from_message(param_details.configurationValue)
                elif param_command == TincProtocol.ParameterConfigureType.MAX:
                    configured = configured and param.set_max_from_message(param_details.configurationValue)
                elif param_command == TincProtocol.ParameterConfigureType.SPACE:
                    configured = configured and param.set_space_from_message(param_details.configurationValue)
                else:
                    print("Unrecognized Parameter Configure command")
                
        if not configured:
            print("Parameter configuration failed")
            
    def send_parameter_value(self, param):
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
        config.configurationValue.Pack(value)
        msg.details.Pack(config)
        print("send")
        self._send_message(msg)
        
    def register_processor(self, message):
        proc_details = any_pb2.Any()
        proc_details.Unpack(message.details)
        if proc_details.Is(TincProtocol.RegisterProcessor):
            processor_type = message.type
            proc_id  = message.id
            # print(name)
            input_dir = message.inputDirectory
            # print(input_dir)
            input_files = message.inputFiles
            # print(input_files)
            output_dir = message.outputDirectory
            # print(output_dir)
            output_files = message.outputFiles
            # print(output_files)
            running_dir = message.runningDirectory
            # print(running_dir)
            
            if processor_type == TincProtocol.CPP:
                new_processor = CppProcessor(proc_id, input_dir, input_files, output_dir, output_files, running_dir)
            elif processor_type ==  TincProtocol.SCRIPT:
                new_processor = ScriptProcessor(proc_id, input_dir, input_files, output_dir, output_files, running_dir)
            elif processor_type == TincProtocol.CHAIN:
                new_processor = ComputationChain(proc_id, input_dir, input_files, output_dir, output_files, running_dir)
            else:
                new_processor = None
                print(f"Unexpected processor type {processor_type}")
            
            found = False
            for proc in self.processors:
                if proc.name == proc_id:
                    if type(proc).__name__ == processor_type:
                        self.name = proc_id
                        self.input_dir = input_dir
                        self.output_dir = output_dir
                        self.running_dir = running_dir
                        print(f"Updated processor '{proc_id}'")
                        found = True
                        break
                    else:
                        print(f"ERROR processor type mismatch! {proc_id}")
                
            if not found and new_processor:
                self.processors.append(new_processor)
                print(f"Registered processor '{proc_id}'")
        else:
            print("Unexpected payload in Register Processor")
        
    def configure_processor(self, details):
        if details.Is(TincProtocol.ConfigureProcessor.DESCRIPTOR):
            proc_details = TincProtocol.ConfigureProcessor()
            details.Unpack(proc_details)
            proc_id= proc_details.id
            count = proc_details.configurationKey
            for proc in self.processors:
                if proc.name == proc_id:
                    proc.configuration.update({proc_details.configurationKey: proc_details.configurationValue})
    
    def processor_update(self, client_address: str , address: str, *args: List[Any]):
        name = args[0]
        config_key = args[1]
        config_value = args[2]
        
        for proc in self.processors:
            if proc.name == name:
                proc.configuration[config_key] = config_value
                print(f"Config [{config_key}] = {config_value}")
                
    def register_datapool(self, details):
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
                    print(f"DataPool already registered: '{dp_id}'")
                    found = True
                    break
            
            if not found:
                new_datapool = DataPool(self, dp_id, ps_id, slice_cache_dir)
                self.datapools.append(new_datapool)
        else:
            print("Unexpected payload in Register Datapool")
            
    def configure_datapool(self, details):
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
        else:
            print("Unexpected payload in Configure Datapool")
        
    # Disk buffer messages ------------------
    def register_disk_buffer(self, details):
        
        if details.Is(TincProtocol.RegisterDiskBuffer.DESCRIPTOR):
            
            db_details = TincProtocol.RegisterDiskBuffer()
            details.Unpack(db_details)
            disk_buffer_id= db_details.id
            
            found = False
            for db in self.disk_buffers:
                if db.id == disk_buffer_id:
                    if not db_details.type == db.type:
                        print(f"DiskBuffer registered: '{disk_buffer_id}' ERROR: type mismatch")
                    else:
                        print(f"DiskBuffer already registered: '{disk_buffer_id}'")
                    found = True
                    break
        
            if not found:
                
                new_db = DiskBuffer(self, disk_buffer_id, db_details.type,
                                    db_details.baseFilename, db_details.path)
                self.disk_buffers.append(new_db)
        else:
            print("Unexpected payload in Register DiskBuffer")
            
            
    def send_disk_buffer_current_filename(self, disk_buffer, filename):
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
        # print("send")
        self._send_message(msg)
    
    # ParameterSpace messages ------------------
    def register_parameter_space(self, details):
        # print('register ps')
        if details.Is(TincProtocol.RegisterParameterSpace.DESCRIPTOR):
            ps_details = TincProtocol.RegisterParameterSpace()
            details.Unpack(ps_details)
            ps_id = ps_details.id
                
            found = False
            for ps in self.parameter_spaces:
                if ps.id == ps_id:
                    print(f"ParameterSpace already registered: '{ps_id}'")
                    found = True
                    break
            
            if not found:
                new_ps = ParameterSpace(ps_id)
                self.parameter_spaces.append(new_ps)
        

# ------------------------------------------------------
    def process_object_command_reply(self, message):
        command_details = TincProtocol.Command()
        if message.details.Is(TincProtocol.Command.DESCRIPTOR):
            message.details.Unpack(command_details)
            
            message_id = command_details.message_id
            # TODO we should verify the object id somehow
            try:
                command_data = self.pending_requests.pop(message_id)
                self.pending_replies[message_id] = [command_details.details, command_data]
            except KeyError:
                print(f"Unexpected command reply: {message_id}")
        else:
            print("Unsupported payload in Command reply")
        
        
    def process_register_command(self, message):
        # print("Register command")
        if message.objectType == TincProtocol.ObjectType.PARAMETER:
            self.register_parameter(message.details)
        elif message.objectType == TincProtocol.ObjectType.PROCESSOR:
            self.register_processor(message.details)
        elif message.objectType == TincProtocol.ObjectType.DISK_BUFFER:
            self.register_disk_buffer(message.details)
        elif message.objectType == TincProtocol.ObjectType.DATA_POOL:
            self.register_datapool(message.details)
        elif message.objectType == TincProtocol.ObjectType.PARAMETER_SPACE:
            self.register_parameter_space(message.details)
        else:
            print("Unexpected Register command")
    
    def process_request_command(self, message):
        pass
    def process_remove_command(self, message):
        pass
    def process_configure_command(self, message):
        if message.objectType == TincProtocol.PARAMETER:
            self.configure_parameter(message.details)
        elif message.objectType == TincProtocol.PROCESSOR:
            self.configure_processor(message.details)
        elif message.objectType == TincProtocol.DISK_BUFFER:
            self.configure_disk_buffer(message.details)
        elif message.objectType == TincProtocol.DATA_POOL:
            self.configure_datapool(message.details)
        # elif message.objectType == TincProtocol.PARAMETER_SPACE:
        #     pass
        else:
            print("Unexpected Configure command")
            
    def process_command_command(self, message):
        pass
    
    def process_reply_command(self, message):
        self.process_object_command_reply(message)
        
    def process_ping_command(self, message):
        pass
    def process_pong_command(self, message):
        pass
        
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
        
    def request_datapool_slice_file(self, datapool_id, field, sliceDimensions):
        self.request_count_lock.acquire()
        request_number = self.pending_requests_count
        self.pending_requests_count += 1
        if self.pending_requests_count == 4294967295:
            self.pending_requests_count = 0
        self.request_count_lock.release()
        
        msg = TincProtocol.TincMessage()
        msg.messageType  = TincProtocol.COMMAND
        msg.objectType = TincProtocol.DATA_POOL
        command = TincProtocol.Command()
        command.id.id = datapool_id
        command.message_id = request_number
        
        slice_details = TincProtocol.DataPoolCommandSlice()
        slice_details.field = field
        
        if type(sliceDimensions) == str:
            slice_details.dimension[:] = [sliceDimensions]
        elif type(sliceDimensions) == list and len(sliceDimensions) > 0:
            for dim in sliceDimensions:
                slice_details.dimension.append(dim)
                
        command.details.Pack(slice_details)
        msg.details.Pack(command)
        
        # TODO check possible race condiiton in pending_requests count
        self.pending_requests[request_number] = [datapool_id]

        self._send_message(msg)
            
        # print(f"Sent command: {request_number}")
        # FIXME implement timeout
        while not request_number in self.pending_replies:
            time.sleep(0.05)
            
        command_details, user_data = self.pending_replies.pop(request_number)
        if command_details.Is(TincProtocol.DataPoolCommandSliceReply.DESCRIPTOR):
            slice_reply = TincProtocol.DataPoolCommandSliceReply()
            command_details.Unpack(slice_reply)
            return slice_reply.filename
        else:
            return None
        
    def synchronize(self):
        self.request_parameters()
        self.request_processors()
        self.request_disk_buffers()
        self.request_data_pools()
        self.request_parameter_spaces()
        
    def quit_message(self, client_address, address: str, *args: List[Any]):
        print("Got /quit message, closing parameter server")
        self.stop()

    def _send_message(self, msg):
        size = msg.ByteSize()
        ser_size = struct.pack('N', size)
        num_bytes = self.socket.send(ser_size + msg.SerializeToString())
        # print(f'sent {num_bytes}')
        
    # Server ---------------
    def server_thread_function(self, ip: str, port: int):
#         print("Starting on port " + str(port))
        al_message = b''
        pc_message = TincProtocol.TincMessage()
        
        failed_attempts = 0
        while self.running:
            if not self.connected:
                self.socket = None
                try:
                    # Attempt a connection
                    if failed_attempts == 0:
                        print(f"Attempt connection. {ip}:{port}")
                    failed_attempts += 1
                    if failed_attempts == 100:
                        print(f"Connection failed.")
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
                print("Connected, sending handshake.")
                hs_message = bytearray()
                hs_message.append(commands['HANDSHAKE'])
                hs_message += struct.pack("H", tinc_client_version)
                hs_message += struct.pack("H", tinc_client_revision)
                s.send(hs_message)
                
                hs_message = Message(s.recv(1024))
                command = hs_message.get_byte()
                if command == commands['HANDSHAKE_ACK']:
                    self.server_version = 0
                    self.server_revision = 0
                    if len(hs_message.remaining_bytes()) > 8:
                        self.server_version = hs_message.get_uint32()
                        
                    if len(hs_message.remaining_bytes()) > 8:
                        self.server_revision = hs_message.get_uint32()
                
                    self.connected = True
                    self.socket = s
                    failed_attempts = 0
                    print(f"Got HANDSHAKE_ACK. Server version {self.server_version} revision {self.server_revision}")
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
                    
                    if len(al_message) < message_size + 8:
                        break
                    
                    num_bytes = pc_message.ParseFromString(al_message[8:8+message_size])
                    
                    if num_bytes > 0:
                        
                        if pc_message.messageType == TincProtocol.REQUEST:
                            self.process_register_command(pc_message)
                        elif pc_message.messageType == TincProtocol.REMOVE:
                            self.process_remove_command(pc_message)
                        elif pc_message.messageType == TincProtocol.REGISTER:
                            self.process_register_command(pc_message)
                        elif pc_message.messageType == TincProtocol.CONFIGURE:
                            self.process_configure_command(pc_message)
                        elif pc_message.messageType == TincProtocol.COMMAND:
                            self.process_command_command(pc_message)
                        elif pc_message.messageType == TincProtocol.COMMAND_REPLY:
                            self.process_reply_command(pc_message)
                        elif pc_message.messageType == TincProtocol.PING:
                            self.process_ping_command(pc_message)
                        elif pc_message.messageType == TincProtocol.PONG:
                            self.process_pong_command(pc_message)
                        else:
                            print("Unknown message")
                        al_message = al_message[message_size + 8:]
                        # print(f"Processed Byte_size {message_size}:{pc_message.ByteSize()} {len(message)}" )
                    else:
                        break
                            

                        
        print("Closed command server")                

    def print(self): 
        print("Print")
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
              
