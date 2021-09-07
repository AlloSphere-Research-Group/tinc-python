from .disk_buffer import DiskBuffer
from .tinc_object import TincObject
from .parameter import *

import re
import shlex

class Processor(TincObject):    
    # These properties are meant to be set directly by the user
    input_dir = ''
    input_files = ''
    output_dir = ''
    output_files = ''
    running_dir = ''
    debug = False
    ignore_fail = False
    enabled = True
    configuration = {}
    
    # Callbacks

    # You can provide here a function that takes the current Processor object that is called before processing
    # This function must return True otherwise the process() function is aborted
    prepare = None  # cb(self)
    start_callback = None # cb(self)
    done_callback = None # cb(self, ok)


    def __init__(self, tinc_id, input_dir = "", input_files = [],
                 output_dir = "", output_files = [], running_dir = ""):
        super().__init__(tinc_id)
        self.input_dir = input_dir
        self.input_files = input_files
        self.output_dir = output_dir
        self.output_files = output_files
        self.running_dir = running_dir
        # Internal data
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

    def register_parameter(self, dim, triggers_processor = True):
        # TODO ML check if parameter is already registered, to avoid double registration
        self._dimensions.append(dim)
        if (triggers_processor):
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
        self._buffer_filename = ''

    def set_argument_template(self, template):
        self._arg_template = template
        
    def capture_output(self, capture = True):
        self._capture_output = True

    def process(self, force_recompute = False):
        if self.start_callback is not None:
            self.start_callback(self)

        if not self.enabled:
            return True
        
        if self.debug:
            print(f"Starting ProcessorScript '{self.id}'")

        if self.prepare is not None:
            if not self.prepare(self):
                return False
        import subprocess
        wd = None
        if self.running_dir != '':
            wd = self.running_dir
        cmd = self.command + " "
        if len(self.script_name) > 0:
            cmd += self.script_name + " "
        cmd += self._get_arguments()
        try:
            if self.debug:
                print(f'Processor Running command: {cmd}')
            out = subprocess.check_output(shlex.split(cmd), cwd=wd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            print(e.output.decode('ascii'))
            print(repr(e))
            # if self._capture_output:
            #     with open(self.output_files[0], 'wb') as f:
            #         f.write(out)
            if self.done_callback is not None:
                self.done_callback(self, False)
            return False 

        if len(self._buffer_filename) > 0:
            if isinstance(self.output_files[0],DiskBuffer):
                self.output_files[0].done_writing_file(self._buffer_filename)
            if self.debug:
                print(f"Output is disk buffer: {self._buffer_filename}")
            self._buffer_filename = ''

        if self._capture_output:
            if isinstance(self.output_files[0],DiskBuffer):
                fname = self.output_files[0].get_filename_for_writing()
            elif type(self.output_files[0]) == str:
                fname = self.output_files[0]
            else:
                raise ValueError(f'Invalid type for output: {self.output_files[0]}')
            
            with open(fname, 'wb') as f:
                f.write(out)
            if self.debug:
                print(f"Output captured to: {out}")
                
            if isinstance(self.output_files[0],DiskBuffer):
                if self.debug:
                    print(f"Wrote stdout to disk buffer: {self.output_files[0].id}")
                fname = self.output_files[0].done_writing_file(fname)
                
        if self.done_callback is not None:
            self.done_callback(self, True)
            
        if self.debug:
            print(f"Finished ProcessorScript '{self.id}'")
        return True

    def _get_arguments(self):
        if self._arg_template == '':
            return ''
        args = self._arg_template

        for p in self._dimensions:

            if len(self.output_files) > 0 and not self._capture_output:
                if type(self.output_files[0]) == str: 
                    # TODO support multiple output files
                    args = args.replace(f'%%:OUTFILE:0%%',self.output_files[0]) 
                    
                if isinstance(self.output_files[0],DiskBuffer):
                    fname = self.output_files[0].get_filename_for_writing()
                    # FIXME the buffer file will remain locked by the disk buffer if there is an exception in this function
                    args = args.replace(f'%%:OUTFILE:0%%',fname) 

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