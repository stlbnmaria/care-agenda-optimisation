from pathlib import Path
from typing import Tuple

import pandas as pd

from config.availability import CAREGIVER_AVAILABILITY_DICT


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


def create_commute_df(kind: str = "driving") -> None:
    """Loads all the commute data and creates a whole df based on kind.

    Parameters:
    - kind (str): Kind of commute (either driving for all or by license).

    Returns: None
    """
    # loading and merging commute data
    commute_file_paths = [
        "data/commute_driving_clients.csv",
        "data/commute_driving_care_clients.csv",
        "data/commute_driving_clients_care.csv",
    ]
    if kind == "license":
        commute_file_paths = commute_file_paths + [
            "data/commute_bicycling_clients.csv",
            "data/commute_bicycling_care_clients.csv",
            "data/commute_bicycling_clients_care.csv",
        ]
    commute_dataframes = [pd.read_csv(file) for file in commute_file_paths]
    for df in commute_dataframes:
        if df.columns[0] != ["pair"]:  # standardizing column names
            df.rename(columns={df.columns[0]: "pair"}, inplace=True)
    commute_data_df = pd.concat(commute_dataframes, ignore_index=True)

    # create dummy commutes between the same caregivers home
    caregivers = pd.read_excel("data/ChallengeXHEC23022024.xlsx", sheet_name=2)

    if kind == "license":
        methods = ["driving", "bicycling"]
    else:
        methods = ["driving"]

    for commute in methods:
        caregivers_commute = pd.DataFrame(
            {
                "source": caregivers["ID Intervenant"].unique(),
                "destination": caregivers["ID Intervenant"].unique(),
            }
        )
        caregivers_commute.insert(0, "commute_meters", 0)
        caregivers_commute.insert(0, "commute_seconds", 0)
        caregivers_commute.insert(
            0, "pair", list(zip(caregivers_commute.source, df.destination))
        )
        caregivers_commute["commute_method"] = commute

        # merge all data
        commute_data_df = pd.concat(
            [commute_data_df, caregivers_commute], axis=0
        )

    # create commute in minutes
    commute_data_df["commute_minutes"] = (
        commute_data_df["commute_seconds"] / 60
    )

    # save to csv
    commute_data_df.to_csv(f"data/commute_{kind}_all.csv", index=False)


def create_schedule_df() -> None:
    """Creates schedule data for optimisation for all days.

    Parameters: None

    Returns: None
    """
    # load all necessary files
    excel_file = Path("data/ChallengeXHEC23022024.xlsx")
    schedule = pd.read_excel(excel_file, sheet_name=0)
    caregivers = pd.read_excel(excel_file, sheet_name=2)

    # filter all data to contain only wanted prestation
    discard_list = [
        "ADMINISTRATION",
        "VISITE MEDICALE",
        "FORMATION",
        "COORDINATION",
        "HOMMES TOUTES MAINS",
    ]
    schedule = schedule[~schedule.Prestation.isin(discard_list)]

    schedule = schedule.copy()

    schedule["Heure de début"] = pd.to_datetime(
        schedule["Date"].astype(str)
        + " "
        + schedule["Heure de début"].astype(str)
    )
    schedule["Heure de fin"] = pd.to_datetime(
        schedule["Date"].astype(str)
        + " "
        + schedule["Heure de fin"].astype(str)
    )

    for date in schedule.Date.unique():
        # create dummy sessions for caregivers for beginning of day
        before_first_client = caregivers[["ID Intervenant"]].copy()
        before_first_client["ID Client"] = caregivers["ID Intervenant"]
        before_first_client["Date"] = pd.to_datetime(date)
        before_first_client["Heure de début"] = before_first_client[
            "Date"
        ] + pd.Timedelta(hours=5)
        before_first_client["Heure de fin"] = before_first_client[
            "Date"
        ] + pd.Timedelta(hours=5)
        before_first_client["Prestation"] = "COMMUTE"

        # create dummy sessions for caregivers for end of day
        after_last_client = caregivers[["ID Intervenant"]].copy()
        after_last_client["ID Client"] = caregivers["ID Intervenant"]
        after_last_client["Date"] = pd.to_datetime(date)
        after_last_client["Heure de début"] = after_last_client[
            "Date"
        ] + pd.Timedelta(hours=22)
        after_last_client["Heure de fin"] = after_last_client[
            "Date"
        ] + pd.Timedelta(hours=22)
        after_last_client["Prestation"] = "COMMUTE"

        schedule = pd.concat(
            [schedule, before_first_client], ignore_index=True
        )
        schedule = pd.concat([schedule, after_last_client], ignore_index=True)

    # sort values and create index for sessions
    schedule = schedule.sort_values(["Heure de début", "Heure de fin"])
    schedule = schedule.reset_index(drop=True)
    schedule["idx"] = schedule.index

    # create session duration in minutes
    schedule["Duration"] = (
        schedule["Heure de fin"] - schedule["Heure de début"]
    )
    schedule["Duration"] = schedule["Duration"].apply(
        lambda x: x.seconds // 60
    )

    # create start time in minutes
    schedule["Start_time"] = (
        schedule["Heure de début"] - pd.to_datetime(schedule["Date"])
    ).dt.seconds
    schedule["Start_time"] = schedule["Start_time"].apply(lambda x: x // 60)

    # drop caregiver to be sure
    schedule = schedule.drop(columns="ID Intervenant")

    # save data to csv
    schedule.to_csv("data/schedule.csv", index=False)


def create_caregiver_availability() -> None:
    caregiver_avail_df = pd.DataFrame(
        list(CAREGIVER_AVAILABILITY_DICT.items()),
        columns=["ID Intervenant", "UNDISP_DAYS"],
    )
    caregiver_avail_df.to_csv("data/caregiver_avail.csv", index=False)


if __name__ == "__main__":
    create_commute_df(kind="driving")
    create_commute_df(kind="license")

    create_schedule_df()
    create_caregiver_availability()
