from .tinc_object import TincObject
from .parameter import *

import re

class Processor(TincObject):    
    # These properties are meant to be set directly by the user
    input_dir = ''
    input_files = ''
    output_dir = ''
    output_files = ''
    running_dir = ''
    debug = False
    ignore_fail = False
    prepare_function = None
    enabled = True
    configuration = {}

    def __init__(self, tinc_id, input_dir = "", input_files = [],
                 output_dir = "", output_files = [], running_dir = ""):
        super().__init__(tinc_id)
        self.input_dir = input_dir
        self.input_files = input_files
        self.output_dir = output_dir
        self.output_files = output_files
        self.running_dir = running_dir
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

    def register_parameter(self, dim):
        self._dimensions.append(dim)
        dim.register_callback(self._dimension_changed)

    def _dimension_changed(self, value):
        self.process()

class ComputationChain(Processor):
    def __init__(self, tinc_id = "_", input_dir = "", input_files = [],
                 output_dir = "", output_files = [], running_dir = ""):
        super().__init__(tinc_id, input_dir, input_files,
                                               output_dir, output_files, running_dir)
        
    def print(self):
        print(f"*** Computation Chain: {self.id}")
        #Processor.print(self)
        

class ProcessorScript(Processor):
    command:str = ''
    script_name:str = ''

    command_line_flag_template =''
    def __init__(self, tinc_id = "_", input_dir = "", input_files = [],
                 output_dir = "", output_files = [], running_dir = ""):
        super().__init__(tinc_id, input_dir, input_files, output_dir, output_files, running_dir)
        self._arg_template = ''
        self._capture_output = False

    def set_argument_template(self, template):
        self._arg_template = template
        
    def capture_output(self, capture = True):
        self._capture_output = True

    def process(self, force_recompute = False):
        if not self.enabled:
            return True
        
        if self.debug:
            print("Starting ProcessorScript '{self.id}'")
        import subprocess
        cmd = [self.command, self.script_name, self._get_arguments()]
        out = subprocess.check_output(cmd)

        if self._capture_output:
            with open(self.output_files[0], 'wb') as f:
                f.write(out)

    def _get_arguments(self):
        if self._arg_template == '':
            return ''
        args = self._arg_template

        for p in self._dimensions:
            if p.space_representation_type == parameter_space_representation_types.VALUE:
                args = args.replace(f'%%{p.id}%%', str(p.value) if type(p) != ParameterString else p.value)
            elif p.space_representation_type == parameter_space_representation_types.ID:
                args = args.replace(f'%%{p.id}%%', p.get_current_id())
            elif p.space_representation_type == parameter_space_representation_types.INDEX:
                args = args.replace(f'%%{p.id}%%', str(p.get_current_index()))
            re.sub(f'%%{p.id}:VALUE%%', str(p.value) if type(p) != ParameterString else p.value, args)
            if len(p.values) > 0:
                re.sub(f'%%{p.id}:INDEX%%', str(p.get_current_index()), args)
                re.sub(f'%%{p.id}:ID%%', p.get_current_id(), args)

        return args

    
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