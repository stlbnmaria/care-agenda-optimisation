from pathlib import Path
from typing import Tuple

import pandas as pd


def load_data(excel_file: Path) -> Tuple[pd.DataFrame]:
    """Loads data from an Excel file containing schedule, clients, and caregivers.

    Parameters:
    - excel_file (Path): Path to the Excel file.

    Returns:
    Tuple[pd.DataFrame]: A tuple containing three DataFrames:
        1. Schedule DataFrame with schedule information.
        2. Clients DataFrame with client information.
        3. Caregivers DataFrame with caregiver information.
    """
    schedule = pd.read_excel(excel_file, sheet_name=0)
    clients = pd.read_excel(excel_file, sheet_name=1)
    caregivers = pd.read_excel(excel_file, sheet_name=2)

    return schedule, clients, caregivers
