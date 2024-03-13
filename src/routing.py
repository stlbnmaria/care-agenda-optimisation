from itertools import product
from typing import Tuple

import googlemaps
import pandas as pd

from config.config_data import EXCEL_FILE
from config.config_routing import COMMUTE_METHOD, GOOGLE_API, ROUTE_DIRECTION
from src.dataloader import load_data


def get_coordinate_tuple(
    df: pd.DataFrame, constraint: pd.Series
) -> Tuple[float]:
    """Extracts latitude and longitude from a DataFrame based on a given constraint.

    Parameters:
    - df (pd.DataFrame): DataFrame with latitude and longitude information.
    - constraint (pd.Series): Boolean Series as a constraint for row selection.

    Returns:
    Tuple[float]: Tuple containing latitude and longitude coordinates.
    """
    df = df.copy()

    Lat = df.loc[constraint, "Latitude"]
    Long = df.loc[constraint, "Longitude"]
    coord_tuple = (Lat, Long)

    return coord_tuple


def gmaps_api_request(
    origins: Tuple[float], destination: Tuple[float]
) -> Tuple[int]:
    """Fetches distance & duration from Google Maps API for given origins & destination.

    Parameters:
    - origins (Tuple[float]): Tuple with origin coordinates (lat, lon).
    - destination (Tuple[float]): Tuple with destination coordinates (lat, lon).

    Returns:
    Tuple[int]: Distance (meters) and duration (seconds) of the route.
                If an error occurs, both values are 0.
    """
    result = gmaps.distance_matrix(origins, destination, mode=COMMUTE_METHOD)
    try:
        result_dist = result["rows"][0]["elements"][0]["distance"]["value"]
    except KeyError:
        result_dist = 0
    try:
        result_time = result["rows"][0]["elements"][0]["duration"]["value"]
    except KeyError:
        result_time = 0

    return result_dist, result_time


if __name__ == "__main__":
    _, clients, caregivers = load_data(EXCEL_FILE)

    gmaps = googlemaps.Client(key=GOOGLE_API)

    # empty list - will be used to store calculated distances
    list_seconds = []
    list_distance = []

    if ROUTE_DIRECTION == "clients":
        combs_list = list(product(clients["ID Client"], clients["ID Client"]))

        # Loop through each row in the data frame using pairwise
        for client1, client2 in combs_list:
            if client1 == client2:
                result_dist, result_time = 0, 0
            else:
                # Assign latitude and longitude as origin/departure points
                origins = get_coordinate_tuple(
                    clients, clients["ID Client"] == client1
                )
                destination = get_coordinate_tuple(
                    clients, clients["ID Client"] == client2
                )

                # pass origin and destination variables to distance_matrix
                result_dist, result_time = gmaps_api_request(
                    origins, destination
                )

            # append result to list
            list_seconds.append(result_time)
            list_distance.append(result_dist)

    elif ROUTE_DIRECTION == "care_client":
        combs_list = []

        for care_id in caregivers["ID Intervenant"].unique():
            # Loop through each row in the data frame using pairwise
            for client_id in clients["ID Client"].unique():
                # Assign latitude and longitude as origin/departure points
                origins = get_coordinate_tuple(
                    caregivers, caregivers["ID Intervenant"] == care_id
                )
                destination = get_coordinate_tuple(
                    clients, clients["ID Client"] == client_id
                )

                # pass origin and destination variables to distance_matrix
                result_dist, result_time = gmaps_api_request(
                    origins, destination
                )

                # append result to list
                list_seconds.append(result_time)
                list_distance.append(result_dist)
                combs_list.append((care_id, client_id))

    elif ROUTE_DIRECTION == "client_care":
        combs_list = []

        for care_id in caregivers["ID Intervenant"].unique():
            # Loop through each row in the data frame using pairwise
            for client_id in clients["ID Client"].unique():
                # Assign latitude and longitude from the next row as the destination point
                origins = get_coordinate_tuple(
                    clients, clients["ID Client"] == client_id
                )
                destination = get_coordinate_tuple(
                    caregivers, caregivers["ID Intervenant"] == care_id
                )

                # pass origin and destination variables to distance_matrix
                result_dist, result_time = gmaps_api_request(
                    origins, destination
                )

                # append result to list
                list_seconds.append(result_time)
                list_distance.append(result_dist)
                combs_list.append((client_id, care_id))

    # create output df and save
    df = pd.DataFrame(
        {
            ROUTE_DIRECTION: combs_list,
            "commute_seconds": list_seconds,
            "commute_meters": list_distance,
        }
    )
    df["source"], df["destination"] = zip(*df[ROUTE_DIRECTION])
    df["commute_method"] = COMMUTE_METHOD
    df.to_csv(
        f"data/commute_{COMMUTE_METHOD}_{ROUTE_DIRECTION}.csv", index=False
    )
