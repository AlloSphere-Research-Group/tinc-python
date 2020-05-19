from pythonosc import dispatcher
from pythonosc import osc_server
from pythonosc import udp_client
import threading
import time
from typing import List, Any

from parameter import *
from processor import *

class AppConnection(object):
    def __init__(self, pserver, handshake_server_addr: str = "127.0.0.1",
                 handshake_server_port: int = 16987, listener_first_port: int = 14001):
        
        self.pserver = pserver
        self.handshakeServerAddr = handshake_server_addr
        self.handshakeServerPort = handshake_server_port
        self.listenerFirstPort = listener_first_port
        self.client = udp_client.SimpleUDPClient(self.handshakeServerAddr, self.handshakeServerPort)
        self.connected = False
        self.server = None
        self.processors = []
        
        self.d = dispatcher.Dispatcher()
        self.d.map("/requestListenerInfo", self.send_listener_info,
                           needs_reply_address = True)
        self.d.map("/registerListener", self.register_listener,
                           needs_reply_address = True)
        self.d.map("/registerParameter", self.register_parameter,
                           needs_reply_address = True)
        self.d.map("/registerBundleParameter", self.register_bundle_parameter,
                           needs_reply_address = True)
        self.d.map("/registerProcessor", self.register_processor,
                           needs_reply_address = True)
        self.d.map("/processor/configuration", self.processor_update,
                           needs_reply_address = True)
        self.d.map("/quit", self.quit_message)
#         self.d.map("/*", self.message_handler)
        self.start()
        
    def __del__(self):
        self.stop()
        
    def start(self):

        self.running = True
        self.x = threading.Thread(target=self.server_thread_function, args=(self.handshakeServerAddr, self.listenerFirstPort))
        self.x.start()
        
    def stop(self):
        if self.running:
            self.running = False
            self.x.join()
            self.server = None
            self.connected = False

    def get_listener_info(self):
        print("LISTENER INFO")
        pass
        
    # OSC Message handling 
    def send_listener_info(self, client_address: str, address: str, *args: List[Any]):
        print("Got /requestListenerInfo from " + str(client_address))
        self.client.send_message("/registerListener", (self.pserver.ip, self.pserver.port))
        self.client.send_message("/requestListenerInfo", (self.handshakeServerAddr, self.listenerFirstPort))
        self.connected = True
        
    def register_listener(self, client_address: str , address: str, *args: List[Any]):
        self.pserver.add_listener(args[0], args[1])
        
    def register_bundle_parameter(self, client_address: str , address: str, *args: List[Any]):
        bundle_name, bundle_id, name, group, default, prefix, minimum, maximum = args
        if type(default) == float:
            new_param = Parameter(name, group, default, prefix, minimum, maximum)
        elif type(default) == str:
            new_param = ParameterString(name, group, default, prefix)
        elif type(default) == int:
            new_param = ParameterInt(name, group, default, prefix, minimum, maximum)

        for p in self.pserver.parameters:
            if p.get_full_address() == new_param.get_full_address() and p.prefix == new_param.prefix:
                print(f"Parameter {args[0]} already registered")
                return
        print(f"Registered parameter {name} in bundle {bundle_name}:{bundle_id} from {client_address}")
        self.pserver.register_bundle_parameter(new_param, bundle_name, bundle_id)
        
        
    def register_parameter(self, client_address: str , address: str, *args: List[Any]):
        name, group, default, prefix, minimum, maximum = args
        if type(default) == float:
            new_param = Parameter(name, group, default, prefix, minimum, maximum)
        elif type(default) == str:
            new_param = ParameterString(name, group, default, prefix)
        elif type(default) == int:
            new_param = ParameterInt(name, group, default, prefix, minimum, maximum)

        print(f"Registering parameter {args[0]} from {client_address}")
        self.pserver.register_parameter(new_param)
        
    def register_processor(self, client_address: str , address: str, *args: List[Any]):
        processor_type, name, parent, input_dir, input_file, output_dir, output_file, running_dir = args
        if processor_type == 'ComputationChain':
            new_processor = ComputationChain(name, parent, input_dir, input_file, output_dir, output_file, running_dir)
        elif processor_type == 'DataScript':
            new_processor = DataScript(name, parent, input_dir, input_file, output_dir, output_file, running_dir)
        elif processor_type == 'CppProcessor':
            new_processor = CppProcessor(name, parent, input_dir, input_file, output_dir, output_file, running_dir)
        
        found = False
        for proc in self.processors:
            if proc.name == name:
                if type(proc).__name__ == processor_type:
                    self.name = name
                    self.parent = parent
                    self.input_dir = input_dir
                    self.output_dir = output_dir
                    self.running_dir = running_dir
                    print(f"Updated processor '{name}'")
                    found = True
                    break
                else:
                    print(f"ERROR processor type mismatch! {name}")
            
        if not found:
            self.processors.append(new_processor)
            print(f"Registered processor '{name}'")
        
    
    def processor_update(self, client_address: str , address: str, *args: List[Any]):
        name = args[0]
        config_key = args[1]
        config_value = args[2]
        
        for proc in self.processors:
            if proc.name == name:
                proc.configuration[config_key] = config_value
#     def message_handler(self, address: str, *args: List[Any]):
                print(f"Config [{config_key}] = {config_value}")

    def quit_message(self, client_address, address: str, *args: List[Any]):
        print("Got /quit message, closing parameter server")
        self.stop()
    
    # Send commands
    def request_parameters(self):
        self.client.send_message("/sendParametersMeta", (self.handshakeServerAddr, self.listenerFirstPort))
        
    def request_all_parameter_values(self):
        self.client.send_message("/sendAllParameters", (self.pserver.ip, self.pserver.port))
        
    def request_processors(self):
        self.client.send_message("/computationChains", (self.listenerFirstPort))

    # Server ---------------
    def server_thread_function(self, ip: str, port: int):
#         print("Starting on port " + str(port))
        self.server = osc_server.ThreadingOSCUDPServer(
          (ip, port), self.d)
        self.server.timeout = 0.1
        print("Command server: Serving on {}".format(self.server.server_address))
        while self.running:
            if not self.connected:
                self.client.send_message("/handshake", self.listenerFirstPort)
                time.sleep(0.3)
            self.server.handle_request()
        self.client.send_message("/goodbye", (self.handshakeServerAddr, self.listenerFirstPort))
        print("Closed command server")

    def print(self):    
        if self.server:
            print(f"Command Server at {self.server.server_address}")
            if self.connected:
                print("APP CONNECTED")
            elif self.running:
                print("Attempting to connect to app.")
            else:
                print("NOT RUNNING")
        else:
            print("App command server not available.")

class ParameterServer(object):
    def __init__(self, ip: str = "localhost", start_port: int = 9011):
        self.ip = ip
        self.port = start_port
        self.parameters = []
        self.listeners = []
        self.bundles = {}
        self.dispatcher = dispatcher.Dispatcher()
        self.dispatcher.set_default_handler(self.default_osc_handler, needs_reply_address = True)
        
        self.start()
        
    def __del__(self):
        self.stop()
        
    def start(self):
        self.running = True
        self.x = threading.Thread(target=self.server_thread_function, args=(self.ip, self.port))
        self.x.start()
        self.app_connection = AppConnection(self)
        
    def stop(self):
        self.app_connection.stop()
        self.running = False
        self.x.join()
        
        self.server = None
        self.app_connection = None
        
    def print(self):
        if not self.running:
            print("Parameter server not running. Use start()")
            return
        print(f"Parameter Server running at {self.ip}:{self.port}")
        self.app_connection.print()
        if len(self.listeners) > 0:
            print(' --- Listeners ---')
            for l in self.listeners:
                print(f'{l._address}:{l._port}')
        if len(self.parameters) > 0:
            print(' --- Parameters ---')
            for p in self.parameters:
                print(f'{p.get_full_address()} -- {str(p.value)}')
                for c in p._value_callbacks:
                    print(f'callback:  {c.__name__}')
        
        if len(self.bundles) > 0:
            print(' --- Bundles ---')
            for name, instances in self.bundles.items():
                print(f'name: {name} instances: {instances.keys()}')
                for instance_id,params in instances.items():
                    print(f'{instance_id} -----------')
                    for p in params:
                        print(f'{instance_id}:: {p.get_full_address()} -- {str(p.value)}')
#                         for c in p._value_callbacks:
#                             print(f'callback:  {c.__name__}')
    
    def monitor_server(self, timeout: float = 30):
        timeAccum = 0.0
        while timeAccum < timeout or timeout == 0:
            timeAccum += 0.1
            time.sleep(0.1)
#             yield
        
    def register_parameter(self, p):
        for existing in self.parameters:
            if existing.get_full_address() == p.get_full_address():
                print(f"Parameter {new_param.get_full_address()} already registered")
                return
        p.observers.append(self)
        self.parameters.append(p)
        
        self.dispatcher.map(p.get_full_address(), self.set_parameter_value, p,
                           needs_reply_address = True)
        
    
    def register_bundle_parameter(self, p, bundle_name :str, bundle_id : str):
        if not bundle_name in self.bundles:
            self.bundles[bundle_name] = {}
        if not bundle_id in self.bundles[bundle_name]:
            self.bundles[bundle_name][bundle_id] = []
        
        for existing in self.bundles[bundle_name][bundle_id]:
            if existing.get_full_address() == p.get_full_address():
                print(f"Parameter {p.get_full_address()} already registered in bundle {bundle_name}:{bundle_id}")
                return
        self.bundles[bundle_name][bundle_id].append(p)
        
        p.parent_bundle = (bundle_name, bundle_id)
        
        p.observers.append(self)

    def get_parameter(self, name):
        for p in self.parameters:
            if p.name == name:
                return p
            
        return None
    
    def get_parameter_from_bundle(self, bundle_name, bundle_id, name):
        for p in self.bundles[bundle_name][bundle_id]:
            if p.name == name:
                return p
        return None

    def register_parameters(self, params):
        for p in params:
            self.register_parameter(p)
            
    def request_all_parameter_values(self):
        self.app_connection.request_all_parameter_values()
    
    def request_parameters(self):
        self.app_connection.request_parameters()
        
    def default_osc_handler(self, client_address, addr, p: str, *args):
        for bundle_name, bundles in self.bundles.items():
            for bundle_id, params in bundles.items():
                prefix = f'/{bundle_name}/{bundle_id}'
                
                if addr.find(prefix) == 0:
                    for p in params:
                        bundle_param_name = prefix + p.get_full_address()
                        if bundle_param_name == addr:
                    
                            p.set_value(p, client_address)
                    #         if not p[0].value == args[0]:
                    #             p[0].value = args[0]
                    #        print("got parameter message " + str(addr) + str(args))
    
    def set_parameter_value(self, client_address, addr, p: str, *args):
        # TODO there should be a way to select whether to relay duplicates or not, perhaps depending on a role
        p[0].set_value(args[0], client_address)
#         if not p[0].value == args[0]:
#             p[0].value = args[0]
        print("got parameter message " + str(addr) + str(args))
        
    def add_listener(self, ip: str, port: int):
        print("Register listener " + ip + ":" + str(port))
        for l in self.listeners:
            if l._address == ip and l._port == port:
                print("Already registered ignoring request.")
                return
        self.listeners.append(udp_client.SimpleUDPClient(ip, port))
        
    def server_thread_function(self, ip: str, port: int):
        port_to_try = port
        self.server = None
        while not self.server and port_to_try < port + 100:
            try:
                self.server = osc_server.ThreadingOSCUDPServer(
                  (ip, port_to_try), self.dispatcher)
                self.server.timeout = 1.0
            except Exception as e:
                port_to_try += 1
                print(f"Now trying port {port_to_try}")
        
        if not self.server:
            print("Error. Could not find free port for Parameter Server")
            return
        
        print("Parameter server started on {}".format(self.server.server_address))
        while self.running:
            self.server.handle_request()
            
        self.server.server_close()
        print("Closed parameter server")
        self.server = None
        
    def send_parameter_value(self, p, source_address):
        for l in self.listeners:
            parent_prefix = ''
            if p.parent_bundle:
                parent_prefix = f'/{p.parent_bundle[0]}/{p.parent_bundle[1]}'
            
            print("Sending " + parent_prefix + p.get_full_address() + " from " + str(source_address))
            print("******* to " + l._address)
            if not source_address or not source_address[0] == l._address:
                l.send_message(parent_prefix + p.get_full_address(), p.value)
            else:
                print("Blocked return message for " + source_address[0])
                pass
            
        
