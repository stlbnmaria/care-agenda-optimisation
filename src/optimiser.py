from itertools import product
from pathlib import Path

import pandas as pd
import pyomo.environ as pe
import pyomo.gdp as pyogdp


class CareScheduler:
    def __init__(self, date):
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

        self.model = self.create_model()

    def _generate_case_durations(self):
        return pd.Series(
            self.df_sessions["Duration"].values, index=self.df_sessions["idx"]
        ).to_dict()

    def _generate_start_time(self):
        return pd.Series(
            self.df_sessions["Start_time"].values,
            index=self.df_sessions["idx"],
        ).to_dict()

    def _generate_clients_commute(self):
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

    def _IDX_CLIENTS_match(self):
        return pd.Series(
            self.df_sessions["ID Client"].values, index=self.df_sessions["idx"]
        ).to_dict()

    def _generate_disjunctions(self):
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

            if case1 <= case2:
                disjunctions.append((case1, case2, caregiver))

        return disjunctions

    def _generate_tasks(self):
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

            tasks.append((case, caregiver))

        return tasks

    def _case_combinations(self):
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
            return model.DOWN_TIME_COUNTS[case1, case2, caregiver] == (
                model.SESSION_ASSIGNED[case1, case2, caregiver]
                * int(
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
            )

        model.DOWNTIME_CNTS = pe.Constraint(
            model.DISJUNCTIONS, rule=down_time_counts
        )

        def commute_care(model, case1, case2, caregiver):
            commute_expr = model.SESSION_ASSIGNED[case1, case2, caregiver] * (
                model.COMMUTE[
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

        model.DISJUNCTIONS_RULE = pyogdp.Disjunction(
            model.DISJUNCTIONS, rule=no_case_overlap
        )

        pe.TransformationFactory("gdp.bigm").apply_to(model)

        return model

    def solve(self):
        solvername = "cbc"
        solverpath_exe = "/opt/homebrew/bin/cbc"
        solver = pe.SolverFactory(solvername, executable=solverpath_exe)

        # Add solver parameters (time limit)
        options = {"seconds": 600}
        for key, value in options.items():
            solver.options[key] = value

        # Solve model (verbose)
        solver_results = solver.solve(self.model, tee=True)
        return solver_results


if __name__ == "__main__":
    for i in range(1, 32):
        if i < 10:
            i = f"0{i}"
        else:
            i = str(i)

        print(f"Starting optimisation for 2024-01-{i}")
        scheduler = CareScheduler(date=f"2024-01-{i}")
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