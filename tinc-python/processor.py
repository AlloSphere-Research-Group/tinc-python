

class Processor(object):
    def __init__(self, name = "_", input_dir = "", input_files = [],
                 output_dir = "", output_files = [], running_dir = ""):
        self.name = name
        self.input_dir = input_dir
        self.input_files = input_files
        self.output_dir = output_dir
        self.output_files = output_files
        self.running_dir = running_dir
        self.configuration = {}
        self.parent = None
        
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

class ComputationChain(Processor):
    def __init__(self, name = "_", input_dir = "", input_files = [],
                 output_dir = "", output_files = [], running_dir = ""):
        super(ComputationChain, self).__init__(name, input_dir, input_files,
                                               output_dir, output_files, running_dir)
        
    def print(self):
        print(f"*** Computation Chain: {self.name}")
        #Processor.print(self)
        

class ScriptProcessor(Processor):
    def __init__(self, name = "_", input_dir = "", input_files = [],
                 output_dir = "", output_files = [], running_dir = ""):
        super(ScriptProcessor, self).__init__(name, input_dir, input_files,
                                               output_dir, output_files, running_dir)
        self.name = name
        
    def print(self):
        print(f"*** Data Script Processor: {self.name}")
        if self.parent:
            print(f"   *** Child of: {self.parent}")
        Processor.print(self)
        

class CppProcessor(Processor):
    def __init__(self, name = "_", input_dir = "", input_files = [],
                 output_dir = "", output_files = [], running_dir = ""):
        super(CppProcessor, self).__init__(name, input_dir, input_files,
                                               output_dir, output_files, running_dir)
        
    def print(self):
        print(f"*** C++ Processor: {self.name}")
        Processor.print(self)