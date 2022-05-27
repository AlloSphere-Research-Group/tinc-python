from pythonosc import dispatcher
from pythonosc import osc_server
from pythonosc import udp_client
import threading
import time
from typing import List, Any

from .parameter import *
from .processor import *

class ParameterServer(object):
    def __init__(self, ip: str = "localhost", start_port: int = 9011, tinc_client = None):
        self.ip = ip
        self.port = start_port
        self.parameters = []
        self.listeners = []
        self.bundles = {}
        self.dispatcher = dispatcher.Dispatcher()
        self.dispatcher.set_default_handler(self.default_osc_handler, needs_reply_address = True)
        
        self.tinc_client = tinc_client
        
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
        
    def _send_parameter_value(self, p, source_address):
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
            
        
