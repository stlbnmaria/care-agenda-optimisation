# Home Care Agenda Optimisation
[![Python Version](https://img.shields.io/badge/python-3.9-blue.svg)]()
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![Linting: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-informational?logo=pre-commit&logoColor=white)](https://github.com/stlbnmaria/care-agenda-optimisation/blob/main/.pre-commit-config.yaml)

Authors: Elizaveta Barysheva, Kaan Caylan, Joao Melo, Steve Moses, Madhura Nirale & Maria Susanne Stoelben

## Description
This project is about optimizing a home care agenda by minimizing commute time, number of short downtimes (less than 30 minutes) and carbon emissions. Additionally, a streamlit app was built to interactively explore the data as well as the optimisation results. Furthermore, the Grand Est region was analysed regarding market potential.

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

```bash
pip install -r requirements-dev.txt
pre-commit install
```

## Load Data

To run dataloader before optimisation problem
```bash
python3 src/dataloader.py
```

To generate new clients to the preprocessed data:
```bash
python3 python src/dataloader.py --generate-new-clients --n-clients 5 --random-client-segment
```

Number of clients may be changed using --n_clients argument. Default setting generates clients from random
segments. If you want to specify the segments from which you want to create clients from:

```bash
python3 src/dataloader.py --generate-new-clients --n-clients 3  --client-personas-sequence "13210"
```

where the sequence is the sequence of client segments to add. Its length must match n-clients to add

## Run optimizer
```bash
python src/optimiser.py
```
Arguments to script may be added according to desired optimisation.

Available arguments:

- --include_availability (bool) : Take caregiver availability into account.
- --filter_for_competence (bool) : Filter for competence of caregivers.
- --carbon_reduction (bool) : Include carbon emission in the optimisation function.
- --transport (str) : Type of transport. Defaults to "license"
- --time_limit (int) : Maximum time limit to run one optimisation problem in seconds.
