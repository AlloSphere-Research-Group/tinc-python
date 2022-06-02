from tinc import processor
from .disk_buffer import DiskBuffer
from .tinc_object import TincObject
from .parameter import *

import re
import os
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

    '''Base functionality and interface for TINC Processors.

    You will want to instantiate specific processors: :class:`tinc.processor.ProcessorScript` or
    :class:`tinc.processor.ProcessorScriptDocker`.
    '''
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
        
    def __str__(self):
        if self.input_dir:
            return f"Input directory: {self.input_dir}"
        if self.input_files:
            return f"Input files: {self.input_files}"
        if self.output_dir:
            return f"Output directory: {self.output_dir}"
        if self.output_files:
            return f"Output files: {self.output_files}"
        if self.running_dir:
            return f"Running directory: {self.running_dir}"
        for key, value in self.configuration.items():
            return f"['{key}'] = {value}"

    def set_output_files(self, outfiles):
        if not type(outfiles) == list:
            raise ValueError("Must pass a list of files")
        self.output_files = outfiles
        
    def set_input_files(self, infiles):
        if not type(infiles) == list:
            raise ValueError("Must pass a list of files")
        self.input_files = infiles

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
        
    def __str__(self):
        return f"*** Computation Chain: {self.id}"
        #Processor.print(self)
        

class ProcessorScript(Processor):
    command:str = ''
    script_name:str = ''

    command_line_flag_template =''
    '''A :class:`tinc.processor.Processor` that executes a system process.
    '''
    def __init__(self, tinc_id = "_", input_dir = "", input_files = [],
                 output_dir = "", output_files = [], running_dir = ""):
        super().__init__(tinc_id, input_dir, input_files, output_dir, output_files, running_dir)
        self._arg_template = ''
        self._capture_output = False
        self._buffer_filename = ''

    def __str__(self):
        out = f"*** ProcessorScript : {self.id}"
        out += Processor.print(self)
        return out

    def set_command_line(self, cmd_line):
        i = cmd_line.find(' ')
        if i >= 0:
            self.command = cmd_line[0:i]
            self.set_argument_template(cmd_line[i+1:])
        else:
            self.command = cmd_line

    def set_argument_template(self, template):
        self._arg_template = template
        
    def capture_output(self, capture = True):
        if type(capture) == str:
            self.set_output_files([capture])
            self._capture_output = True
        elif type(capture) == bool:
           self._capture_output = capture
        else:
            raise ValueError("Must pass a boolean or a filename to capture to")

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
        cmd = self._make_command_line()
        try:
            if self.debug:
                print(f'Processor Running command: {cmd}')
            out = subprocess.check_output(shlex.split(cmd), cwd=wd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            print(e.output.decode('ascii'))
            print(repr(e))
            
            if self.done_callback is not None:
                self.done_callback(self, False)
            return False 

        fname = self._get_output_filename_read()
        if self._capture_output:
            with open(fname, 'wb') as f:
                f.write(out)
            if self.debug:
                print(f"Output captured to: {fname}")

        if len(self.output_files) > 0 and isinstance(self.output_files[0],DiskBuffer):
            self.output_files[0].load_data(fname)
            if self.debug:
                print(f"Output is disk buffer {self.output_files[0].id}: {fname}")

        if self.done_callback is not None:
            self.done_callback(self, True)
            
        if self.debug:
            print(f"Finished ProcessorScript '{self.id}'")
        return True

    def sanitize_name(filename):
        filename = filename.replace('(', '_')
        filename = filename.replace(')', '_')
        filename = filename.replace('<', '_')
        filename = filename.replace('>', '_')
        filename = filename.replace('*', '_')
        filename = filename.replace('"', '_')
        filename = filename.replace('[', '_')
        filename = filename.replace(']', '_')
        filename = filename.replace('|', '_')
        filename = filename.replace(':', '_')
        return filename

    def _make_command_line(self):
        cmd = self.command + " "
        if len(self.script_name) > 0:
            cmd += self.script_name + " "
        cmd += self._get_arguments()
        return cmd

    def _get_arguments(self):
        if self._arg_template == '':
            return ''
        args = self._arg_template

        for p in self._dimensions:

            if len(self.output_files) > 0 and not self._capture_output:
                fname = self._get_output_filename_write()
                # FIXME the buffer file will remain locked by the disk buffer if there is an exception in this function
                if fname is not None:
                    args = args.replace(f'%%:OUTFILE:0%%','"' + fname + '"') 

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

    def _get_output_filename_write(self):
        # TODO support multiple output files
        if len(self.output_files) == 0:
            return None
        if type(self.output_files[0]) == str: 
            fname = os.path.normpath(self.output_files[0])
        elif isinstance(self.output_files[0],DiskBuffer):
            fname = self.output_files[0].get_filename_for_writing()
        else:
            raise ValueError(f'Invalid type for output: {self.output_files[0]}')
        
        return fname

    def _get_output_filename_read(self):
        # TODO support multiple output files
        if type(self.output_files[0]) == str: 
            fname = os.path.normpath(self.output_files[0])
        elif isinstance(self.output_files[0],DiskBuffer):
            fname = self.output_files[0].get_filename_for_writing()
        
        return fname
        

class ProcessorScriptDocker(ProcessorScript):
    container_id = ''
    path_map = {}

    '''A :class:`tinc.processor.Processor` that executes a system process on a Docker container
    '''
    def set_container_id(self, container_id):
        if container_id is None or not type(container_id) == str:
            raise ValueError("Container id invalid")
        self.container_id = container_id
        
    def find_container_id(self, name):
        from subprocess import check_output
        docker_list = check_output(["docker", "ps", '--format', '{{.ID}}\t{{.Image}}\t{{.Names}}']).decode('ascii').splitlines()
        container_name = None
        for c in docker_list:
            if c.split('\t')[1] == name:
                container_name = c.split('\t')[2]
        return container_name

    def set_path_map(self, local_path, container_path):
        self.path_map[local_path] = container_path

    def _make_command_line(self):
        cmd = "docker exec " + self.container_id +" " + self.command + " "
        if len(self.script_name) > 0:
            cmd += self.script_name + " "
        cmd += self._get_arguments()
        return cmd

    def _get_output_filename_write(self):
        # TODO support multiple output files
        if len(self.output_files) == 0:
            return None
        if type(self.output_files[0]) == str: 
            fname = os.path.normpath(self.output_files[0])
        elif isinstance(self.output_files[0],DiskBuffer):
            fname = self.output_files[0].get_filename_for_writing()
        else:
            raise ValueError(f'Invalid type for output: {self.output_files[0]}')
        for local,remote in self.path_map.items():
            print(os.path.normpath(local), os.path.normpath(fname))
            if fname.find(local) == 0:
                fname = fname.replace(local, remote)
                break
            elif fname.find(os.path.normpath(local)) == 0:
                fname = fname.replace(os.path.normpath(local), remote)
                break
            elif os.path.normpath(fname).find(os.path.normpath(local)) == 0:
                fname = os.path.normpath(fname).replace(os.path.normpath(local), remote)
                break
        fname = fname.replace('\\', '/') # remote assumed to be Linux
        return fname

    def _get_output_filename_read(self):
        if len(self.output_files) == 0:
            return None
        # TODO support multiple output files
        if type(self.output_files[0]) == str: 
            fname = os.path.normpath(self.output_files[0])
        elif isinstance(self.output_files[0],DiskBuffer):
            fname = self.output_files[0].get_filename_for_writing()
        
        return fname

class ProcessorCpp(Processor):
    def __init__(self, name = "_", input_dir = "", input_files = [],
                 output_dir = "", output_files = [], running_dir = ""):
        super().__init__(name, input_dir, input_files,
                                               output_dir, output_files, running_dir)
    '''Placeholder for a remote Processor that executes C++ code.'''
    def __str__(self):
        out += f"*** C++ Processor: {self.id}"
        Processor.print(self)
