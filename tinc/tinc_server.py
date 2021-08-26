from .tinc_client import TincClient

import os, shutil
from subprocess import Popen, PIPE

import time
import json

class TincServer(TincClient):

    _server_process = None
    _server_root_path_map = {}

    def __init__(self):
        tinc_bin = shutil.which('tinc_server', path=os.getenv('TINC_BIN_DIR'))
        if not tinc_bin:
            raise RuntimeError('TINC_BIN_DIR not set and tinc_server not found in path')
        super().__init__(self ,auto_connect=False)
    
    def start(self):
        tinc_bin = shutil.which('tinc_server', path=os.getenv('TINC_BIN_DIR'))
        if not tinc_bin:
            raise RuntimeError('TINC_BIN_DIR not set and tinc_server not found in path')

        self._server_process = Popen(tinc_bin, stdin=PIPE)
        # TODO handle configuration if another server already exists on this node
        
        # FIXME instead of waiting check to see when server is available
        time.sleep(1)

        with open('tinc_server_config.json', 'w') as f:
            json.dump({"rootPathMap" :self._server_root_path_map}, f)
        super().start()

    def set_root_map_entry(self, server_path, client_path, host = ''):
        if not 'host' in self._server_root_path_map:
            self._server_root_path_map[host] = []
        self._server_root_path_map[host].append({"serverPath" : server_path, "clientPath" : client_path})

    def stop(self):
        if self._server_process:
            self._server_process.kill()
            # TODO do ti more gracefully:
            # self._server_process.communicate(input=b"\n")
            # TODO ensure server has quit
            self._server_process = None

