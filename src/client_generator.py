import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


def get_client_segments(
    file_path: str = "data/ChallengeXHEC23022024.xlsx",
) -> pd.DataFrame:
    # Load data
    excel_data = pd.ExcelFile(file_path)

    jan24_df = pd.read_excel(excel_data, sheet_name="JAN24")
    clients_df = pd.read_excel(excel_data, sheet_name="clients")

    paris_center_coords = {"Latitude": 48.864716, "Longitude": 2.349014}

    clients_df["Distance from Paris Center"] = np.sqrt(
        (clients_df["Latitude"] - paris_center_coords["Latitude"]) ** 2
        + (clients_df["Longitude"] - paris_center_coords["Longitude"]) ** 2
    )

    # Convert service times to datetime
    fixed_date = pd.Timestamp("2024-01-01")
    jan24_df["Heure de début"] = pd.to_datetime(
        fixed_date.strftime("%Y-%m-%d")
        + " "
        + jan24_df["Heure de début"].astype(str)
    )
    jan24_df["Heure de fin"] = pd.to_datetime(
        fixed_date.strftime("%Y-%m-%d")
        + " "
        + jan24_df["Heure de fin"].astype(str)
    )

    jan24_df["Service Duration"] = (
        jan24_df["Heure de fin"] - jan24_df["Heure de début"]
    ).dt.total_seconds() / 60  # In Minutes

    client_service_count = jan24_df.groupby("ID Client")["Prestation"].count()
    client_service_duration = jan24_df.groupby("ID Client")[
        "Service Duration"
    ].sum()

    combined_client_data = clients_df.set_index("ID Client").join(
        [client_service_count, client_service_duration], how="left"
    )
    combined_client_data.rename(
        columns={
            "Prestation": "Total Services",
            "Service Duration": "Total Service Duration",
        },
        inplace=True,
    )
    combined_client_data["Average Service Duration"] = (
        combined_client_data["Total Service Duration"]
        / combined_client_data["Total Services"]
    )
    service_variety = jan24_df.groupby("ID Client")["Prestation"].nunique()

    combined_client_data = combined_client_data.join(
        service_variety, how="left"
    )
    combined_client_data.rename(
        columns={"Prestation": "Service Variety"}, inplace=True
    )

    total_days_in_january = jan24_df["Date"].nunique()
    combined_client_data["Service Frequency"] = (
        combined_client_data["Total Services"] / total_days_in_january
    )

    features_for_clustering = combined_client_data[
        [
            "Distance from Paris Center",
            "Total Services",
            "Total Service Duration",
            "Average Service Duration",
            "Service Variety",
            "Service Frequency",
        ]
    ]
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features_for_clustering)

    kmeans = KMeans(n_clusters=4, random_state=0)
    kmeans.fit(features_scaled)

    combined_client_data["Cluster"] = kmeans.labels_

    return combined_client_data[
        ["Latitude", "Longitude", "Cluster"]
    ].reset_index()


def generate_random_sessions(
    persona_group: int,
    df_client_with_persona: pd.DataFrame,
    df_clients: pd.DataFrame,
    df_sessions: pd.DataFrame,
    df_caregivers: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate new clients and add it into the raw dataset.

    Args:
        persona_group (str): One of the possible persona segments created
        df_client_with_persona (pd.DataFrame): Output from get_client_segments.
            Similar to client sessions but contains persona column
        df_clients (pd.DataFrame): raw clients data from excel sheet
        df_sessions (pd.DataFrame): raw sessions data from excel sheet
        df_caregivers (pd.DataFrame): raw caregivers data from excel sheet

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: new client data and new sessions data
    """
    print("Adding for persona group: ", persona_group)
    df_persona = df_client_with_persona[
        df_client_with_persona["Cluster"] == persona_group
    ].copy()

    """while len(df_persona) <= 2:
        all_personas = ["a", "b", "c", "e", "f", "h", "j", "k", "l"]
        persona_group = np.random.choice(all_personas)
        df_persona = df_client_with_persona[
            df_client_with_persona["client_persona"] == persona_group
            ].copy()"""

    df = df_sessions.merge(df_persona, how="right", on="ID Client")

    event_counts = df.groupby(["Cluster", "Date"])["Prestation"].count()

    event_probabilities = df.groupby("Cluster")["Prestation"].value_counts(
        normalize=True
    )

    # Take a random location for client
    client_loc = df_persona[["ID Client", "Latitude", "Longitude"]].sample(1)
    new_client_id = client_loc.pop("ID Client").iloc[0]
    client_loc = {
        k: list(v.values())[0] for k, v in client_loc.to_dict().items()
    }

    # Join new client to client dataset
    new_client = pd.DataFrame(
        {"ID Client": new_client_id} | client_loc, index=[len(df_clients)]
    )
    new_df_clients = pd.concat([df_clients, new_client])

    # Get event counts with a Poisson Distribution
    event_counts = df.groupby(["Cluster", "Date"])["Prestation"].count()
    event_counts = event_counts.loc[persona_group]

    event_counts_per_day = (
        df.groupby(["Cluster", "Date"])["Prestation"].count()
        / df.groupby("Cluster")["ID Client"].nunique()
    )
    mu = event_counts_per_day.mean()
    sim_event_counts = pd.Series(
        poisson.rvs(mu, size=df["Date"].nunique()), index=df["Date"].unique()
    )

    # Get event probabilities
    probs = event_probabilities.loc[persona_group]

    # Generate a random event until all events are complete
    new_events = pd.DataFrame(columns=df_sessions.columns)

    ## Choose a random event start time
    for date, count in sim_event_counts.to_frame().iterrows():
        count = count.iloc[0]
        if count == 0:
            continue

        # Assign events based on probabilities
        events = np.random.choice(probs.index, count, p=probs.values)

        # From these events, sample times
        times = pd.DataFrame(
            [
                df[df["Prestation"] == event][
                    ["Heure de début", "Heure de fin"]
                ]
                .sample(1)
                .squeeze()
                .to_list()
                for event in events
            ],
            columns=["Heure de début", "Heure de fin"],
        )

        new_row = pd.DataFrame(
            {
                "ID Client": [new_client_id] * count,
                "ID Intervenant": [
                    df_caregivers["ID Intervenant"].sample(1).iloc[0]
                ]
                * count,
                "Date": [date] * count,
                "Heure de début": times["Heure de début"].to_list(),
                "Heure de fin": times["Heure de fin"].to_list(),
                "Prestation": events,
            }
        )

        new_events = pd.concat([new_events, new_row])

    new_df_sessions = (
        pd.concat([df_sessions, new_events])
        .sort_values(by="Date")
        .reset_index(drop=True)
    )
    return new_df_clients, new_df_sessions


def add_new_clients_and_sessions(
    n_clients: int,
    random_client_segment: bool = True,
    client_personas_sequence: str = None,
    all_personas: list[str] = [0, 1, 2, 3],
    excel_file: str = "data/ChallengeXHEC23022024.xlsx",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add new clients to clients dataframe and new sessions based on these clients to sessions dataset.

    Args:
        n_clients (int): number of clients to add
        random_client_segment (bool, optional): whether to add random segments of clients or fixed. Defaults to False.
        client_personas_sequence (list[str], optional): If random_client_segment is set to False A list of client segments
            that has the same length as n_clients to add must be specified. Defaults to None.
        all_personas (list[str], optional): List of all personas. Defaults to [0,1,2,3].
        excel_file (str, optional): filepath for Excel document. Defaults to "data/ChallengeXHEC23022024.xlsx".

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: Tuple of new Client DataFrame and new Sessions DataFrame
    """
    # Adding Clients
    df_clients = pd.read_excel(excel_file, sheet_name=1)
    intervenants_df = pd.read_excel(excel_file, sheet_name=2)
    df_sessions = pd.read_excel(excel_file, sheet_name=0)
    client_segments = get_client_segments()

    # If we want random segments of clients
    if random_client_segment:
        clients = np.random.choice(all_personas, n_clients)
        for client_persona in clients:
            df_clients, df_sessions = generate_random_sessions(
                client_persona,
                client_segments,
                df_clients,
                df_sessions,
                df_caregivers=intervenants_df,
            )
        return df_clients, df_sessions

    # If we want a fixed segment of clients
    # The length of the sequence must match the length of the n_clients we want to add
    # assert n_clients == len(client_personas_sequence)

    for client_persona in client_personas_sequence:
        df_clients, df_sessions = generate_random_sessions(
            int(client_persona),
            client_segments,
            df_clients,
            df_sessions,
            df_caregivers=intervenants_df,
        )
    return df_clients, df_sessions
