# Home Care Agenda Optimisation
[![Python Version](https://img.shields.io/badge/python-3.9-blue.svg)]()
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![Linting: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-informational?logo=pre-commit&logoColor=white)](https://github.com/stlbnmaria/care-agenda-optimisation/blob/main/.pre-commit-config.yaml)

Authors: Elizaveta Barysheva, Kaan Caylan, Joao Melo, Steve Moses, Madhura Nirale & Maria Susanne Stoelben

## Description

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

## Run the App
In the app you can explore some interactive data analysis as well as the comparison of given and optimised schedule.
```bash
cd app/
streamlit run 🏡_Home.py
```
