"""The module to display data analysis in the app."""
import os
import io
import numpy as np
import pandas as pd
import seaborn as sns
import plotly.io as pio
import plotly.figure_factory as ff
import folium
from streamlit_folium import folium_static
import streamlit as st
from zipfile import ZipFile
import matplotlib.pyplot as plt
from streamlit_extras.switch_page_button import switch_page
import plotly.express as px
import plotly.graph_objects as go
import holidays
from plotly.subplots import make_subplots

st.set_page_config(page_title="Data Analysis", page_icon="📊")


@st.cache_data()
def read_excel_file(excel_file: str) -> tuple:
    """Read an Excel file and return DataFrames for each sheet.

    Parameters:
    - excel_file (str): The path to the Excel file.

    Returns:
    - tuple: A tuple containing DataFrames for each sheet of the Excel file.
    """
    dataframes = []
    xls = pd.ExcelFile(excel_file)
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name)
        dataframes.append(df)
    return tuple(dataframes)



@st.cache_data()
def preloaded():
    file_path = "/Users/madhuranirale/Desktop/HEC-T1/health/ChallengeXHEC23022024.xlsx"
    excel_data = pd.ExcelFile(file_path)


    jan24_df = pd.read_excel(excel_data, sheet_name="JAN24")
    clients_df = pd.read_excel(excel_data, sheet_name="clients")
    intervenants_df = pd.read_excel(excel_data, sheet_name="intervenants")

    return jan24_df, clients_df, intervenants_df

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


st.title("Analytics Dashboard")

excel_file = st.file_uploader(
    "Upload your excel file", type="xlsx", accept_multiple_files=False
)

jan24_df, clients_df, intervenants_df = preloaded()

if st.button("Use pre-loaded file"):
    pass
else:
    if excel_file:
        # Display success message
        st.success("File uploaded successfully!")

        jan24_df, clients_df, intervenants_df = read_excel_file(excel_file)


if (
    (jan24_df is not None)
    and (clients_df is not None)
    and (intervenants_df is not None)
):

    # Sidebar filters
    st.sidebar.header("Filters")

    # Start and end date filter
    jan24_df["Date"] = pd.to_datetime(jan24_df["Date"])
    min_date = jan24_df["Date"].min()
    max_date = jan24_df["Date"].max()
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

    # Clients filter
    client_options = ["All"] + list(jan24_df["ID Client"].unique())
    selected_clients = st.sidebar.multiselect(
        "Clients", client_options, default= "All"
    )
    if "All" in selected_clients:
        selected_clients = list(jan24_df["ID Client"].unique())

    # Intervenant filter
    caregiver_options = ["All"] + list(jan24_df["ID Intervenant"].unique())
    selected_caregivers = st.sidebar.multiselect("Caregiver", caregiver_options, default="All")
    if "All" in selected_caregivers:
        selected_caregivers = list(jan24_df["ID Intervenant"].unique())

    # Services filter
    service_options = ["All"] + list(jan24_df["Prestation"].unique())
    selected_services = st.sidebar.multiselect("Service", service_options, default="All")
    if "All" in selected_services:
        selected_services = list(jan24_df["Prestation"].unique())

    # Apply filters
    filtered_df = jan24_df[
        (
            (jan24_df["ID Client"].isin(selected_clients))
        )
        & (
            (jan24_df["ID Intervenant"].isin(selected_caregivers))
        )
        & (
            (jan24_df["Prestation"].isin(selected_services))
        )
        & (
            (jan24_df["Date"] >= start_date)
            & (jan24_df["Date"] <= end_date)
        )
    ]

    st.subheader("Key Metrics")

    # Compute key metrics
    total_clients = len(clients_df)
    total_caregivers = len(intervenants_df)
    vehicule_personnel_percentage = (intervenants_df['Véhicule personnel'].value_counts(normalize=True) * 100).get('Oui', 0)
    vehicule_personnel_percentage_formatted = f"{vehicule_personnel_percentage:.2f}%"
    permis_percentage = (intervenants_df['Permis'].value_counts(normalize=True) * 100).get('Oui', 0)
    permis_percentage_formatted = f"{permis_percentage:.2f}%"
    competences_list = [comp.split(', ') for comp in intervenants_df['Compétences']]
    flatten_competences = [item for sublist in competences_list for item in sublist]
    most_common_competence = str.lower(pd.Series(flatten_competences).value_counts().idxmax())

    # Example KPIs with emojis
    kpi_names = [
        ":office_worker: #Clients",
        ":busts_in_silhouette: #Caregivers",
        ":red_car: License holders"
        #":mechanic: Top service",
    ]
    kpi_values = [
        total_clients,
        total_caregivers,
        permis_percentage_formatted
        #most_common_competence
    ]

    display_kpis(kpi_names, kpi_values)

    st.write("\n")
    st.write("\n")

    st.subheader('Client and Caregiver locations')

    # Create a Folium map
    map = folium.Map(
        location=[clients_df.Latitude.mean(), clients_df.Longitude.mean()],
        zoom_start=10,
        control_scale=True,
    )

    # Add client markers
    for index, location_info in clients_df.iterrows():
        folium.CircleMarker(
            [location_info["Latitude"], location_info["Longitude"]],
            color="blue",
            fill_color="blue",
        ).add_to(map)

    # Add intervenant markers
    for index, location_info in intervenants_df.iterrows():
        folium.CircleMarker(
            [location_info["Latitude"], location_info["Longitude"]],
            color="red",
            fill_color="red",
        ).add_to(map)

    # Create legend
    legend_html = """
    <div style="position:fixed; bottom:20px; left:20px; z-index:9999; font-size:14px; background-color:white; border-radius:5px; padding:10px;">
        <p><i class="fa fa-circle fa-1x" style="color:blue"></i>&nbsp;&nbsp;Client</p>
        <p><i class="fa fa-circle fa-1x" style="color:red"></i>&nbsp;&nbsp;Intervenant</p>
    </div>
    """

    # Add legend to the map
    map.get_root().html.add_child(folium.Element(legend_html))

    # Display the Folium map using folium_static
    folium_static(map)

    st.subheader("Service distribution")

    # Group by 'Prestation' and count unique 'ID Client' for each service
    clients_per_service = filtered_df.groupby('Prestation')['ID Client'].nunique()

    # Plotting the pie chart
    plt.figure(figsize=(10, 10))
    ax = plt.subplot()
    wedges, _ = ax.pie(clients_per_service, labels=clients_per_service.index, startangle=140, wedgeprops=dict(width=0.4))

    # Draw a white circle at the center to create the donut shape
    center_circle = plt.Circle((0, 0), 0.6, color='white', fc='white', linewidth=1.25)
    ax.add_artist(center_circle)

    # Display legend with percentages in brackets, reduce the size
    legend_labels = [f'{label} ({percent:.1f}%)' for label, percent in zip(clients_per_service.index, clients_per_service / clients_per_service.sum() * 100)]
    ax.legend(wedges, legend_labels, title="Services", loc="lower left", bbox_to_anchor=(1, 0.7))
    
    st.pyplot(plt)

    st.write("\n")
    st.write("\n")

    st.subheader('Total Number of Services Provided Per Day')

    services_per_day = filtered_df.groupby('Date').size()

    # Plotting the data
    plt.figure(figsize=(12, 6))
    services_per_day.plot(marker='o', color='blue')
    plt.xlabel('Date')
    plt.ylabel('Number of Services')
    plt.xticks(rotation=45)
    plt.grid(False)

    st.pyplot(plt)

    st.subheader('Service Frequency by Day of the Week')

    filtered_df['Day of Week'] = filtered_df['Date'].dt.day_name()
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    filtered_df['Day of Week'] = pd.Categorical(filtered_df['Day of Week'], categories=days_order, ordered=True)
    service_by_day = filtered_df.groupby(['Prestation', 'Day of Week']).size().unstack(fill_value=0)

    fig = px.bar(service_by_day, barmode='group', labels={'value': 'Frequency', 'variable': 'Day of Week'})
    fig.update_layout(width=850, height=600)
    fig.update_layout(legend=dict(title='Day of Week', orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))

    st.plotly_chart(fig)

    # Button to navigate to the inner page
    get_clients_button = st.button("Optimise schedule")

    if get_clients_button:
        switch_page("Schedule_Optimiser")
