# -*- coding: utf-8 -*-
"""
Created on July 19 2021

@author: Andres
"""

import os
import glob

try:
    from ipywidgets import interact, interactive, interact_manual
    import ipywidgets as widgets
except:
    pass


class PresetHandler(object) :
    '''Manage preset read and write for parameters
    
    :param root_dir: Path where presets are stored
    '''
    def __init__(self, root_dir = "presets/"):
        self.root_dir = root_dir
        if len(self.root_dir) > 0 and not self.root_dir[-1] == "/":
            self.root_dir += '/'
        if not os.path.exists(self.root_dir):
            os.makedirs(self.root_dir)
        self._sub_dir = ''
        self._presets_map = {}
        self.set_preset_map("default")
        self._parameters = []
        self._interactive_widget = None
        self._interactive_store_widget = None
        pass

    def store_preset(self, name):
        '''Store the current values in a preset.

        The preset name will determine the file name. See :meth:`tinc.preset_handler.PresetHandler.store_preset_index`
        
        Will overwrite preset if name exists.

        :param name: Name for the preset.
        '''
        index = -1
        name = name.replace(':', "_") # names can't have colons.
        name = name.replace(' ', "_") # names can't have spaces.
        for entry in self._presets_map.items():
            if entry[1] == name:
                index = entry[0]
                self.store_preset_index(index, name)
                return
        index = 0
        for entry in self._presets_map.items():
            if index <= entry[0]:
                index = entry[0] + 1
    
        self.store_preset_index(index, name)

    def store_preset_index(self, index, name = "", overwrite = True):
        '''Store preset by index'''
        name = name.replace(':', "_") # names can't have colons.
        name = name.replace(' ', "_") # names can't have spaces.
        if name == '':
            for entry in self._presets_map.items():
                if entry[0] == index:
                    name = entry[1]
                    break
            if name == '':
                name = str(index)
        values = {}
        for p in self._parameters:
            values[p.get_osc_address()] = p.value
        self._presets_map[index] = name
        self._save_preset_values(values, name, overwrite)
        self._store_current_preset_map()
        self._configure_widget()

    def recall_preset(self, name):
        '''Recall parameter values from preset.'''
        path = self.root_dir + self._sub_dir + name + ".preset"
        if not os.path.exists(path):
            print(f"Preset '{name}' does not exist. No preset loaded")
            return False
        with open(path) as f:
            for line in f.readlines():
                if line[:2] == "::":
                    break
                parts = line.split()
                for p in self._parameters:
                    if p.get_osc_address() == parts[0]:
                        if parts[1] == 'f':
                            p.set_value(float(parts[2]))
                        elif parts[1] == 'i':
                            p.set_value(int(parts[2]))
                        elif parts[1] == 's':
                            # FIXME support whitespace in string
                            p.set_value(parts[2][1:-1])
        return True

    def rename_preset(self, name, new_name):
        for entry in self._presets_map.items():
            if entry[1] == name:
                path = self.root_dir + self._sub_dir + name + ".preset"
                new_path = self.root_dir + self._sub_dir + new_name + ".preset"
                os.rename(path, new_path)
                self._presets_map[entry[0]] = new_name
                
                self._store_current_preset_map()
                self._configure_widget()
                return True
        return False
    
    def recall_preset_index(self, index):
        for entry in self._presets_map.items():
            if entry[0] == index:
                return self.recall_preset(entry[1])

        return False

    def available_presets(self):
        '''Return a list of currently available presets.'''
        return [entry[1] for entry in self._presets_map.items()]

    def register_parameter(self, parameter):
        '''Register a parameter with the preset handler
        
        Parameters that have been registered will be modified when presets are recalled
        and will provide their current value when presets are stored.
        '''
        self._parameters.append(parameter)

    def set_sub_dir(self, subdir):
        self._sub_dir = subdir

    def interactive_widget(self):
        if self._interactive_widget is None:
            self._interactive_widget = interactive(self.__set_from_internal_widget, value = widgets.Dropdown(
                    options=['dummy'],
                    # value='dummy',
                    description='Preset:',))
        self._configure_widget()
        return self._interactive_widget

    def interactive_store_widget(self):
        if self._interactive_store_widget is None:
            self._interactive_store_widget= widgets.Button(description='Store preset',)
            self._interactive_store_widget.on_click(self._on_store_button_clicked)
        return self._interactive_store_widget

    def _on_store_button_clicked(self, b):
        max_index = 0
        for index in self._presets_map:
            if max_index <= index:
                max_index = index + 1
        self.store_preset_index(max_index)

    def _configure_widget(self):
        if not self._interactive_widget:
            return
        options = []
        for entry in self._presets_map.items():
            options.append(entry[1])
        self._interactive_widget.children[0].options = options
    
    def __set_from_internal_widget(self, value):
        self.recall_preset(value)

    def set_preset_map(self, preset_map_name):
        '''Set the current map for indeces to preset names
        
        The maps are stored in the file system with extension .presetMap
        '''
        self._current_map_name = preset_map_name
        map_path = self._build_map_path(preset_map_name)
        if not os.path.exists(map_path):
            count = 0
            for p in glob.glob(self.root_dir + self._sub_dir + "*.preset"):
                if p.count('/') > 0:
                    self._presets_map[count] = p[p.rfind('/'): -7]
            self._store_current_preset_map(preset_map_name)
        else:
            with open(map_path) as f:
                for line in f.readlines():
                    if line[:2] == "::" or line == "\n":
                        break
                    parts = line.split(':')
                    if len(parts) == 2:
                        self._presets_map[int(parts[0])] = parts[1][:-1] # remove trailing newline

    def _save_preset_values(self, values, name, overwrite = True):
        path = self.root_dir + self._sub_dir + name + ".preset"
        # TODO check for overwrite
        with open(path, 'w') as f:
            for v in values.items():
                line = f"{v[0]} "
                # TODO support parameters with more than one value (e.g. color)
                if type(v[1]) == float: 
                    line += f'f {v[1]}\n'
                elif type(v[1]) == int: 
                    line += f'i {v[1]}\n'
                elif type(v[1]) == str: 
                    line += f's "{v[1]}"\n'
                else:
                    print("Unsupported type for preset")
                    continue
                f.write(line)
            f.write("::\n")
        

    def _store_current_preset_map(self, map_name = '', use_sub_dir = False):
        if map_name != '':
            self._current_map_name = map_name

        map_path = self._build_map_path(self._current_map_name, use_sub_dir)
        with open(map_path, 'w') as f:
            for entry in self._presets_map.items():
                f.write(str(entry[0]) + ':' + entry[1] + '\n')
            f.write('::\n')

    def _build_map_path(self, map_name, use_sub_dir = False):
        if not map_name[-10:] == ".presetMap":
            map_name += ".presetMap"
        if use_sub_dir:
            map_name = self._sub_dir + map_name
        return self.root_dir + map_name
