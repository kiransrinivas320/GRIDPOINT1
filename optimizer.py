import math
import itertools


# =================================================
# 1. DISTANCE CALCULATION
# =================================================

def calculate_distance(lat1, lon1, lat2, lon2):

    R = 6371

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)

    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return R * c


# =================================================
# 2. FIND FEASIBLE ASSIGNMENT
# =================================================

def find_assignment(
    data,
    warehouse_indices,
    max_radius=None,
    warehouse_capacity=None
):

    # Store all possible warehouse choices
    # for every neighborhood

    possibilities = {}

    for index, row in data.iterrows():

        choices = []

        for warehouse_index in warehouse_indices:

            warehouse = data.iloc[warehouse_index]

            distance = calculate_distance(

                row["Latitude"],
                row["Longitude"],

                warehouse["Latitude"],
                warehouse["Longitude"]

            )

            # Radius restriction

            if (
                max_radius is not None
                and distance > max_radius
            ):
                continue

            choices.append({

                "warehouse_index":
                    warehouse_index,

                "distance":
                    distance

            })

        # No warehouse can reach this neighborhood

        if len(choices) == 0:

            return None

        # Try closest warehouse first

        choices.sort(
            key=lambda x: x["distance"]
        )

        possibilities[index] = choices


    # Process neighborhoods with fewer choices first

    neighborhood_order = sorted(

        possibilities.keys(),

        key=lambda x: len(
            possibilities[x]
        )

    )


    warehouse_orders = {

        warehouse_index: 0

        for warehouse_index
        in warehouse_indices

    }


    selected_assignments = {}


    # -------------------------------------------------
    # BACKTRACKING
    # -------------------------------------------------

    def backtrack(position):

        if position == len(
            neighborhood_order
        ):

            return True


        neighborhood_index = (
            neighborhood_order[position]
        )

        row = data.iloc[
            neighborhood_index
        ]


        for choice in possibilities[
            neighborhood_index
        ]:

            warehouse_index = (
                choice["warehouse_index"]
            )

            distance = (
                choice["distance"]
            )


            # Check capacity

            if warehouse_capacity is not None:

                if (

                    warehouse_orders[
                        warehouse_index
                    ]

                    + row["Orders"]

                    > warehouse_capacity

                ):

                    continue


            # Assign

            warehouse_orders[
                warehouse_index
            ] += row["Orders"]


            selected_assignments[
                neighborhood_index
            ] = {

                "warehouse_index":
                    warehouse_index,

                "distance":
                    distance

            }


            # Continue

            if backtrack(position + 1):

                return True


            # Undo assignment

            warehouse_orders[
                warehouse_index
            ] -= row["Orders"]


            del selected_assignments[
                neighborhood_index
            ]


        return False


    success = backtrack(0)


    if not success:

        return None


    return selected_assignments


# =================================================
# 3. CALCULATE COST
# =================================================

def calculate_total_cost(

    data,

    warehouse_indices,

    cost_per_km,

    max_radius=None,

    warehouse_capacity=None

):

    assignment_result = find_assignment(

        data,

        warehouse_indices,

        max_radius,

        warehouse_capacity

    )


    if assignment_result is None:

        return None


    total_physical_distance = 0

    total_weighted_distance = 0

    total_cost = 0

    assignments = []


    for index, row in data.iterrows():

        assignment = (
            assignment_result[index]
        )


        warehouse_index = (
            assignment["warehouse_index"]
        )


        best_distance = (
            assignment["distance"]
        )


        weighted_distance = (

            best_distance
            * row["Orders"]

        )


        delivery_cost = (

            weighted_distance
            * cost_per_km

        )


        total_physical_distance += (
            best_distance
        )


        total_weighted_distance += (
            weighted_distance
        )


        total_cost += (
            delivery_cost
        )


        assignments.append({

            "Neighborhood":
                row["Neighborhood"],

            "Warehouse":
                data.iloc[
                    warehouse_index
                ]["Neighborhood"],

            "Distance_km":
                best_distance,

            "Orders":
                row["Orders"],

            "Weighted_Distance":
                weighted_distance,

            "Delivery_Cost":
                delivery_cost

        })


    return (

        total_physical_distance,

        total_weighted_distance,

        total_cost,

        assignments

    )


# =================================================
# 4. OPTIMIZATION ENGINE
# =================================================

def find_best_warehouses(

    data,

    number_of_warehouses,

    cost_per_km,

    max_radius=None,

    warehouse_capacity=None

):

    number_of_neighborhoods = len(data)


    if number_of_warehouses > (
        number_of_neighborhoods
    ):

        number_of_warehouses = (
            number_of_neighborhoods
        )


    best_cost = float("inf")

    best_physical_distance = None

    best_weighted_distance = None

    best_warehouses = None

    best_assignments = None


    combinations = itertools.combinations(

        range(number_of_neighborhoods),

        number_of_warehouses

    )


    for warehouse_indices in combinations:

        result = calculate_total_cost(

            data,

            warehouse_indices,

            cost_per_km,

            max_radius,

            warehouse_capacity

        )


        if result is None:

            continue


        (

            physical_distance,

            weighted_distance,

            total_cost,

            assignments

        ) = result


        if total_cost < best_cost:

            best_cost = total_cost

            best_physical_distance = (
                physical_distance
            )

            best_weighted_distance = (
                weighted_distance
            )

            best_warehouses = (
                warehouse_indices
            )

            best_assignments = (
                assignments
            )


    # No feasible configuration

    if best_warehouses is None:

        return None


    warehouses = []


    for index in best_warehouses:

        warehouse = data.iloc[index]


        warehouses.append({

            "Neighborhood":
                warehouse["Neighborhood"],

            "Latitude":
                warehouse["Latitude"],

            "Longitude":
                warehouse["Longitude"]

        })


    return (

        warehouses,

        best_physical_distance,

        best_weighted_distance,

        best_cost,

        best_assignments

    )


# =================================================
# 5. BASELINE
# =================================================

def calculate_baseline(

    data,

    cost_per_km

):

    total_orders = data["Orders"].sum()


    if total_orders <= 0:

        return (

            data["Latitude"].mean(),

            data["Longitude"].mean(),

            0,

            0,

            0

        )


    center_lat = (

        (
            data["Latitude"]
            * data["Orders"]
        ).sum()

        / total_orders

    )


    center_lon = (

        (
            data["Longitude"]
            * data["Orders"]
        ).sum()

        / total_orders

    )


    total_physical_distance = 0

    total_weighted_distance = 0

    total_cost = 0


    for index, row in data.iterrows():

        distance = calculate_distance(

            row["Latitude"],
            row["Longitude"],

            center_lat,
            center_lon

        )


        total_physical_distance += (
            distance
        )


        weighted_distance = (

            distance
            * row["Orders"]

        )


        total_weighted_distance += (
            weighted_distance
        )


        total_cost += (

            weighted_distance
            * cost_per_km

        )


    return (

        center_lat,

        center_lon,

        total_physical_distance,

        total_weighted_distance,

        total_cost

    )


# =================================================
# 6. TRAVEL TIME
# =================================================

def calculate_average_travel_time(

    weighted_distance,

    total_orders,

    average_speed

):

    if total_orders <= 0:

        return 0


    if average_speed <= 0:

        return 0


    average_hours = (

        weighted_distance
        / average_speed
        / total_orders

    )


    return average_hours * 60