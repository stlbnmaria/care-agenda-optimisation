import streamlit as st
from pathlib import Path
import pandas as pd
import plotly.express as px
from utils_app import *

st.set_page_config(page_title="Schedule optimiser", page_icon="🧑🏻‍💼")

st.write("\n")
st.write("\n")

def display_kpis(kpi_names, kpi_values):
    """
    Display KPIs using st.metric().

    Parameters:
        kpi_names (list): List of KPI names.
        kpi_values (list): List of corresponding KPI values.

    Returns:
        None
    """
    col1, col2, col3 = st.columns(3)

    # Display KPIs
    for name, value, col in zip(kpi_names, kpi_values, [col1, col2, col3]):
        col.metric(label=name, value=value)

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

def metrics_calculation (
    df: pd.DataFrame,
    kind: str = "driving"
) -> pd.DataFrame:
    if not df.empty:
        all_intervenant_agendas = []
        for intervenant_id in df["ID Intervenant"].unique():
            intervenant_agenda_commute = plot_agenda(
                intervenant_id, df, commute_data_df, kind=kind, moto = 'aggregate'
            )
            all_intervenant_agendas.append(intervenant_agenda_commute)

        temp = pd.concat(all_intervenant_agendas)

        avg_commute= (
            temp[(temp["Task"] == "Commute Time")]
            .groupby(["Date", "ID Intervenant"])["Commute Time"]
            .sum()
            .groupby("Date")
            .mean()
            .mean()
        )

        avg_downtime= (
            temp[(temp["Task"] == "Wait Time")]
            .groupby(["Date", "ID Intervenant"])["Wait Time"]
            .count()
            .groupby("Date")
            .mean()
            .mean()
        )

        commute_given = temp.loc[
            (temp["Task"] == "Commute Time")
            & (temp["Commute Method"] == "driving"),
            "Commute Meters",
        ].sum()

        return round(avg_commute,2), round(avg_downtime,2), round(commute_given/1000,2)
    
    else:
         return 0,0,0

q1a = pd.read_csv('../results/question_1_a.csv')
q1b = pd.read_csv('../results/question_1_b.csv')
q2a = pd.read_csv('../results/question_2_a.csv')
q2b = pd.read_csv('../results/question_2_b.csv')

commute_file_paths = [
    "../data/commute_bicycling_clients.csv",
    "../data/commute_driving_clients.csv",
    "../data/commute_bicycling_care_clients.csv",
    "../data/commute_bicycling_clients_care.csv",
    "../data/commute_driving_care_clients.csv",
    "../data/commute_driving_clients_care.csv",
]

commute_data_df = get_commute_data(commute_file_paths)
caregivers = pd.read_excel("../data/ChallengeXHEC23022024.xlsx", sheet_name=2)

optimised_sched_q1a = preprocess_schedules(
    q1a, caregivers, sched="optimised", kind="driving"
)

optimised_sched_q1b = preprocess_schedules(
    q1b, caregivers, sched="optimised", kind="driving"
)

optimised_sched_q2a = preprocess_schedules(
    q2a, caregivers, sched="optimised", kind="license"
)

optimised_sched_q2b = preprocess_schedules(
    q2b, caregivers, sched="optimised", kind="license"
)

schedule = pd.read_excel("../data/ChallengeXHEC23022024.xlsx", sheet_name=0)

discard_list = [
    "ADMINISTRATION",
    "VISITE MEDICALE",
    "FORMATION",
    "COORDINATION",
    "HOMMES TOUTES MAINS",
]

schedule = schedule[~schedule.Prestation.isin(discard_list)]
given_sched = preprocess_schedules(
    schedule, caregivers, sched="given", kind="driving"
)

# Sidebar filters
st.sidebar.header("Filters")

# Start and end date filter
given_sched["Date"] = pd.to_datetime(given_sched["Date"])
min_date = given_sched["Date"].min()
max_date = given_sched["Date"].max()
start_date = pd.Timestamp(
    st.sidebar.date_input(
        "Start date",
        min_date.date(),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )
)
end_date = pd.Timestamp(
    st.sidebar.date_input(
        "End date",
        max_date.date(),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )
)

#constraint filters
constraint_options = ['basic (commute time + downtime)', 'basic + emissions',
                      'basic + additional', 'basic + additional + emissions']
selected_constraint = st.sidebar.selectbox("Optimised constraints", constraint_options)

# Intervenant filter
caregiver_options = list(optimised_sched_q1a["ID Intervenant"].unique())
selected_caregiver = st.sidebar.selectbox("Caregiver", caregiver_options)

# Apply date filters
given_sched  = given_sched[(given_sched["Date"] >= start_date) & (given_sched["Date"] <= end_date)]
optimised_sched_q1a  = optimised_sched_q1a[(optimised_sched_q1a["Date"] >= start_date) & (optimised_sched_q1a["Date"] <= end_date)]
optimised_sched_q1b = optimised_sched_q1b[(optimised_sched_q1b["Date"] >= start_date) & (optimised_sched_q1b["Date"] <= end_date)]
optimised_sched_q2a = optimised_sched_q2a[(optimised_sched_q2a["Date"] >= start_date) & (optimised_sched_q2a["Date"] <= end_date)]
optimised_sched_q2b = optimised_sched_q2b[(optimised_sched_q2b["Date"] >= start_date) & (optimised_sched_q2b["Date"] <= end_date)]

# Compute key metrics
avg_commute_given , avg_wait_given, distance_given = metrics_calculation(given_sched)
avg_commute_q1a , avg_wait_q1a, distance_q1a = metrics_calculation(optimised_sched_q1a)
avg_commute_q1b , avg_wait_q1b, distance_q1b = metrics_calculation(optimised_sched_q1b)
avg_commute_q2a , avg_wait_q2a, distance_q2a = metrics_calculation(optimised_sched_q2a, kind="license")
avg_commute_q2b , avg_wait_q2b, distance_q2b = metrics_calculation(optimised_sched_q2b, kind="license")


kpi_names = [
    ":stopwatch: Avg. Commute Time (min)",
    ":arrow_down: Avg nr short downtimes",
    ":straight_ruler: Commute distance (km)"
]
kpi_values_given = [
    avg_commute_given,
    avg_wait_given,
    distance_given
]

# NOTE: change kind here depending on execution above
if selected_constraint == 'basic (commute time + downtime)' : 

    st.subheader('Given Schedule')
    display_kpis(kpi_names, kpi_values_given)
    intervenant_agenda_existing = plot_agenda(
        selected_caregiver, given_sched, commute_data_df, kind="driving"
    )

    st.subheader('Optimised Schedule')
    kpi_values_q1a = [
        avg_commute_q1a,
        avg_wait_q1a,
        distance_q1a
    ]
    display_kpis(kpi_names, kpi_values_q1a)
    intervenant_agenda_commute = plot_agenda(
        selected_caregiver, optimised_sched_q1a, commute_data_df, kind="driving"
    )
elif selected_constraint == 'basic + emissions' : 

    st.subheader('Given Schedule')
    display_kpis(kpi_names, kpi_values_given)
    intervenant_agenda_existing = plot_agenda(
        selected_caregiver, given_sched, commute_data_df, kind="driving"
    )

    st.subheader('Optimised Schedule')
    kpi_values_q1b = [
        avg_commute_q1b,
        avg_wait_q1b,
        distance_q1b
    ]
    display_kpis(kpi_names, kpi_values_q1b)
    intervenant_agenda_commute = plot_agenda(
        selected_caregiver, optimised_sched_q1b, commute_data_df, kind="driving"
    )
elif selected_constraint == 'basic + additional' : 

    st.subheader('Given Schedule')
    display_kpis(kpi_names, kpi_values_given)
    intervenant_agenda_existing = plot_agenda(
        selected_caregiver, given_sched, commute_data_df, kind="driving"
    )

    st.subheader('Optimised Schedule')
    if not optimised_sched_q2a.empty:  # Check if DataFrame is not empty
            kpi_values_q2a = [
            avg_commute_q2a,
            avg_wait_q2a,
            distance_q2a
        ]
            display_kpis(kpi_names, kpi_values_q2a)
            intervenant_agenda_commute = plot_agenda(
                selected_caregiver, optimised_sched_q2a, commute_data_df, kind="license"
            )
    else:
        st.write("No optimized agenda found for the selected date.")
elif selected_constraint == 'basic + additional + emissions' : 

    st.subheader('Given Schedule')
    display_kpis(kpi_names, kpi_values_given)
    intervenant_agenda_existing = plot_agenda(
        selected_caregiver, given_sched, commute_data_df, kind="driving"
    )

    st.subheader('Optimised Schedule')
    if not optimised_sched_q2b.empty:  # Check if DataFrame is not empty
            kpi_values_q2b = [
                avg_commute_q2b,
                avg_wait_q2b,
                distance_q2b
            ]
            display_kpis(kpi_names, kpi_values_q2b)
            intervenant_agenda_commute = plot_agenda(
                selected_caregiver, optimised_sched_q2b, commute_data_df, kind="license"
            )
    else:
        st.write("No optimized agenda found for the selected date.")

