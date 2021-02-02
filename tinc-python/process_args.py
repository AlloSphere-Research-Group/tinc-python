# -*- coding: utf-8 -*-
"""
Created on Thu Apr 25 17:15:01 2019

@author: andres
"""
import argparse,json

# TODO add mutually exclusive options for config.json file vs. user provided arguments.

# TODO provision for all functionality from argparse

# TODO verify and report missing arguments in json config if args provided

# TODO set __running_dir for command line args automatically

class TincArgumentParser(argparse.ArgumentParser):
    def __init__(self, **kwargs):
        super(TincArgumentParser, self).__init__(**kwargs)
        import sys
        if len(sys.argv) == 2 and sys.argv[1][-5:] == ".json":
            self.config_file = sys.argv[1]
        else:
            self.config_file = None
        # self.add_argument('config_file', type=str, default="config.json", nargs='?')

    def get_args(self):
      if  self.config_file is None:
          print("TincArgumentParser: No config file provided, setting defaults")
          args = vars(self.parse_args())
          if '__input_names' in args and type(args['__input_names']) != list:
              args['__input_names'] = [args['__input_names']]
          if '__output_names' in args and type(args['__output_names']) != list:
              args['__output_names'] = [args['__output_names']]
          return args
      with open(self.config_file) as cf:
            out_args = json.load(cf)
            if '__tinc_metadata_version' in out_args:
                print("Reading TINC json for command line args")
                # Check we have a TINC json config file, otherwise do regular arg parsing
                return out_args
            else:
                print("__tinc_version not found in json. Using regular argparse.")
                p_args = self.parse_args()
                out_args = vars(p_args)
      return out_args

      def write_args(self, out_args):
        with open(self.config_file, "w") as cf:
          json.dump(out_args, cf)
