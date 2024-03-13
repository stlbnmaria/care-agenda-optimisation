import numpy as np
import pandas as pd
import plotly.express as px


def compute_commute_and_wait_times(
    df: pd.DataFrame, commute_data_df: pd.DataFrame, kind: str = "license"
) -> pd.DataFrame:
    """Computes commute and wait times for each entry in the DataFrame.

    Parameters:
        df (pd.DataFrame): DataFrame containing schedule data.
        commute_data_df (pd.DataFrame): DataFrame containing commute time data.
        kind (str, optional): Type of commute method to consider. Defaults to "license".

    Returns:
        pd.DataFrame: Data with added columns for commute & wait time, and commute distance.
    """
    df["Wait Time"] = 0
    df["Commute Time"] = 0

    # iterate over clients
    for intervenant_id in df["ID Intervenant"].unique():
        intervenant_data = df[df["ID Intervenant"] == intervenant_id]

        # iterate over days
        for date in intervenant_data["Date"].unique():
            daily_data = intervenant_data[
                intervenant_data["Date"] == date
            ].sort_values(by="Start DateTime")
            prev_end_time = None
            prev_client_id = None

            for index, row in daily_data.iterrows():
                destination_id = str(row["ID Client"])

                # get the right commute method
                if kind == "license":
                    commute_method = (
                        row["Commute Method"]
                        if "Commute Method" in row
                        else "driving"
                    )
                else:
                    commute_method = "driving"

                if prev_client_id is None or prev_end_time is None:
                    source_id = str(intervenant_id)
                else:
                    source_id = str(prev_client_id)

                    # calculate wait time and add if smaller than 30 minutes
                    wait_time = (
                        row["Start DateTime"] - prev_end_time
                    ).total_seconds() // 60 - commute_data_df.loc[
                        (source_id, destination_id, commute_method),
                        "commute_seconds",
                    ] // 60
                    if wait_time < 30:
                        df.loc[index, "Wait Time"] = wait_time

                # calculate commute time
                try:
                    commute_time = (
                        commute_data_df.loc[
                            (source_id, destination_id, commute_method),
                            "commute_seconds",
                        ]
                        // 60
                    )
                    commute_meters = commute_data_df.loc[
                        (source_id, destination_id, commute_method),
                        "commute_meters",
                    ]

                except KeyError:
                    commute_time = 0  # Default to 0 if not found
                    commute_meters = 0  # Default to 0 if not found
                    print(
                        f"Data not found for commute time: {source_id},"
                        f"{destination_id}, {commute_method}"
                    )

                df.loc[index, "Commute Time"] = commute_time
                df.loc[index, "Commute Meters"] = commute_meters

                # Update previous end time and client ID for next iteration
                prev_end_time = row["End DateTime"]
                prev_client_id = row["ID Client"]

    return df


def plot_agenda(
    intervenant_id: int,
    jan24_df: pd.DataFrame,
    commute_data_df: pd.DataFrame,
    kind: str = "license",
    save_plots: bool = False,
    save_dir: str = None,
) -> pd.DataFrame:
    """Plot the agenda for a specific intervenant, including commute and wait times.

    Parameters:
        intervenant_id (int): ID of the intervenant.
        jan24_df (pd.DataFrame): DataFrame containing schedule data.
        commute_data_df (pd.DataFrame): DataFrame containing commute time data.
        kind (str, optional): Type of commute method to consider. Defaults to "license".
        save_plots (bool, optional): Whether to save the plots or not. Defaults to False.
        save_dir (str, optional): Directory to save the plots. Defaults to None.

    Returns:
        pd.DataFrame: Combined DataFrame with agenda details including commute and wait times.
    """
    # filter for caregiver and sort by start date
    intervenant_agenda = jan24_df[jan24_df["ID Intervenant"] == intervenant_id]
    intervenant_agenda_sorted = intervenant_agenda.sort_values(
        by=["Date", "Heure de début"]
    )

    # generate some columns for the plot with the right naming and type
    df_timeline = intervenant_agenda_sorted.copy()
    df_timeline["Start"] = pd.to_datetime(df_timeline["Start DateTime"])
    df_timeline["Finish"] = pd.to_datetime(df_timeline["End DateTime"])
    df_timeline["Task"] = df_timeline["Prestation"]
    df_timeline["Resource"] = df_timeline["ID Intervenant"].astype(str)
    df_timeline["ID Client"] = df_timeline["ID Client"].astype(str)

    # compute wait and commute times
    df_timeline = compute_commute_and_wait_times(
        df_timeline, commute_data_df, kind
    )

    # create wait and commute entries
    commute_entries = df_timeline.copy()
    commute_entries["Start"] = commute_entries["Start"] - pd.to_timedelta(
        commute_entries["Commute Time"], unit="m"
    )
    commute_entries["Finish"] = commute_entries["Start"] + pd.to_timedelta(
        commute_entries["Commute Time"], unit="m"
    )
    commute_entries["Task"] = "Commute Time"
    commute_entries["Type"] = "Commute"

    # generate rows for wait time
    wait_entries = []
    prev_finish = None
    for _, row in df_timeline.iterrows():
        if prev_finish is not None and row["Wait Time"] > 0:
            wait_entry = row.copy()
            wait_entry["Start"] = prev_finish
            wait_entry["Finish"] = row["Start"]
            wait_entry["Task"] = "Wait Time"
            wait_entry["Type"] = "Wait"
            wait_entries.append(wait_entry)
        prev_finish = row["Finish"]
    wait_entries_df = pd.DataFrame(wait_entries)

    df_timeline["Type"] = "Task"

    # add end of day commute from the last session home
    end_of_day_commutes = []
    for date in df_timeline["Date"].unique():
        daily_data = df_timeline[df_timeline["Date"] == date]
        if not daily_data.empty:
            last_client_id = daily_data.iloc[-1]["ID Client"]
            source_id = str(last_client_id)
            destination_id = str(intervenant_id)
            commute_method = daily_data.iloc[-1]["Commute Method"]

            try:
                commute_time = (
                    commute_data_df.loc[
                        (source_id, destination_id, commute_method),
                        "commute_seconds",
                    ]
                    / 60
                )
                commute_meters = commute_data_df.loc[
                    (source_id, destination_id, commute_method),
                    "commute_meters",
                ]
            except KeyError:
                print("Commute time not found")

            end_of_day_commute = {
                "Start": daily_data.iloc[-1]["End DateTime"],
                "Finish": daily_data.iloc[-1]["End DateTime"]
                + pd.Timedelta(minutes=commute_time),
                "Task": "Commute Time",
                "Type": "Commute",
                "ID Client": "Home",
                "Date": date,
                "ID Intervenant": intervenant_id,
                "Commute Time": commute_time,
                "Commute Meters": commute_meters,
                "Commute Method": commute_method,
                "Wait Time": 0,
            }
            end_of_day_commutes.append(end_of_day_commute)

    end_of_day_commutes_df = pd.DataFrame(end_of_day_commutes)

    combined_df = pd.concat(
        [df_timeline, commute_entries, wait_entries_df, end_of_day_commutes_df]
    )
    combined_df.sort_values(by="Start", inplace=True)

    # create schedule plot
    fig = px.timeline(
        combined_df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Type",
        color_discrete_map={
            "Task": "blue",
            "Commute": "orange",
            "Wait": "green",
        },
        hover_data=["ID Client", "Wait Time", "Commute Time"],
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(title=f"Agenda for Intervenant ID: {intervenant_id}")
    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=list(
                    [
                        dict(
                            count=1,
                            label="1D",
                            step="day",
                            stepmode="backward",
                        ),
                        dict(
                            count=7,
                            label="1W",
                            step="day",
                            stepmode="backward",
                        ),
                        dict(step="all"),
                    ]
                )
            ),
            rangeslider=dict(visible=True),
            type="date",
        )
    )
    # save plots if specified
    if save_plots:
        save_dir.mkdir(parents=True, exist_ok=True)
        fig.write_html(f"{save_dir}/timeline_{intervenant_id}.html")
        return None

    fig.show()
    return combined_df


def preprocess_schedules(
    temp: pd.DataFrame,
    caregivers: pd.DataFrame,
    sched: str = "optimised",
    kind: str = "license",
) -> pd.DataFrame:
    """Preprocesses schedule data for plotting.

    Parameters:
        temp (pd.DataFrame): DataFrame containing schedule data.
        caregivers (pd.DataFrame): DataFrame containing caregiver information.
        sched (str, optional): Type of schedule to process. Defaults to "optimised".
        kind (str, optional): Type of commute method to consider. Defaults to "license".

    Returns:
        pd.DataFrame: Preprocessed schedule DataFrame.
    """
    jan24_df = temp.copy()
    jan24_df = jan24_df[jan24_df.Prestation != "COMMUTE"]

    # add the correct commute possibility for cargivers
    if kind == "license":
        caregivers["Commute Method"] = caregivers["Véhicule personnel"].map(
            {"Oui": "driving", "Non": "bicycling", np.nan: "bicycling"}
        )  # map commute method
    else:
        caregivers["Commute Method"] = "driving"

    # merge and create the start and end time
    if sched == "optimised":
        jan24_df = jan24_df.merge(
            caregivers[["ID Intervenant", "Commute Method"]],
            left_on="Caregiver_ID",
            right_on="ID Intervenant",
            how="left",
        )  # merge with agenda data

        jan24_df["Start DateTime"] = pd.to_datetime(jan24_df["Heure de début"])
        jan24_df["End DateTime"] = pd.to_datetime(jan24_df["Heure de fin"])
    else:
        jan24_df = jan24_df.merge(
            caregivers[["ID Intervenant", "Commute Method"]],
            on="ID Intervenant",
            how="left",
        )  # merge with agenda data

        jan24_df["Start DateTime"] = pd.to_datetime(
            jan24_df["Date"].astype(str)
            + " "
            + jan24_df["Heure de début"].astype(str)
        )
        jan24_df["End DateTime"] = pd.to_datetime(
            jan24_df["Date"].astype(str)
            + " "
            + jan24_df["Heure de fin"].astype(str)
        )
    return jan24_df
