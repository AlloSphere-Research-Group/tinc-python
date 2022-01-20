

from subprocess import Popen
from .tinc_client import TincClient
from time import sleep

class TincBridge(TincClient):

    def __init__(self, executable = None, running_path = "./"):
        super().__init__()
        self.executable = executable
        self.running_path = running_path
        self._proc = None
        pass

    def launch(self):
        self._proc = Popen([self.executable], cwd = self.running_path)
        sleep(4) # TODO use better method, like testing until server responds.
        super().start()

    def quit(self):
        super().stop()
        self._proc.terminate()
