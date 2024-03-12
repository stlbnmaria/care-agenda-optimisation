import pandas as pd
import numpy as np


def get_client_segments(file_path: str = "../data/ChallengeXHEC23022024.xlsx"):
    excel_data = pd.ExcelFile(file_path)
    jan24_df = pd.read_excel(excel_data, sheet_name="JAN24")
    clients_df = pd.read_excel(excel_data, sheet_name="clients")

    # Analyzing client data to create personas
    paris_center_coords = {"Latitude": 48.864716, "Longitude": 2.349014}

    # Calculating the distance of each client from the Paris city center
    clients_df["Distance from Paris Center"] = (
        (clients_df["Latitude"] - paris_center_coords["Latitude"]) ** 2
        + (clients_df["Longitude"] - paris_center_coords["Longitude"]) ** 2
    ) ** 0.5
    client_service_summary = (
        jan24_df.groupby("ID Client")["Prestation"]
        .value_counts()
        .unstack(fill_value=0)
    )
    combined_client_data = clients_df.join(
        client_service_summary, on="ID Client"
    )
    combined_client_data["Distance from Paris Center"] = clients_df[
        "Distance from Paris Center"
    ]

    # Persona A: Central City Dweller Needing Regular Meals
    persona_a_clients = combined_client_data[
        (
            combined_client_data["Distance from Paris Center"]
            <= combined_client_data["Distance from Paris Center"].quantile(
                0.25
            )
        )
        & (combined_client_data["REPAS"] > 0)
    ].head()

    # Persona B: Suburban Senior with Mobility Assistance Needs
    persona_b_clients = combined_client_data[
        (
            combined_client_data["Distance from Paris Center"]
            > combined_client_data["Distance from Paris Center"].quantile(0.25)
        )
        & (
            combined_client_data["Distance from Paris Center"]
            <= combined_client_data["Distance from Paris Center"].quantile(
                0.75
            )
        )
        & (combined_client_data["TOILETTE"] > 0)
    ].head()

    # Persona C: Remote Client Needing Weekly Check-ins
    persona_c_clients = combined_client_data[
        (
            combined_client_data["Distance from Paris Center"]
            > combined_client_data["Distance from Paris Center"].quantile(0.75)
        )
        & (combined_client_data["REPAS"] <= 2)
    ].head()

    jan24_df["Start Hour"] = jan24_df["Heure de début"].apply(lambda x: x.hour)
    jan24_df["End Hour"] = jan24_df["Heure de fin"].apply(lambda x: x.hour)

    # Persona E:  Adults Needing Evening Assistance (services post 5 PM)
    persona_e_clients = (
        jan24_df[jan24_df["Start Hour"] >= 17]["ID Client"]
        .value_counts()
        .head()
        .index.tolist()
    )
    jan24_df["Day of Week"] = jan24_df["Date"].dt.dayofweek
    # Persona F: Weekend Assistance Client (services on weekends)
    persona_f_clients = (
        jan24_df[jan24_df["Day of Week"] >= 5]["ID Client"]
        .value_counts()
        .head()
        .index.tolist()
    )

    # Persona H: Clients Needing Frequent Short Visits (Services less than or equal to 1 hour)
    jan24_df["Service Duration"] = (
        jan24_df["End Hour"] - jan24_df["Start Hour"]
    )
    short_duration_clients = jan24_df[jan24_df["Service Duration"] <= 1]
    persona_h_clients = (
        short_duration_clients["ID Client"]
        .value_counts()
        .head()
        .index.tolist()
    )
    # Persona I: Early Morning Service Client (services before 8 AM)
    early_morning_clients = jan24_df[jan24_df["Start Hour"] < 8]
    persona_i_clients = (
        early_morning_clients["ID Client"].value_counts().head().index.tolist()
    )

    # Persona J: High Frequency Care Recipient (multiple services throughout the day)
    high_frequency_clients = jan24_df["ID Client"].value_counts()
    persona_j_clients = high_frequency_clients[
        high_frequency_clients > high_frequency_clients.quantile(0.75)
    ].index.tolist()[:5]
    # Persona K: Infrequent, but Long Duration Visits (longer duration, fewer appointments)
    long_duration_clients = jan24_df[
        jan24_df["Service Duration"]
        > jan24_df["Service Duration"].quantile(0.75)
    ]
    infrequent_long_duration_clients = long_duration_clients[
        "ID Client"
    ].value_counts()
    persona_k_clients = infrequent_long_duration_clients[
        infrequent_long_duration_clients
        < infrequent_long_duration_clients.quantile(0.25)
    ].index.tolist()[:5]

    # Persona L: Clients with Varied Service Needs (diverse types of services)
    varied_service_clients = client_service_summary[
        client_service_summary > 0
    ].count(axis=1)
    persona_l_clients = varied_service_clients[
        varied_service_clients > varied_service_clients.quantile(0.75)
    ].index.tolist()[:5]

    client_groups = {
        "a": persona_a_clients["ID Client"].to_list(),
        "b": persona_b_clients["ID Client"].to_list(),
        "c": persona_c_clients["ID Client"].to_list(),
        "e": persona_e_clients,
        "f": persona_f_clients,
        "h": persona_h_clients,
        "i": persona_i_clients,
        "j": persona_j_clients,
        "k": persona_k_clients,
        "l": persona_l_clients,
    }

    clients_df["client_persona"] = clients_df["ID Client"].apply(
        lambda x: find_key(client_groups, x)
    )
    return clients_df


def generate_random_sessions(
    persona_group: str,
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

    df_persona = df_client_with_persona[
        df_client_with_persona["client_persona"] == persona_group
    ].copy()

    df = pd.merge(df_sessions, df_persona, how="left", on="ID Client")

    # Generate event frequencies for the client persona
    event_frequencies = (
        df.groupby(["client_persona", "Date"])["Prestation"].value_counts()
        // 5
        + 1
    )

    # Generate key for new client
    new_client_id = np.random.randint(10000000, 100000000)

    # Take a random location for client
    client_loc = df_persona[["Latitude", "Longitude"]].sample(1).to_dict()
    client_loc = {k: list(v.values())[0] for k, v in client_loc.items()}

    # Join new client to client dataset
    new_client = pd.DataFrame(
        {"ID Client": new_client_id} | client_loc, index=[len(df_clients)]
    )
    new_df_clients = pd.concat([df_clients, new_client])

    # Get event freqs
    freqs = event_frequencies.loc[persona_group].apply(
        lambda x: max(1, x + np.random.randint(-1, 1))
    )

    # Generate a random event until all events are complete
    new_events = pd.DataFrame(columns=df_sessions.columns)

    ## Choose a random event start time
    for (date, prest), count in freqs.to_frame().iterrows():
        # display(i[1], count.iloc[0])
        count = count.iloc[0]

        times = df[df["Prestation"] == prest][
            ["Heure de début", "Heure de fin"]
        ].sample(count)

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
                "Prestation": [prest] * count,
            }
        )

        new_events = pd.concat([new_events, new_row])

    new_df_sessions = (
        pd.concat([df_sessions, new_events])
        .sort_values(by="Date")
        .reset_index(drop=True)
    )

    return new_df_clients, new_df_sessions


def find_key(dictionary, value):
    for key, values in dictionary.items():
        if value in values:
            return key
    return np.nan  # If the value is not found in any list
