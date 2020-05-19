

class Processor(object):
    def __init__(self, name = "_", parent = "", input_dir = "", input_file = "",
                 output_dir = "", output_file = "", running_dir = ""):
        self.name = name
        self.parent = parent
        self.input_dir = input_dir
        self.input_file = input_file
        self.output_dir = output_dir
        self.output_file = output_file
        self.running_dir = running_dir
        self.configuration = {}
        
    def print(self):
        if self.input_dir:
            print(f"Input directory: {self.input_dir}")
        if self.input_file:
            print(f"Input file: {self.input_file}")
        if self.output_dir:
            print(f"Output directory: {self.output_dir}")
        if self.output_file:
            print(f"Output file: {self.output_file}")
        if self.running_dir:
            print(f"Running directory: {self.running_dir}")
        for key, value in self.configuration.items():
            print(f"['{key}'] = {value}")

class ComputationChain(Processor):
    def __init__(self, name = "_", parent = "", input_dir = "", input_file = "",
                 output_dir = "", output_file = "", running_dir = ""):
        super(ComputationChain, self).__init__(name, parent, input_dir, input_file,
                                               output_dir, output_file, running_dir)
        
    def print(self):
        print(f"*** Computation Chain: {self.name}")
        if self.parent:
            print(f"   *** Child of: {self.parent}")
        #Processor.print(self)
        

class DataScript(Processor):
    def __init__(self, name = "_", parent = "", input_dir = "", input_file = "",
                 output_dir = "", output_file = "", running_dir = ""):
        super(DataScript, self).__init__(name, parent, input_dir, input_file,
                                               output_dir, output_file, running_dir)
        self.name = name
        self.parent = parent
        
    def print(self):
        print(f"*** Data Script Processor: {self.name}")
        if self.parent:
            print(f"   *** Child of: {self.parent}")
        Processor.print(self)
        

class CppProcessor(Processor):
    def __init__(self, name = "_", parent = "", input_dir = "", input_file = "",
                 output_dir = "", output_file = "", running_dir = ""):
        super(DataScript, self).__init__(name, parent, input_dir, input_file,
                                               output_dir, output_file, running_dir)
        
    def print(self):
        print(f"*** C++ Processor: {self.name}")
        if self.parent:
            print(f"   *** Child of: {self.parent}")
        Processor.print(self)