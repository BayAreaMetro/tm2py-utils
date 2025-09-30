from tm2py_utils.summary.acceptance.canonical import Canonical
from tm2py_utils.summary.acceptance.observed import Observed
from tm2py_utils.summary.acceptance.simulated import Simulated
from tm2py_utils.summary.acceptance.acceptance import Acceptance

# Note, these will have to point to the correct files of a successfully run model
scenario_config_file = "E:/GitHub/tm2/tm2py-utils/tm2py_utils/examples/scenario_config.toml"
model_config_file = "E:/GitHub/tm2/tm2py-utils/tm2py_utils/examples/model_config.toml"
canonical_crosswalk_file = "E:/GitHub/tm2/tm2py-utils/tm2py_utils/examples/canonical_crosswalk.toml"
observed_config_file = "E:/GitHub/tm2/tm2py-utils/tm2py_utils/examples/observed_data.toml"
output_folder_root = "E:/TM2/2015_TM2_20250619/acceptance"

print("Processing Canonical Files")
c = Canonical(canonical_crosswalk_file, scenario_file=scenario_config_file)

print("Processing Observed Data")
o = Observed(canonical=c, observed_file=observed_config_file)

print("Processing Simulated Data")
s = Simulated(canonical=c, scenario_file=scenario_config_file, model_file=model_config_file)

print("Processing Acceptance Data")
a = Acceptance(canonical=c, simulated=s, observed=o, output_file_root=output_folder_root)

a.make_acceptance(make_roadway=True, make_other=True)