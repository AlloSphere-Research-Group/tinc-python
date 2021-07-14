from .tinc_object import TincObject

class Processor(TincObject):
    def __init__(self, tinc_id = "_", input_dir = "", input_files = [],
                 output_dir = "", output_files = [], running_dir = ""):
        super().__init__(tinc_id)

        # These properties are meant to be set directly by the user
        self.input_dir = input_dir
        self.input_files = input_files
        self.output_dir = output_dir
        self.output_files = output_files
        self.running_dir = running_dir
        self.debug = False
        self.ignore_fail = False
        self.prepare_function = None
        self.enabled = True
        self.configuration = {}

        # Internal data
        self._start_callback = None
        self._done_callback = None
        self._dimensions =[]
        self._parent = None
        # FIXME we need to support TincServer and local usage
        self._tinc_server = None
        self._local = True 
        
    def print(self):
        if self.input_dir:
            print(f"Input directory: {self.input_dir}")
        if self.input_files:
            print(f"Input files: {self.input_files}")
        if self.output_dir:
            print(f"Output directory: {self.output_dir}")
        if self.output_files:
            print(f"Output files: {self.output_files}")
        if self.running_dir:
            print(f"Running directory: {self.running_dir}")
        for key, value in self.configuration.items():
            print(f"['{key}'] = {value}")

    def process(self, force_recompute = False):
        raise NotImplementedError("You need to use classes that derive from Processor, but not Processor directly")

    def register_start_callback(self,cb):
        self._start_callback = cb

    def register_done_callback(self,cb):
        self._done_callback = cb

    def register_dimension(self, dim):
        self._dimensions.append(dim)

class ComputationChain(Processor):
    def __init__(self, tinc_id = "_", input_dir = "", input_files = [],
                 output_dir = "", output_files = [], running_dir = ""):
        super().__init__(tinc_id, input_dir, input_files,
                                               output_dir, output_files, running_dir)
        
    def print(self):
        print(f"*** Computation Chain: {self.id}")
        #Processor.print(self)
        

class ProcessorScript(Processor):
    def __init__(self, tinc_id = "_", input_dir = "", input_files = [],
                 output_dir = "", output_files = [], running_dir = ""):
        super().__init__(tinc_id, input_dir, input_files,
                                               output_dir, output_files, running_dir)
    
    def process(self, force_recompute = False):
        if not self.enabled:
            return True

        if self.debug:
            print("Starting ProcessorScript '{self.id}'")
    
    def print(self):
        print(f"*** ProcessorScript : {self.id}")
        Processor.print(self)
        

class ProcessorCpp(Processor):
    def __init__(self, name = "_", input_dir = "", input_files = [],
                 output_dir = "", output_files = [], running_dir = ""):
        super().__init__(name, input_dir, input_files,
                                               output_dir, output_files, running_dir)

    def print(self):
        print(f"*** C++ Processor: {self.id}")
        Processor.print(self)