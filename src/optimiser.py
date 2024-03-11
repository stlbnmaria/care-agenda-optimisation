import ast
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import pyomo.environ as pe
import pyomo.gdp as pyogdp

from utils import plot_agenda


class CareScheduler:
    def __init__(
        self,
        date: str,
        include_availability: bool = False,
        transport: str = "driving",
        filter_for_competence: bool = False,
    ):
        try:
            df_sessions = pd.read_csv("data/schedule.csv")
            df_sessions = df_sessions[df_sessions.Date == date]
            self.df_sessions = df_sessions
        except FileNotFoundError:
            print("Session data not found.")

        try:
            self.df_cargeivers = pd.read_excel(
                "data/ChallengeXHEC23022024.xlsx", sheet_name=2
            )
        except FileNotFoundError:
            print("Caregiver data not found")

        try:
            self.df_commute = pd.read_csv("data/commute_driving_all.csv")
        except FileNotFoundError:
            print("Commute data not found")

        try:
            self.df_commute_bicycling = pd.read_csv(
                "data/commute_bicycling_all.csv"
            )
        except FileNotFoundError:
            print("Bicycling commute data not found")

        try:
            self.df_caregiver_transport = pd.read_csv(
                f"data/caregiver_transport_{transport}.csv"
            )
        except FileNotFoundError:
            print("Caregiver transport data not found")

        if include_availability:
            try:
                # load days where caregiver is not available
                df_caregiver_avail = pd.read_csv(
                    "data/caregiver_avail.csv",
                    converters={
                        "ID Intervenant": ast.literal_eval,
                        "UNDISP_DAYS": ast.literal_eval,
                    },
                )

                # filter caregivers df based on availability
                day = (
                    pd.to_datetime(self.df_sessions["Heure de début"])
                    .iloc[0]
                    .day
                )
                caregivers = []
                for caregiver in self.df_cargeivers[
                    "ID Intervenant"
                ].to_list():
                    if (
                        day
                        not in df_caregiver_avail.loc[
                            df_caregiver_avail["ID Intervenant"] == caregiver,
                            "UNDISP_DAYS",
                        ].iloc[0]
                    ):
                        caregivers.append(caregiver)
                self.df_cargeivers = self.df_cargeivers[
                    self.df_cargeivers["ID Intervenant"].isin(caregivers)
                ]

                # filter sessions to exclude COMMUTE of unavailable caregivers
                clients = pd.read_excel(
                    "data/ChallengeXHEC23022024.xlsx", sheet_name=1
                )["ID Client"].to_list()
                self.df_sessions = self.df_sessions[
                    self.df_sessions["ID Client"].isin(caregivers + clients)
                ]
            except FileNotFoundError:
                print("Caregiver availability data not found")

        self.filter_for_competence = filter_for_competence
        if self.filter_for_competence:
            self.CAREGIVER_COMPETENCE = (
                self.df_cargeivers.set_index("ID Intervenant")["Compétences"]
                .apply(lambda x: x.split(","))
                .apply(lambda x: [i.strip() for i in x])
                .apply(lambda x: x + ["COMMUTE"])
                .to_dict()
            )

            self.SESSION_PRESTATION = (
                self.df_sessions.set_index("idx")["Prestation"]
                .replace(
                    {"ACCOMPAGNEMENTS COURSES PA": "ACCOMPAGNEMENTS COURSES"}
                )
                .to_dict()
            )

        self.model = self.create_model()

    def _generate_case_durations(self) -> dict:
        return pd.Series(
            self.df_sessions["Duration"].values, index=self.df_sessions["idx"]
        ).to_dict()

    def _generate_start_time(self) -> dict:
        return pd.Series(
            self.df_sessions["Start_time"].values,
            index=self.df_sessions["idx"],
        ).to_dict()

    def _generate_clients_commute(self) -> dict:
        clients_commute = {}
        cargivers = self.df_cargeivers["ID Intervenant"].to_list()
        for source, dest in product(
            self.df_sessions["ID Client"].unique(),
            self.df_sessions["ID Client"].unique(),
        ):
            if (
                (source in cargivers)
                and (dest in cargivers)
                and (source != dest)
            ):
                continue

            clients_commute[(source, dest)] = self.df_commute.loc[
                (self.df_commute.source == source)
                & (self.df_commute.destination == dest),
                "commute_minutes",
            ].iloc[0]
        return clients_commute

    def _generate_clients_commute_bicycling(self) -> dict:
        clients_commute_bicycling = {}
        cargivers = self.df_cargeivers["ID Intervenant"].to_list()
        for source, dest in product(
            self.df_sessions["ID Client"].unique(),
            self.df_sessions["ID Client"].unique(),
        ):
            if (
                (source in cargivers)
                and (dest in cargivers)
                and (source != dest)
            ):
                continue

            clients_commute_bicycling[
                (source, dest)
            ] = self.df_commute_bicycling.loc[
                (self.df_commute_bicycling.source == source)
                & (self.df_commute_bicycling.destination == dest),
                "commute_minutes",
            ].iloc[
                0
            ]
        return clients_commute_bicycling

    def _IDX_CLIENTS_match(self) -> dict:
        return pd.Series(
            self.df_sessions["ID Client"].values, index=self.df_sessions["idx"]
        ).to_dict()

    def _generate_disjunctions(self) -> list[tuple]:
        """Returns:
        disjunctions (list): list of tuples containing disjunctions
        """
        cases = self.df_sessions["idx"].to_list()
        cargivers = self.df_cargeivers["ID Intervenant"].to_list()
        disjunctions = []
        for (case1, case2, caregiver) in product(cases, cases, cargivers):
            if (
                self.df_sessions.loc[
                    self.df_sessions["idx"] == case1, "ID Client"
                ].iloc[0]
                in cargivers
            ) & (
                self.df_sessions.loc[
                    self.df_sessions["idx"] == case2, "ID Client"
                ].iloc[0]
                in cargivers
            ):

                if (
                    self.df_sessions.loc[
                        self.df_sessions["idx"] == case1, "ID Client"
                    ].iloc[0]
                    != caregiver
                ) | (
                    self.df_sessions.loc[
                        self.df_sessions["idx"] == case2, "ID Client"
                    ].iloc[0]
                    != caregiver
                ):
                    continue

            if (
                self.df_sessions.loc[
                    self.df_sessions["idx"] == case1, "ID Client"
                ].iloc[0]
                in cargivers
            ) & (
                not (
                    self.df_sessions.loc[
                        self.df_sessions["idx"] == case2, "ID Client"
                    ].iloc[0]
                    in cargivers
                )
            ):
                if (
                    self.df_sessions.loc[
                        self.df_sessions["idx"] == case1, "ID Client"
                    ].iloc[0]
                    != caregiver
                ):
                    continue

            if (
                not (
                    self.df_sessions.loc[
                        self.df_sessions["idx"] == case1, "ID Client"
                    ].iloc[0]
                    in cargivers
                )
            ) & (
                self.df_sessions.loc[
                    self.df_sessions["idx"] == case2, "ID Client"
                ].iloc[0]
                in cargivers
            ):
                if (
                    self.df_sessions.loc[
                        self.df_sessions["idx"] == case2, "ID Client"
                    ].iloc[0]
                    != caregiver
                ):
                    continue
            if self.filter_for_competence:
                if (
                    self.SESSION_PRESTATION[case1]
                    not in self.CAREGIVER_COMPETENCE[caregiver]
                    or self.SESSION_PRESTATION[case2]
                    not in self.CAREGIVER_COMPETENCE[caregiver]
                ):
                    continue

            if case1 <= case2:
                disjunctions.append((case1, case2, caregiver))

        return disjunctions

    def _generate_tasks(self) -> list[tuple]:
        cases = self.df_sessions["idx"].to_list()
        cargivers = self.df_cargeivers["ID Intervenant"].to_list()
        tasks = []
        for (case, caregiver) in product(cases, cargivers):
            if (
                self.df_sessions.loc[
                    self.df_sessions["idx"] == case, "ID Client"
                ].iloc[0]
                in cargivers
            ):
                if (
                    self.df_sessions.loc[
                        self.df_sessions["idx"] == case, "ID Client"
                    ].iloc[0]
                    != caregiver
                ):
                    continue
            # Filter out task combination if the caregiver doesn't have the competence
            if self.filter_for_competence:
                if (
                    self.SESSION_PRESTATION[case]
                    not in self.CAREGIVER_COMPETENCE[caregiver]
                ):
                    continue

            tasks.append((case, caregiver))

        return tasks

    def _case_combinations(self) -> list[tuple]:
        cases = self.df_sessions["idx"].unique()
        cargivers = self.df_cargeivers["ID Intervenant"].to_list()

        case_comb = []
        for (case1, case2) in product(cases, cases):
            if (
                self.df_sessions.loc[
                    self.df_sessions["idx"] == case1, "ID Client"
                ].iloc[0]
                in cargivers
            ) & (
                self.df_sessions.loc[
                    self.df_sessions["idx"] == case2, "ID Client"
                ].iloc[0]
                in cargivers
            ):

                if (
                    self.df_sessions.loc[
                        self.df_sessions["idx"] == case1, "ID Client"
                    ].iloc[0]
                    != self.df_sessions.loc[
                        self.df_sessions["idx"] == case2, "ID Client"
                    ].iloc[0]
                ):
                    continue

            if case1 <= case2:
                case_comb.append((case1, case2))

        return case_comb

    def create_model(self):
        model = pe.ConcreteModel()

        # List of case IDs in home care client needs list
        model.CASES = pe.Set(initialize=self.df_sessions["idx"].tolist())
        # List of potential caregiver IDs
        model.CAREGIVERS = pe.Set(
            initialize=self.df_cargeivers["ID Intervenant"].tolist()
        )
        # Session utilisation
        model.DISJUNCTIONS = pe.Set(
            initialize=self._generate_disjunctions(), dimen=3
        )
        # List of tasks - all possible (caseID, caregiverID) combination
        model.TASKS = pe.Set(initialize=self._generate_tasks(), dimen=2)
        model.CASE_COMBINATIONS = pe.Set(
            initialize=self._case_combinations(),
            dimen=2,
        )

        # The duration (expected case time) for each operation
        model.CASE_DURATION = pe.Param(
            model.CASES, initialize=self._generate_case_durations()
        )
        # Start time of a case
        model.CASE_START_TIME = pe.Param(
            model.CASES, initialize=self._generate_start_time()
        )

        model.CLIENT_CONNECTIONS = pe.Set(
            initialize=product(
                self.df_sessions["ID Client"].unique(),
                self.df_sessions["ID Client"].unique(),
            )
        )
        model.IDX_CLIENTS = pe.Param(
            model.CASES, initialize=self._IDX_CLIENTS_match()
        )
        model.COMMUTE = pe.Param(
            model.CLIENT_CONNECTIONS,
            initialize=self._generate_clients_commute(),
        )
        model.COMMUTE_BICYCLING = pe.Param(
            model.CLIENT_CONNECTIONS,
            initialize=self._generate_clients_commute_bicycling(),
        )

        # Decision Variables
        ub = 1440  # minutes in a day
        model.M = pe.Param(initialize=1e3 * ub)  # big M

        # Binary flag, 1 if case is assigned to session, 0 otherwise
        model.SESSION_ASSIGNED = pe.Var(model.DISJUNCTIONS, domain=pe.Binary)
        # commute for cargiver
        model.COMMUTE_CARE = pe.Var(
            model.DISJUNCTIONS, bounds=(0.0, 1440.0), within=pe.PositiveReals
        )
        model.DOWN_TIME_COUNTS = pe.Var(model.DISJUNCTIONS, within=pe.Binary)

        # Objective
        def objective_function(model):
            return pe.summation(model.COMMUTE_CARE) + 5 * pe.summation(
                model.DOWN_TIME_COUNTS
            )

        model.OBJECTIVE = pe.Objective(
            rule=objective_function, sense=pe.minimize
        )

        # each case can be maximum given once as source for all destinations and caregivers
        def session_assignment(model, case):
            return (
                sum(
                    [
                        model.SESSION_ASSIGNED[(case, case2, caregiver)]
                        for case1, case2, caregiver in model.DISJUNCTIONS
                        if case == case1
                    ]
                )
                <= 1
            )

        # each case can be maximum given once as destination for all sources and caregivers
        def session_assignment_2(model, case):
            return (
                sum(
                    [
                        model.SESSION_ASSIGNED[(case1, case, caregiver)]
                        for case1, case2, caregiver in model.DISJUNCTIONS
                        if (case == case2) & (case1 <= case2)
                    ]
                )
                <= 1
            )

        # each case needs to be given at least once as source or destination
        def session_assignment_3(model, case):
            return (
                sum(
                    [
                        model.SESSION_ASSIGNED[(case, case2, caregiver)]
                        for case1, case2, caregiver in model.DISJUNCTIONS
                        if case == case1
                    ]
                )
                + sum(
                    [
                        model.SESSION_ASSIGNED[(case1, case, caregiver)]
                        for case1, case2, caregiver in model.DISJUNCTIONS
                        if (case == case2) & (case1 <= case2)
                    ]
                )
                >= 1
            )

        # if a case is assigned to a caregiver as source, it can't be assigned to a different caregiver as destination
        def session_assignment_4(model, case, caregiver_):
            return (
                sum(
                    [
                        model.SESSION_ASSIGNED[(case1, case2, caregiver)]
                        for case1, case2, caregiver in model.DISJUNCTIONS
                        if (case == case1) & (caregiver_ == caregiver)
                    ]
                )
                + sum(
                    [
                        model.SESSION_ASSIGNED[(case1, case2, caregiver)]
                        for case1, case2, caregiver in model.DISJUNCTIONS
                        if (case == case2)
                        & (case1 <= case2)
                        & (caregiver_ != caregiver)
                    ]
                )
                <= 1
            )

        # if a case is assigned to a caregiver as destination, it also needs to be assigned as a source for this caregiver
        def session_assignment_6(model, case, caregiver_):
            return (
                (
                    sum(
                        [
                            model.SESSION_ASSIGNED[(case1, case2, caregiver)]
                            for case1, case2, caregiver in model.DISJUNCTIONS
                            if (case == case1) & (caregiver_ == caregiver)
                            | (model.IDX_CLIENTS[case1] == caregiver)
                            & (caregiver_ == caregiver)
                        ]
                    )
                    - sum(
                        [
                            model.SESSION_ASSIGNED[(case1, case2, caregiver)]
                            for case1, case2, caregiver in model.DISJUNCTIONS
                            if (
                                (case == case2) & (caregiver_ == caregiver)
                                | (model.IDX_CLIENTS[case2] == caregiver)
                                & (caregiver_ == caregiver)
                            )
                            & (case1 <= case2)
                        ]
                    )
                )
            ) == 0

        model.SESSION_ASSIGNMENT = pe.Constraint(
            model.CASES, rule=session_assignment
        )
        model.SESSION_ASSIGNMENT_2 = pe.Constraint(
            model.CASES, rule=session_assignment_2
        )
        model.SESSION_ASSIGNMENT_3 = pe.Constraint(
            model.CASES, rule=session_assignment_3
        )
        model.SESSION_ASSIGNMENT_4 = pe.Constraint(
            model.TASKS, rule=session_assignment_4
        )
        model.SESSION_ASSIGNMENT_6 = pe.Constraint(
            model.TASKS, rule=session_assignment_6
        )

        def down_time_counts(model, case1, case2, caregiver):
            if self.df_caregiver_transport.loc[
                self.df_caregiver_transport["ID Intervenant"] == caregiver,
                "Permis",
            ].iloc[0]:
                commute_expr = model.SESSION_ASSIGNED[
                    case1, case2, caregiver
                ] * int(
                    (
                        model.CASE_START_TIME[case2]
                        - (
                            model.CASE_START_TIME[case1]
                            + model.CASE_DURATION[case1]
                            + model.COMMUTE[
                                (
                                    model.IDX_CLIENTS[case1],
                                    model.IDX_CLIENTS[case2],
                                )
                            ]
                        )
                    )
                    < 30
                )
            else:
                commute_expr = model.SESSION_ASSIGNED[
                    case1, case2, caregiver
                ] * int(
                    (
                        model.CASE_START_TIME[case2]
                        - (
                            model.CASE_START_TIME[case1]
                            + model.CASE_DURATION[case1]
                            + model.COMMUTE_BICYCLING[
                                (
                                    model.IDX_CLIENTS[case1],
                                    model.IDX_CLIENTS[case2],
                                )
                            ]
                        )
                    )
                    < 30
                )

            return (
                model.DOWN_TIME_COUNTS[case1, case2, caregiver] == commute_expr
            )

        model.DOWNTIME_CNTS = pe.Constraint(
            model.DISJUNCTIONS, rule=down_time_counts
        )

        def commute_care(model, case1, case2, caregiver):
            if self.df_caregiver_transport.loc[
                self.df_caregiver_transport["ID Intervenant"] == caregiver,
                "Permis",
            ].iloc[0]:
                commute_expr = model.SESSION_ASSIGNED[
                    case1, case2, caregiver
                ] * (
                    model.COMMUTE[
                        (
                            model.IDX_CLIENTS[case1],
                            model.IDX_CLIENTS[case2],
                        )
                    ]
                )
            else:
                commute_expr = model.SESSION_ASSIGNED[
                    case1, case2, caregiver
                ] * (
                    model.COMMUTE_BICYCLING[
                        (
                            model.IDX_CLIENTS[case1],
                            model.IDX_CLIENTS[case2],
                        )
                    ]
                )
            return model.COMMUTE_CARE[case1, case2, caregiver] == commute_expr

        model.COMMUTE_CARE_CONST = pe.Constraint(
            model.DISJUNCTIONS, rule=commute_care
        )

        def no_case_overlap(model, case1, case2, caregiver):
            if self.df_caregiver_transport.loc[
                self.df_caregiver_transport["ID Intervenant"] == caregiver,
                "Permis",
            ].iloc[0]:
                return [
                    model.CASE_START_TIME[case1]
                    + model.CASE_DURATION[case1]
                    + model.COMMUTE[
                        (model.IDX_CLIENTS[case1], model.IDX_CLIENTS[case2])
                    ]
                    <= model.CASE_START_TIME[case2]
                    + (
                        (1 - model.SESSION_ASSIGNED[case1, case2, caregiver])
                        * model.M
                    ),
                    model.CASE_START_TIME[case2]
                    + model.CASE_DURATION[case2]
                    + model.COMMUTE[
                        (model.IDX_CLIENTS[case2], model.IDX_CLIENTS[case1])
                    ]
                    <= model.CASE_START_TIME[case1]
                    + (
                        (1 - model.SESSION_ASSIGNED[case1, case2, caregiver])
                        * model.M
                    ),
                ]
            
            return [
                model.CASE_START_TIME[case1]
                + model.CASE_DURATION[case1]
                + model.COMMUTE_BICYCLING[
                    (model.IDX_CLIENTS[case1], model.IDX_CLIENTS[case2])
                ]
                <= model.CASE_START_TIME[case2]
                + (
                    (1 - model.SESSION_ASSIGNED[case1, case2, caregiver])
                    * model.M
                ),
                model.CASE_START_TIME[case2]
                + model.CASE_DURATION[case2]
                + model.COMMUTE_BICYCLING[
                    (model.IDX_CLIENTS[case2], model.IDX_CLIENTS[case1])
                ]
                <= model.CASE_START_TIME[case1]
                + (
                    (1 - model.SESSION_ASSIGNED[case1, case2, caregiver])
                    * model.M
                ),
            ]

        model.DISJUNCTIONS_RULE = pyogdp.Disjunction(
            model.DISJUNCTIONS, rule=no_case_overlap
        )

        pe.TransformationFactory("gdp.bigm").apply_to(model)

        return model

    def solve(self):
        # solvername = "glpk"
        solvername = "cbc"

        solverpath_exe = "/opt/homebrew/bin/cbc"
        solver = pe.SolverFactory(solvername, executable=solverpath_exe)

        # Add solver parameters (time limit)
        options = {"seconds": 1200}
        for key, value in options.items():
            solver.options[key] = value

        # Solve model (verbose)
        solver_results = solver.solve(self.model, tee=True)
        return solver_results


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


def preprocess_schedules(
    temp: pd.DataFrame, caregivers: pd.DataFrame
) -> pd.DataFrame:
    jan24_df = temp.copy()
    jan24_df = jan24_df[jan24_df.Prestation != "COMMUTE"]

    caregivers["Commute Method"] = caregivers["Véhicule personnel"].map(
        {"Oui": "driving", "Non": "bicycling", np.nan: "bicycling"}
    )  # map commute method
    jan24_df = jan24_df.merge(
        caregivers[["ID Intervenant", "Commute Method"]],
        left_on="Caregiver_ID",
        right_on="ID Intervenant",
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


if __name__ == "__main__":
    commute_data_df = get_commute_data()
    caregivers = caregivers = pd.read_excel(
        "data/ChallengeXHEC23022024.xlsx", sheet_name=2
    )
    for i in range(1, 32):
        if i < 10:
            i = f"0{i}"
        else:
            i = str(i)

        print(f"Starting optimisation for 2024-01-{i}")
        scheduler = CareScheduler(
            date=f"2024-01-{i}",
            include_availability=True,
            filter_for_competence=True,
        )
        solver_results = scheduler.solve()
        model = scheduler.model

        # get all session assigned by key
        actions = [
            k
            for k, v in model.SESSION_ASSIGNED.extract_values().items()
            if v == 1
        ]

        actions_df = pd.DataFrame(
            actions, columns=["idx1", "idx2", "Caregiver_ID"]
        )
        actions_df_1 = actions_df[["idx1", "Caregiver_ID"]]
        actions_df_2 = actions_df[["idx2", "Caregiver_ID"]]
        actions_df_1.columns = ["idx", "Caregiver_ID"]
        actions_df_2.columns = ["idx", "Caregiver_ID"]
        actions_df = pd.concat([actions_df_1, actions_df_2], axis=0)
        actions_df = actions_df.drop_duplicates()

        temp = scheduler.df_sessions.copy()
        temp = temp.merge(actions_df, how="left", on="idx")

        results_dir = Path("results")
        results_dir.mkdir(parents=True, exist_ok=True)
        temp.to_csv(results_dir / f"optimised_Q1_2024-01-{i}.csv", index=False)

        # Plot agenda and Save it
        plots_dir = Path("plots")
        jan24_df = preprocess_schedules(temp, caregivers)
        for intervenant_id in jan24_df["ID Intervenant"].unique():

            intervenant_agenda_commute = plot_agenda(
                intervenant_id,
                jan24_df,
                commute_data_df,
                kind="license",
                save_plots=True,
                save_dir=plots_dir / f"2024-01-{i}",
            )
