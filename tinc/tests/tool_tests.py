from tinc import *

data_dir = r'C:\Users\Andres\source\repos\vdv_data\nbO_2chempot'

def read_func(path):
    with open(path) as f:
        j = json.load(f)
    return j

ps = extract_parameter_space_from_output(data_dir, "results.json", read_func)

ps.print()

print(ps.get_dimension("is_equilibrated").values)
print(ps.get_dimension("param_chem_pot(b)").values)
print(ps._path_template)
print(ps.get_current_relative_path())
