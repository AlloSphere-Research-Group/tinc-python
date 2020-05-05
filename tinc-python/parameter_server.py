from pythonosc import dispatcher
from pythonosc import osc_server
from pythonosc import udp_client
import threading
import time
from typing import List, Any

try:
    from ipywidgets import interact, interactive, interact_manual
    import ipywidgets as widgets
except:
    print("Error importin ipywidgets. Notebook widgets not available")

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
        
        self.d = dispatcher.Dispatcher()
        self.d.map("/requestListenerInfo", self.send_listener_info,
                           needs_reply_address = True)
        self.d.map("/registerListener", self.register_listener,
                           needs_reply_address = True)
        self.d.map("/registerParameter", self.register_parameter,
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
        
    def register_parameter(self, client_address: str , address: str, *args: List[Any]):

        name, group, default, prefix, minimum, maximum = args
        if type(default) == float:
            new_param = Parameter(name, group, default, prefix, minimum, maximum)
        elif type(default) == str:
            new_param = ParameterString(name, group, default, prefix)
        elif type(default) == int:
            new_param = ParameterInt(name, group, default, prefix, minimum, maximum)

        for p in self.pserver.parameters:
            if p.get_full_address() == new_param.get_full_address():
                print(f"Parameter {args[0]} already registered")
                return
        print(f"Registered parameter {args[0]} from {client_address}")
        self.pserver.register_parameter(new_param)
        
#     def message_handler(self, address: str, *args: List[Any]):
#         print("Unhandled command [{0}] ~ {1}".format(address, args[0]))

    def quit_message(self, client_address, address: str, *args: List[Any]):
        print("Got /quit message, closing parameter server")
        self.stop()
    
    def request_parameters(self):
        self.client.send_message("/sendParametersMeta", (self.handshakeServerAddr, self.listenerFirstPort))
        
    def request_all_parameter_values(self):
        self.client.send_message("/sendAllParameters", (self.pserver.ip, self.pserver.port))
        

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

class ParameterServer(object):
    def __init__(self, ip: str = "localhost", start_port: int = 9011):
        self.ip = ip
        self.port = start_port
        self.parameters = []
        self.listeners = []
        self.dispatcher = dispatcher.Dispatcher()
        
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
        
        self.app_connection = None
        
    def print(self):
        if not self.running:
            print("Parameter server not running. Use start()")
            return
        print(f"Parameter Server running at {self.ip}:{self.port}")
        if self.app_connection.server:
            print(f"Command Server at {self.app_connection.server.server_address}")
            if self.app_connection.connected:
                print("APP CONNECTED")
            elif self.app_connection.running:
                print("Attempting to connect to app.")
            else:
                print("NOT RUNNING")
        else:
            print("App command server not available.")
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
    
    def monitor_server(self, timeout: float = 30):
        timeAccum = 0.0
        while timeAccum < timeout or timeout == 0:
            timeAccum += 0.1
            time.sleep(0.1)
#             yield
        
    def register_parameter(self, p):
        p.observers.append(self)
        self.parameters.append(p)
        
        self.dispatcher.map(p.get_full_address(), self.set_parameter_value, p,
                           needs_reply_address = True)

    def get_parameter(self, name):
        for p in self.parameters:
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
        self.server = osc_server.ThreadingOSCUDPServer(
          (ip, port), self.dispatcher)
        self.server.timeout = 1.0
        print("Parameter server started on {}".format(self.server.server_address))
        while self.running:
            self.server.handle_request()
            
        self.server.server_close()
        print("Closed parameter server")
        
    def send_parameter_value(self, p, source_address):
        for l in self.listeners:
            print("Sending " + p.get_full_address() + " from " + str(source_address))
            print("Sending to " + l._address)
            if not source_address:
                l.send_message(p.get_full_address(), p.value)
            elif not source_address[0] == l._address:
                l.send_message(p.get_full_address(), p.value)
            else:
                print("Blocked return message for " + source_address[0])
                pass
            
        
