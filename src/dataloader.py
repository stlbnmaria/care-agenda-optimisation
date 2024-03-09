from datetime import datetime
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
        if df.columns[0] != "pair":  # standardizing column names
            df = df.rename(columns={df.columns[0]: "pair"})
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
    caregivers_commute["commute_method"] = "driving"

    # TODO: filter for the correct commute so that it is not double if kind == license
    #       and adapt the commute above
    # caregivers["Commute Method"] = caregivers["Véhicule personnel"].map(
    #     {"Oui": "driving", "Non": "bicycling", np.nan: "bicycling"}
    # )  # map commute method

    # merge all data
    commute_data_df = pd.concat([commute_data_df, caregivers_commute], axis=0)

    # create commute in minutes
    commute_data_df["commute_minutes"] = (
        commute_data_df["commute_seconds"] / 60
    )

    # save to csv
    commute_data_df.to_csv(f"data/commute_{kind}_all.csv", index=False)


def create_schedule_df() -> None:
    excel_file = Path("data/ChallengeXHEC23022024.xlsx")
    schedule = pd.read_excel(excel_file, sheet_name=0)
    caregivers = pd.read_excel(excel_file, sheet_name=2)

    sched_one_day = schedule.loc[schedule.Date == "2024-01-03", :]

    discard_list = [
        "ADMINISTRATION",
        "VISITE MEDICALE",
        "FORMATION",
        "COORDINATION",
        "HOMMES TOUTES MAINS",
    ]

    sched_one_day = sched_one_day[~sched_one_day.Prestation.isin(discard_list)]

    sched_one_day["idx"] = sched_one_day.index

    common_date = sched_one_day["Date"].iloc[0]
    sched_one_day["Heure de fin"] = sched_one_day["Heure de fin"].apply(
        lambda x: datetime.combine(common_date, x)
    )
    sched_one_day["Heure de début"] = sched_one_day["Heure de début"].apply(
        lambda x: datetime.combine(common_date, x)
    )
    sched_one_day["Duration"] = (
        sched_one_day["Heure de fin"] - sched_one_day["Heure de début"]
    )
    sched_one_day["Duration"] = sched_one_day["Duration"].apply(
        lambda x: x.seconds // 60
    )

    before_first_client = caregivers[["ID Intervenant"]].copy()
    before_first_client["ID Client"] = caregivers["ID Intervenant"]
    before_first_client["Duration"] = 0
    before_first_client["Date"] = pd.to_datetime("2024-01-03")
    before_first_client["Heure de début"] = before_first_client[
        "Date"
    ] + pd.Timedelta(hours=5)
    before_first_client["Heure de fin"] = before_first_client[
        "Date"
    ] + pd.Timedelta(hours=5)
    before_first_client["Prestation"] = "COMMUTE"
    before_first_client["idx"] = before_first_client.index

    after_last_client = caregivers[["ID Intervenant"]].copy()
    after_last_client["ID Client"] = caregivers["ID Intervenant"]
    after_last_client["Duration"] = 0
    after_last_client["Date"] = pd.to_datetime("2024-01-03")
    after_last_client["Heure de début"] = after_last_client[
        "Date"
    ] + pd.Timedelta(hours=22)
    after_last_client["Heure de fin"] = after_last_client[
        "Date"
    ] + pd.Timedelta(hours=22)
    after_last_client["Prestation"] = "COMMUTE"
    after_last_client["idx"] = before_first_client.index + 10000

    sched_one_day = pd.concat(
        [sched_one_day, before_first_client], ignore_index=True
    )
    sched_one_day = pd.concat(
        [sched_one_day, after_last_client], ignore_index=True
    )

    sched_one_day = sched_one_day.sort_values("Heure de début")
    sched_one_day.to_csv("data/schedule_2024-03-01.csv", index=False)


if __name__ == "__main__":
    create_commute_df(kind="driving")
    # create_commute_df(kind="license")

    create_schedule_df()
