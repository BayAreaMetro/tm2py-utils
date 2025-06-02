# tm2py-utils
Travel Model Two utilities, including post-processing, summaraziation and other utilities for tm2py.  
To Run tm2py the [Travel Model Two (tm2) repo](https://github.com/BayAreaMetro/tm2py) for model running. 
* __Note:__ tm2py-utils was separated out to allow for a the usage of a wide variety of packages without affecting / breaking the main model. This allows for fast development of utilities with relative stability of the model.

## License

[Include license info if applicable]

## Installation
The environment is intended to work with the python 
### Quick Start
If you only require the usage of Acceptance Criteria Tools, you can install directly from git:  
1) open OpenPaths EMME Shell 24.01.00

2) Install TM2PY Utils
```python
pip install git+https://github.com/BayAreaMetro/tm2py-utils.git
```

### Development
If you would like to develop and/or download example notebooks
1) Open OpenPaths Shell Emme Shell (24.01.00)

2) Create and activate your virtual Environement 
```bash
python -m venv /path/to/venv
```

3) __Optional__ if you would like access to OpenPaths API:  
Copy emmepath file (usually found in C:\Program Files\Bentley\OpenPaths\EMME 24.01.00) to venv/path/to/venv/Lib/site-packages

4) clone tm2py-utils in the appropriate directory
```bash
cd path/to/git/repo/location
git clone https://github.com/BayAreaMetro/tm2py-utils.git
```
5) Install tm2py-utils in your virtual environment
```
cd tm2py-utils
pip install -e .
```
* __Note:__ The environment is fairly lightweight and should work installed on top of an existing tm2py installation, if this is done it is recommended to create a separate virtual environment. 

## Examples / Features
if the package was installed correctly you should be able to run the below
### Acceptance Criteria
Generate files related to acceptance criteria
```python
from tm2py_utils.acceptance.canonical import Canonical
from tm2py_utils.acceptance.observed import Observed
from tm2py_utils.acceptance.simulated import Simulated
from tm2py_utils.acceptance.acceptance import Acceptance

# Note, these will have to point to the correct files of a successfully run model
scenario_config_file = "scenario_config.toml"
model_config_file = "model_config.toml"
canonical_crosswalk_file = "acceptance/canonical_crosswalk.toml"
observed_config_file = "acceptance/observed_data.toml"
output_folder_root = "output_summaries/"

c = Canonical(canonical_crosswalk_file, scenario_file=scenario_config_file)

o = Observed(canonical=c, observed_file=observed_config_file)

s = Simulated(canonical=c, scenario_file=scenario_config_file, model_file=model_config_file)

a = Acceptance(canonical=c, simulated=s, observed=o, output_file_root=output_folder_root)

a.make_acceptance(make_transit=True, make_roadway=True, make_other=True)
```

### Archive model run
Archive important Files of a specific model run into an archive directory.

assuming your environment is active, you can ensure this by running:
```cmd
\path\to\venv\Scripts\activate
```

A model run can then be archived using:
```cmd
tm2py-utils archive path\to\model\run path\to\model\run
```
or

```cmd
tm2py-utils archive path\to\model\run path\to\model\run -n "run name"
```

Alternatively python script can be used
```python
from tm2py_utils.scripts.archive import parse_cli_archive
parse_cli_archive(r"model\run\directory", r"archive\run\directory")
```
