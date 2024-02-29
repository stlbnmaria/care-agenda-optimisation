from itertools import combinations
from typing import Tuple

import googlemaps
import pandas as pd

from config.config_data import EXCEL_FILE
from config.config_routing import COMMUTE_METHOD, GOOGLE_API, ROUTE_DIRECTION
from src.dataloader import load_data


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
    try:
        result = gmaps.distance_matrix(
            origins, destination, mode=COMMUTE_METHOD
        )
        result_dist = result["rows"][0]["elements"][0]["distance"]["value"]
        result_time = result["rows"][0]["elements"][0]["duration"]["value"]
    except KeyError:
        result_dist = 0
        result_time = 0

    return result_dist, result_time


if __name__ == "__main__":
    _, clients, caregivers = load_data(EXCEL_FILE)

    gmaps = googlemaps.Client(key=GOOGLE_API)

    if ROUTE_DIRECTION == "clients":
        comb_clients = list(combinations(clients["ID Client"], 2))

        # empty list - will be used to store calculated distances
        list_seconds = []
        list_distance = []

        # Loop through each row in the data frame using pairwise
        for client1, client2 in comb_clients:
            # Assign latitude and longitude as origin/departure points
            LatOrigin = clients.loc[
                clients["ID Client"] == client1, "Latitude"
            ]
            LongOrigin = clients.loc[
                clients["ID Client"] == client1, "Longitude"
            ]
            origins = (LatOrigin, LongOrigin)

            # Assign latitude and longitude from the next row as the destination point
            LatDest = clients.loc[
                clients["ID Client"] == client2, "Latitude"
            ]  # Save value as lat
            LongDest = clients.loc[
                clients["ID Client"] == client2, "Longitude"
            ]  # Save value as lat
            destination = (LatDest, LongDest)

            # pass origin and destination variables to distance_matrix
            result_dist, result_time = gmaps_api_request(origins, destination)

            # append result to list
            list_seconds.append(result_time)
            list_distance.append(result_dist)

        df = pd.DataFrame(
            {
                "clients": comb_clients,
                "commute_seconds": list_seconds,
                "commute_meters": list_distance,
            }
        )
        df["source"], df["destination"] = zip(*df.clients)

    elif ROUTE_DIRECTION == "care_clients":
        # empty list - will be used to store calculated distances
        combs_list = []
        list_seconds = []
        list_distance = []

        for care_id in caregivers["ID Intervenant"].unique():
            # Loop through each row in the data frame using pairwise
            for client_id in clients["ID Client"].unique():
                # Assign latitude and longitude as origin/departure points
                LatOrigin = caregivers.loc[
                    caregivers["ID Intervenant"] == care_id, "Latitude"
                ]
                LongOrigin = caregivers.loc[
                    caregivers["ID Intervenant"] == care_id, "Longitude"
                ]
                origins = (LatOrigin, LongOrigin)

                # Assign latitude and longitude from the next row as the destination point
                LatDest = clients.loc[
                    clients["ID Client"] == client_id, "Latitude"
                ]  # Save value as lat
                LongDest = clients.loc[
                    clients["ID Client"] == client_id, "Longitude"
                ]  # Save value as lat
                destination = (LatDest, LongDest)

                # pass origin and destination variables to distance_matrix
                result_dist, result_time = gmaps_api_request(
                    origins, destination
                )

                # append result to list
                list_seconds.append(result_time)
                list_distance.append(result_dist)
                combs_list.append((care_id, client_id))

        df = pd.DataFrame(
            {
                "care_client": combs_list,
                "commute_seconds": list_seconds,
                "commute_meters": list_distance,
            }
        )
        df["source"], df["destination"] = zip(*df.care_client)

    elif ROUTE_DIRECTION == "clients_care":
        # empty list - will be used to store calculated distances
        list_seconds = []
        list_distance = []
        combs_list = []

        for care_id in caregivers["ID Intervenant"].unique():
            # Loop through each row in the data frame using pairwise
            for client_id in clients["ID Client"].unique():
                # Assign latitude and longitude from the next row as the destination point
                LatOrigin = clients.loc[
                    clients["ID Client"] == client_id, "Latitude"
                ]  # Save value as lat
                LongOrigin = clients.loc[
                    clients["ID Client"] == client_id, "Longitude"
                ]  # Save value as lat
                origins = (LatOrigin, LongOrigin)

                # Assign latitude and longitude as origin/departure points
                LatDest = caregivers.loc[
                    caregivers["ID Intervenant"] == care_id, "Latitude"
                ]
                LongDest = caregivers.loc[
                    caregivers["ID Intervenant"] == care_id, "Longitude"
                ]
                destination = (LatDest, LongDest)

                # pass origin and destination variables to distance_matrix
                result_dist, result_time = gmaps_api_request(
                    origins, destination
                )

                # append result to list
                list_seconds.append(result_time)
                list_distance.append(result_dist)
                combs_list.append((client_id, care_id))

        df = pd.DataFrame(
            {
                "client_care": combs_list,
                "commute_seconds": list_seconds,
                "commute_meters": list_distance,
            }
        )
        df["source"], df["destination"] = zip(*df.client_care)

    # finalise and save
    df["commute_method"] = COMMUTE_METHOD
    df.to_csv(
        f"data/commute_{COMMUTE_METHOD}_{ROUTE_DIRECTION}.csv", index=False
    )
