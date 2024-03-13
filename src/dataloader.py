from pathlib import Path
from typing import Tuple
import argparse
import pandas as pd

from config.availability import CAREGIVER_AVAILABILITY_DICT
from src.client_generator import add_new_clients_and_sessions
import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)


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
    - kind (str): Kind of commute (either driving for all or by bicycling).

    Returns: None
    """
    # loading and merging commute data
    commute_file_paths = [
        f"data/commute_{kind}_clients.csv",
        f"data/commute_{kind}_care_clients.csv",
        f"data/commute_{kind}_clients_care.csv",
    ]
    commute_dataframes = [pd.read_csv(file) for file in commute_file_paths]
    for df in commute_dataframes:
        if df.columns[0] != ["pair"]:  # standardizing column names
            df.rename(columns={df.columns[0]: "pair"}, inplace=True)
    commute_data_df = pd.concat(commute_dataframes, ignore_index=True)

    # create dummy commutes between the same caregivers home
    caregivers = pd.read_excel("data/ChallengeXHEC23022024.xlsx", sheet_name=2)

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
    caregivers_commute["commute_method"] = kind

    # merge all data
    commute_data_df = pd.concat([commute_data_df, caregivers_commute], axis=0)

    # create commute in minutes
    commute_data_df["commute_minutes"] = (
        commute_data_df["commute_seconds"] / 60
    )

    # save to csv
    commute_data_df.to_csv(f"data/commute_{kind}_all.csv", index=False)


def create_schedule_df(generate_new_clients: bool, **kwargs) -> None:
    """Creates schedule data for optimisation for all days.

    Parameters: None

    Returns: None
    """
    # load all necessary files
    excel_file = Path("data/ChallengeXHEC23022024.xlsx")
    schedule = pd.read_excel(excel_file, sheet_name=0)
    caregivers = pd.read_excel(excel_file, sheet_name=2)

    if generate_new_clients:
        df_clients, schedule = add_new_clients_and_sessions(**kwargs)

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


def create_transport_possibilities(kind: str = "license") -> None:
    excel_file = Path("data/ChallengeXHEC23022024.xlsx")
    caregivers = pd.read_excel(excel_file, sheet_name=2)

    # get license information
    caregiver_transport = caregivers[["ID Intervenant", "Permis"]]
    caregiver_transport = caregiver_transport.fillna("Non")
    caregiver_transport = caregiver_transport.replace(
        {"Oui": True, "Non": False}
    )

    # dummy value for driving
    if kind == "driving":
        caregiver_transport["Permis"] = True

    caregiver_transport.to_csv(
        f"data/caregiver_transport_{kind}.csv", index=False
    )


def get_commute_data(
    commute_file_paths: list[str] = [
        "data/commute_bicycling_clients.csv",
        "data/commute_driving_clients.csv",
        "data/commute_bicycling_care_clients.csv",
        "data/commute_bicycling_clients_care.csv",
        "data/commute_driving_care_clients.csv",
        "data/commute_driving_clients_care.csv",
    ]
) -> pd.DataFrame:

    commute_dataframes = [pd.read_csv(file) for file in commute_file_paths]

    for df in commute_dataframes:
        if df.columns[0] not in ["pair"]:  # standardizing column names
            df.rename(columns={df.columns[0]: "pair"}, inplace=True)

    commute_data_df = pd.concat(commute_dataframes, ignore_index=True)
    commute_data_df[["source", "destination"]] = commute_data_df[
        "pair"
    ].str.extract(r"\((\d+), (\d+)\)")
    commute_data_df.drop(columns="pair", inplace=True)
    commute_data_df.set_index(
        ["source", "destination", "commute_method"], inplace=True
    )
    return commute_data_df


def load_and_save_data(generate_new_clients: bool = False, **kwargs):
    create_schedule_df(generate_new_clients, **kwargs)
    create_caregiver_availability()
    create_commute_df(kind="driving")
    create_commute_df(kind="bicycling")
    create_transport_possibilities(kind="license")
    create_transport_possibilities(kind="driving")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Main function with argparse")

    parser.add_argument(
        "--generate-new-clients",
        action="store_true",
        default=False,
        help="Boolean flag to generate new clients",
    )
    parser.add_argument(
        "--n-clients", type=int, default=1, help="Number of new clients"
    )
    parser.add_argument(
        "--random-client-segment",
        action="store_true",
        help="Boolean flag for random client segment",
    )
    parser.add_argument(
        "--client-personas-sequence",
        nargs="+",
        type=int,
        default=None,
        help="List of client personas sequence",
    )

    args = parser.parse_args()

    load_and_save_data(**vars(args))
