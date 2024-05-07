import math
import time
import heapq
import networkx as nx
import numpy as np

from scipy.optimize import fsolve, minimize
import warnings

from network_import import *
from utils import PathUtils

warnings.filterwarnings('ignore', 'The iteration is not making good progress')

class FlowTransportNetwork:

    def __init__(self):
        self.linkSet = {}
        self.nodeSet = {}

        self.tripSet = {}
        self.zoneSet = {}
        self.originZones = {}

        self.networkx_graph = None

    def to_networkx(self):
        if self.networkx_graph is None:
            self.networkx_graph = nx.DiGraph([(int(begin),int(end)) for (begin,end) in self.linkSet.keys()])
        return self.networkx_graph

    def reset_flow(self):
        for link in self.linkSet.values():
            link.reset_flow()

    def reset(self):
        for link in self.linkSet.values():
            link.reset()


class Zone:
    def __init__(self, zoneId: str):
        self.zoneId = zoneId

        self.lat = 0
        self.lon = 0
        self.destList = []  # list of zone ids (strs)


class Node:
    """
    This class has attributes associated with any node
    """

    def __init__(self, nodeId: str):
        self.Id = nodeId

        self.lat = 0
        self.lon = 0

        self.outLinks = []  # list of node ids (strs)
        self.inLinks = []  # list of node ids (strs)

        # For Dijkstra
        self.label = np.inf
        self.pred = None


class Link:
    """
    This class has attributes associated with any link
    """

    def __init__(self,
                 init_node: str,
                 term_node: str,
                 capacity: float,
                 length: float,
                 fft: float,
                 b: float,
                 power: float,
                 speed_limit: float,
                 toll: float,
                 linkType
                 ):
        self.init_node = init_node
        self.term_node = term_node
        self.max_capacity = float(capacity)  # veh per hour
        self.length = float(length)  # Length
        self.fft = float(fft)  # Free flow travel time (min)
        self.beta = float(power)
        self.alpha = float(b)
        self.speedLimit = float(speed_limit)
        self.toll = float(toll)
        self.linkType = linkType

        self.curr_capacity_percentage = 1
        self.capacity = self.max_capacity
        self.flow = 0.0
        self.cost = self.fft

    # Method not used for assignment
    def modify_capacity(self, delta_percentage: float):
        assert -1 <= delta_percentage <= 1
        self.curr_capacity_percentage += delta_percentage
        self.curr_capacity_percentage = max(0, min(1, self.curr_capacity_percentage))
        self.capacity = self.max_capacity * self.curr_capacity_percentage

    def reset(self):
        self.curr_capacity_percentage = 1
        self.capacity = self.max_capacity
        self.reset_flow()

    def reset_flow(self):
        self.flow = 0.0
        self.cost = self.fft


class Demand:
    def __init__(self,
                 init_node: str,
                 term_node: str,
                 demand: float
                 ):
        self.fromZone = init_node
        self.toNode = term_node
        self.demand = float(demand)


def DijkstraHeap(origin, network: FlowTransportNetwork):
    """
    Calcualtes shortest path from an origin to all other destinations.
    The labels and preds are stored in node instances.
    """
    for n in network.nodeSet:
        network.nodeSet[n].label = np.inf
        network.nodeSet[n].pred = None
    network.nodeSet[origin].label = 0.0
    network.nodeSet[origin].pred = None
    SE = [(0, origin)]
    while SE:
        currentNode = heapq.heappop(SE)[1]
        currentLabel = network.nodeSet[currentNode].label
        for toNode in network.nodeSet[currentNode].outLinks:
            link = (currentNode, toNode)
            newNode = toNode
            newPred = currentNode
            existingLabel = network.nodeSet[newNode].label
            newLabel = currentLabel + network.linkSet[link].cost
            if newLabel < existingLabel:
                heapq.heappush(SE, (newLabel, newNode))
                network.nodeSet[newNode].label = newLabel
                network.nodeSet[newNode].pred = newPred


def BPRcostFunction(optimal: bool,
                    fft: float,
                    alpha: float,
                    flow: float,
                    capacity: float,
                    beta: float,
                    length: float,
                    maxSpeed: float
                    ) -> float:
    if capacity < 1e-3:
        return np.finfo(np.float32).max
    if optimal:
        return fft * (1 + (alpha * math.pow((flow * 1.0 / capacity), beta)) * (beta + 1))
    return fft * (1 + alpha * math.pow((flow * 1.0 / capacity), beta))


def constantCostFunction(optimal: bool,
                         fft: float,
                         alpha: float,
                         flow: float,
                         capacity: float,
                         beta: float,
                         length: float,
                         maxSpeed: float
                         ) -> float:
    if optimal:
        return fft + flow
    return fft

def BPRcostFunctionDerivative(optimal: bool,
                              fft: float,
                              alpha: float,
                              flow: float,
                              capacity: float,
                              beta: float,
                              length: float,
                              maxSpeed: float
                              ) -> float:
    return fft * alpha * beta * math.pow((flow * 1.0 / capacity), beta - 1) / capacity

def BPRcostFunctionIntegral(optimal: bool,
                            fft: float,
                            alpha: float,
                            flow: float,
                            capacity: float,
                            beta: float,
                            length: float,
                            maxSpeed: float
                            ) -> float:
    return fft * (flow + alpha * flow * math.pow((flow * 1.0 / capacity), beta) / (1 + beta))

def greenshieldsCostFunction(optimal: bool,
                             fft: float,
                             alpha: float,
                             flow: float,
                             capacity: float,
                             beta: float,
                             length: float,
                             maxSpeed: float
                             ) -> float:
    if capacity < 1e-3:
        return np.finfo(np.float32).max
    if optimal:
        return (length * (capacity ** 2)) / (maxSpeed * (capacity - flow) ** 2)
    return length / (maxSpeed * (1 - (flow / capacity)))


def updateTravelTime(network: FlowTransportNetwork, optimal: bool = False, costFunction=BPRcostFunction):
    """
    This method updates the travel time on the links with the current flow
    """
    for l in network.linkSet:
        network.linkSet[l].cost = costFunction(optimal,
                                               network.linkSet[l].fft,
                                               network.linkSet[l].alpha,
                                               network.linkSet[l].flow,
                                               network.linkSet[l].capacity,
                                               network.linkSet[l].beta,
                                               network.linkSet[l].length,
                                               network.linkSet[l].speedLimit
                                               )


def findAlpha(x_bar, network: FlowTransportNetwork, optimal: bool = False, costFunction=BPRcostFunction):
    """
    This uses unconstrained optimization to calculate the optimal step size required
    for Frank-Wolfe Algorithm
    """

    def sum(alpha):
        # alpha = max(0, min(1, alpha))
        sum_integral = 0  # this line is the derivative of the objective function.
        for l in network.linkSet:
            tmpFlow = alpha * x_bar[l] + (1 - alpha) * network.linkSet[l].flow
            tmpCost = BPRcostFunctionIntegral(optimal,
                                              network.linkSet[l].fft,
                                              network.linkSet[l].alpha,
                                              tmpFlow,
                                              network.linkSet[l].capacity,
                                              network.linkSet[l].beta,
                                              network.linkSet[l].length,
                                              network.linkSet[l].speedLimit
                                              )
            sum_integral = sum_integral + tmpCost
        return sum_integral

    sol = minimize(sum, np.array([0.5]), tol=1e-10)
    return max(0, min(1, sol.x[0]))


def tracePreds(dest, network: FlowTransportNetwork):
    """
    This method traverses predecessor nodes in order to create a shortest path
    """
    prevNode = network.nodeSet[dest].pred
    spLinks = []
    while prevNode is not None:
        spLinks.append((prevNode, dest))
        dest = prevNode
        prevNode = network.nodeSet[dest].pred
    return spLinks


def loadAON(network: FlowTransportNetwork, computeXbar: bool = True):
    """
    This method produces auxiliary flows for all or nothing loading.
    """
    x_bar = {l: 0.0 for l in network.linkSet}
    SPTT = 0.0
    for r in network.originZones:
        DijkstraHeap(r, network=network)
        for s in network.zoneSet[r].destList:
            dem = network.tripSet[r, s].demand

            if dem <= 0:
                continue

            SPTT = SPTT + network.nodeSet[s].label * dem

            if computeXbar and r != s:
                for spLink in tracePreds(s, network):
                    x_bar[spLink] = x_bar[spLink] + dem

    return SPTT, x_bar


def readDemand(demand_df: pd.DataFrame, network: FlowTransportNetwork):
    for index, row in demand_df.iterrows():

        init_node = str(int(row["init_node"]))
        term_node = str(int(row["term_node"]))
        demand = row["demand"]

        if init_node == term_node or demand == 0: continue
        network.tripSet[init_node, term_node] = Demand(init_node, term_node, demand)
        if init_node not in network.zoneSet:
            network.zoneSet[init_node] = Zone(init_node)
        if term_node not in network.zoneSet:
            network.zoneSet[term_node] = Zone(term_node)
        if term_node not in network.zoneSet[init_node].destList:
            network.zoneSet[init_node].destList.append(term_node)

    print(len(network.tripSet), "OD pairs")
    print(len(network.zoneSet), "OD zones")


def readNetwork(network_df: pd.DataFrame, network: FlowTransportNetwork):
    for index, row in network_df.iterrows():

        init_node = str(int(row["init_node"]))
        term_node = str(int(row["term_node"]))
        capacity = row["capacity"]
        length = row["length"]
        free_flow_time = row["free_flow_time"]
        b = row["b"]
        power = row["power"]
        speed = row["speed"]
        toll = row["toll"]
        link_type = row["link_type"]

        network.linkSet[init_node, term_node] = Link(init_node=init_node,
                                                     term_node=term_node,
                                                     capacity=capacity,
                                                     length=length,
                                                     fft=free_flow_time,
                                                     b=b,
                                                     power=power,
                                                     speed_limit=speed,
                                                     toll=toll,
                                                     linkType=link_type
                                                     )
        if init_node not in network.nodeSet:
            network.nodeSet[init_node] = Node(init_node)
        if term_node not in network.nodeSet:
            network.nodeSet[term_node] = Node(term_node)
        if term_node not in network.nodeSet[init_node].outLinks:
            network.nodeSet[init_node].outLinks.append(term_node)
        if init_node not in network.nodeSet[term_node].inLinks:
            network.nodeSet[term_node].inLinks.append(init_node)

    print(len(network.nodeSet), "nodes")
    print(len(network.linkSet), "links")


def get_TSTT(network: FlowTransportNetwork, costFunction=BPRcostFunction, use_max_capacity: bool = True):
    TSTT = round(sum([network.linkSet[a].flow * costFunction(optimal=False,
                                                             fft=network.linkSet[
                                                                 a].fft,
                                                             alpha=network.linkSet[
                                                                 a].alpha,
                                                             flow=network.linkSet[
                                                                 a].flow,
                                                             capacity=network.linkSet[
                                                                 a].max_capacity if use_max_capacity else network.linkSet[
                                                                 a].capacity,
                                                             beta=network.linkSet[
                                                                 a].beta,
                                                             length=network.linkSet[
                                                                 a].length,
                                                             maxSpeed=network.linkSet[
                                                                 a].speedLimit
                                                             ) for a in
                      network.linkSet]), 9)
    return TSTT

def calculate_conjugate_beta(network: FlowTransportNetwork, d_FW, d_bar, optimal: bool = False):
    beta_numerator = np.sum([d_bar[l] * d_FW[l] * BPRcostFunctionDerivative(
        optimal,
        network.linkSet[l].fft,
        network.linkSet[l].alpha,
        network.linkSet[l].flow,
        network.linkSet[l].capacity,
        network.linkSet[l].beta,
        network.linkSet[l].length,
        network.linkSet[l].speedLimit) for l in network.linkSet])
    beta_denominator = np.sum([d_bar[l] * (d_FW[l] - d_bar[l]) * BPRcostFunctionDerivative(
        optimal,
        network.linkSet[l].fft,
        network.linkSet[l].alpha,
        network.linkSet[l].flow,
        network.linkSet[l].capacity,
        network.linkSet[l].beta,
        network.linkSet[l].length,
        network.linkSet[l].speedLimit) for l in network.linkSet])
    if beta_denominator == 0:
        beta = 0
    else:
        beta = beta_numerator / beta_denominator
        if beta > 1 - 1e-9:
            beta = 1 - 1e-9
        elif beta < 0:
            beta = 0
    return beta

def assignment_loop(network: FlowTransportNetwork,
                    algorithm: str = "FW",
                    systemOptimal: bool = False,
                    costFunction=BPRcostFunction,
                    accuracy: float = 0.001,
                    maxIter: int = 1000,
                    maxTime: int = 60,
                    verbose: bool = True,
                    output_file: str = None):
    """
    For explaination of the algorithm see Chapter 7 of:
    https://sboyles.github.io/blubook.html
    PDF:
    https://sboyles.github.io/teaching/ce392c/book.pdf
    """
    network.reset_flow()

    iteration_number = 1
    gap = np.inf
    gaps = []
    TSTT = np.inf
    assignmentStartTime = time.time()

    # Check if desired accuracy is reached
    while gap > accuracy:

        # Get x_bar throug all-or-nothing assignment
        _, x_bar = loadAON(network=network)

        if algorithm == "CFW":
            d_FW = {l: x_bar[l] - network.linkSet[l].flow for l in network.linkSet}
            if iteration_number == 1:
                d_CFW = d_FW
            else:
                d_bar = {l: (1 - alpha) * d_CFW[l] for l in network.linkSet}
                beta = calculate_conjugate_beta(network, d_FW, d_bar, systemOptimal)
                d_CFW = {l: d_FW[l] + beta * (d_bar[l] - d_FW[l]) for l in network.linkSet}
                x_bar = {l: d_CFW[l] + network.linkSet[l].flow for l in network.linkSet}

        if algorithm == "MSA" or iteration_number == 1:
            alpha = (2 / (iteration_number + 1))
        elif algorithm in ["FW", "CFW"]:
            # If using Frank-Wolfe determine the step size alpha by solving a nonlinear equation
            alpha = findAlpha(x_bar,
                              network=network,
                              optimal=systemOptimal,
                              costFunction=costFunction)
        else:
            print("Terminating the program.....")
            print("The solution algorithm ", algorithm, " does not exist!")
            raise TypeError('Algorithm must be MSA, FW or CFW')

        # Apply flow improvement
        for l in network.linkSet:
            network.linkSet[l].flow = alpha * x_bar[l] + (1 - alpha) * network.linkSet[l].flow

        # Compute the new travel time
        updateTravelTime(network=network,
                         optimal=systemOptimal,
                         costFunction=costFunction)

        # Compute the relative gap
        SPTT, _ = loadAON(network=network, computeXbar=False)
        SPTT = round(SPTT, 9)
        TSTT = round(sum([network.linkSet[a].flow * network.linkSet[a].cost for a in
                          network.linkSet]), 9)

        # print(TSTT, SPTT, "TSTT, SPTT, Max capacity", max([l.capacity for l in network.linkSet.values()]))
        gap = (TSTT / SPTT) - 1
        runTime = time.time() - assignmentStartTime
        gaps.append([runTime, gap])
        if gap < 0:
            print("Error, gap is less than 0, this should not happen")
            print("TSTT", "SPTT", TSTT, SPTT)

            # Uncomment for debug

            # print("Capacities:", [l.capacity for l in network.linkSet.values()])
            # print("Flows:", [l.flow for l in network.linkSet.values()])

        # Compute the real total travel time (which in the case of system optimal rounting is different from the TSTT above)
        TSTT = get_TSTT(network=network, costFunction=costFunction)

        iteration_number += 1
        if iteration_number > maxIter:
            if verbose:
                print(
                    "The assignment did not converge to the desired gap and the max number of iterations has been reached")
                print("Assignment took", round(time.time() - assignmentStartTime, 5), "seconds")
                print("Current gap:", round(gap, 5))
            verbose = False
            break
        if time.time() - assignmentStartTime > maxTime:
            if verbose:
                print("The assignment did not converge to the desired gap and the max time limit has been reached")
                print("Assignment did ", iteration_number, "iterations")
                print("Current gap:", round(gap, 5))
            verbose = False
            break

    if verbose:
        print("Assignment converged in ", iteration_number, "iterations")
        print("Assignment took", round(time.time() - assignmentStartTime, 5), "seconds")
        print("Current gap:", round(gap, 5))
    if output_file is not None:
        np.savetxt(f"./iteration_gaps/{output_file}", np.array(gaps), fmt="%.9f")
    return TSTT

class Route:
    def __init__(self):
        self.r = -1
        self.s = -1
        self.cost = np.inf
        self.links = []
        self.flow = 0

def cal_shortest_routes(network: FlowTransportNetwork):
    """
    This method calculates shortest route for all OD pairs.
    """
    shortest_routes = {}
    for r in network.originZones:
        DijkstraHeap(r, network=network)
        for s in network.zoneSet[r].destList:
            dem = network.tripSet[r, s].demand

            if dem <= 0:
                continue

            route = Route()
            route.r = r
            route.s = s
            route.cost = network.nodeSet[s].label
            if r != s: route.links = tracePreds(s, network)

            shortest_routes[(r, s)] = route

    return shortest_routes

def update_network_flow(network: FlowTransportNetwork, routes: dict):
    network.reset_flow()
    for OD, route_list in routes.items():
        for route in route_list:
            for link in route.links:
                network.linkSet[link].flow += route.flow

def update_routes_cost(network: FlowTransportNetwork, routes: dict):
    for OD, route_list in routes.items():
        for route in route_list:
            route.cost = 0
            for link in route.links:
                route.cost += network.linkSet[link].cost

def calculate_second_derivative(network: FlowTransportNetwork, route: Route, shortest_route: Route):
    h = 0
    route_set = set(route.links)
    shortest_route_set = set(shortest_route.links)
    link_set = route_set ^ shortest_route_set
    for l in link_set:
        link = network.linkSet[l]
        h += BPRcostFunctionDerivative(
            False,
            network.linkSet[l].fft,
            network.linkSet[l].alpha,
            network.linkSet[l].flow,
            network.linkSet[l].capacity,
            network.linkSet[l].beta,
            network.linkSet[l].length,
            network.linkSet[l].speedLimit)
    return h

def obtain_step_direction(routes, shortest_routes, network: FlowTransportNetwork):
    step_direction = {(OD, route_idx): 0 for OD, OD_routes in routes for route_idx in range(len(OD_routes))}
    for OD, OD_routes in routes.items():
        shortest_route = shortest_routes[OD]
        route_idx = 0
        for route in OD_routes:
            if len(set(route.links) ^ set(shortest_route.links)) == 0:
                shortest_route = route
                step_direction[(OD, route_idx)] = 0
            else:
                h = calculate_second_derivative(network, route, shortest_route)
                if h == 0:
                    step_direction[(OD, route_idx)] = np.inf
                else:
                    step_direction[(OD, route_idx)] = (route.cost - shortest_route.cost) / h
            route_idx += 1
    return step_direction

def exact_line_search_for_path_based_gp(routes, shortest_routes, network: FlowTransportNetwork):
    """
    This uses unconstrained optimization to calculate the optimal step size required
    for GP Algorithm
    """
    step_direction = obtain_step_direction(routes, shortest_routes, network)
    def sum(alpha):
        sum_integral = 0  # this line is the derivative of the objective function.
        tmp_link_flow = {l: 0 for l in network.linkSet}
        for OD, OD_routes in routes.items():
            shortest_route = shortest_routes[OD]
            flow_sum = 0
            route_idx = 0
            for route in OD_routes:
                tmp_route_flow = max(0, route.flow - alpha * step_direction[(OD, route_idx)])
                flow_sum += tmp_route_flow
                for link in route.links:
                    tmp_link_flow[link] += tmp_route_flow
                route_idx += 1
            tmp_shortest_route_flow = network.tripSet[shortest_route.r, shortest_route.s].demand - flow_sum
            for link in shortest_route.links:
                tmp_link_flow[link] += tmp_shortest_route_flow
        for l, tmpFlow in tmp_link_flow.items():
            tmpCost = BPRcostFunctionIntegral(False,
                                      network.linkSet[l].fft,
                                      network.linkSet[l].alpha,
                                      tmpFlow,
                                      network.linkSet[l].capacity,
                                      network.linkSet[l].beta,
                                      network.linkSet[l].length,
                                      network.linkSet[l].speedLimit
                                      )
            sum_integral = sum_integral + tmpCost
        return sum_integral
    sol = minimize(sum, x0=np.array([0.1]), tol=1e-3)
    alpha = max(0, min(1, sol.x[0]))
    if alpha == 0: alpha = 1e-2
    return alpha, step_direction

def path_based_gp_method(network: FlowTransportNetwork,
                         algorithm: str = "GP",
                         systemOptimal: bool = False,
                         costFunction=BPRcostFunction,
                         accuracy: float = 0.001,
                         maxIter: int = 1000,
                         maxTime: int = 60,
                         verbose: bool = True,
                         output_file: str = None,
                         step_size: float = 0.05):
    """
    Ref: A Faster Path-Based Algorithm for Traffic Assignment
    """
    network.reset_flow()

    iteration_number = 1
    gap = np.inf
    gaps = []
    TSTT = np.inf
    assignmentStartTime = time.time()
    routes = {(r, s): [] for r in network.originZones for s in network.zoneSet[r].destList }

    # Check if desired accuracy is reached
    while gap > accuracy:
        shortest_routes = cal_shortest_routes(network)
        if iteration_number == 1:
            for OD, route in shortest_routes.items():
                route.flow = network.tripSet[route.r, route.s].demand
                routes[OD].append(route)
        else:
            if algorithm == "GP-E":
                alpha, step_direction = exact_line_search_for_path_based_gp(routes, shortest_routes, network)
            else:
                alpha = step_size
                step_direction = obtain_step_direction(routes, shortest_routes, network)
            for OD, OD_routes in routes.items():
                shortest_route = shortest_routes[OD]
                is_append = True
                flow_sum = 0
                route_idx = 0
                for route in OD_routes:
                    if step_direction[(OD, route_idx)] == 0:
                        shortest_route = route
                        is_append = False
                    else:
                        route.flow = max(0, route.flow - alpha * step_direction[(OD, route_idx)])
                        flow_sum += route.flow
                    route_idx += 1
                shortest_route.flow = network.tripSet[shortest_route.r, shortest_route.s].demand - flow_sum
                if is_append: OD_routes.append(shortest_route)

        # Compute the new travel time
        update_network_flow(network, routes)
        updateTravelTime(network=network, optimal=systemOptimal, costFunction=costFunction)
        update_routes_cost(network, routes)

        # Compute the relative gap
        SPTT, _ = loadAON(network=network, computeXbar=False)
        SPTT = round(SPTT, 9)
        TSTT = round(sum([network.linkSet[a].flow * network.linkSet[a].cost for a in
                          network.linkSet]), 9)

        # print(TSTT, SPTT, "TSTT, SPTT, Max capacity", max([l.capacity for l in network.linkSet.values()]))
        gap = (TSTT / SPTT) - 1
        runTime = time.time() - assignmentStartTime
        gaps.append([runTime, gap])
        if gap < 0:
            print("Error, gap is less than 0, this should not happen")
            print("TSTT", "SPTT", TSTT, SPTT)

            # Uncomment for debug

            # print("Capacities:", [l.capacity for l in network.linkSet.values()])
            # print("Flows:", [l.flow for l in network.linkSet.values()])

        # Compute the real total travel time (which in the case of system optimal rounting is different from the TSTT above)
        TSTT = get_TSTT(network=network, costFunction=costFunction)

        iteration_number += 1
        if iteration_number > maxIter:
            if verbose:
                print(
                    "The assignment did not converge to the desired gap and the max number of iterations has been reached")
                print("Assignment took", round(time.time() - assignmentStartTime, 5), "seconds")
                print("Current gap:", round(gap, 5))
            verbose = False
            break
        if time.time() - assignmentStartTime > maxTime:
            if verbose:
                print("The assignment did not converge to the desired gap and the max time limit has been reached")
                print("Assignment did ", iteration_number, "iterations")
                print("Current gap:", round(gap, 5))
            verbose = False
            break

    if verbose:
        print("Assignment converged in ", iteration_number, "iterations")
        print("Assignment took", round(time.time() - assignmentStartTime, 5), "seconds")
        print("Current gap:", round(gap, 5))
    if output_file is not None:
        np.savetxt(f"./iteration_gaps/{output_file}", np.array(gaps), fmt="%.9f")
    return TSTT


def writeResults(network: FlowTransportNetwork, output_file: str, costFunction=BPRcostFunction,
                 systemOptimal: bool = False, verbose: bool = True):
    outFile = open(output_file, "w")
    TSTT = get_TSTT(network=network, costFunction=costFunction)
    if verbose:
        print("\nTotal system travel time:", f'{TSTT} secs')
    tmpOut = "Total Travel Time:\t" + str(TSTT)
    outFile.write(tmpOut + "\n")
    tmpOut = "Cost function used:\t" + BPRcostFunction.__name__
    outFile.write(tmpOut + "\n")
    tmpOut = ["User equilibrium (UE) or system optimal (SO):\t"] + ["SO" if systemOptimal else "UE"]
    outFile.write("".join(tmpOut) + "\n\n")
    tmpOut = "init_node\tterm_node\tflow\ttravelTime"
    outFile.write(tmpOut + "\n")
    for i in network.linkSet:
        tmpOut = str(network.linkSet[i].init_node) + "\t" + str(
            network.linkSet[i].term_node) + "\t" + str(
            network.linkSet[i].flow) + "\t" + str(costFunction(False,
                                                               network.linkSet[i].fft,
                                                               network.linkSet[i].alpha,
                                                               network.linkSet[i].flow,
                                                               network.linkSet[i].max_capacity,
                                                               network.linkSet[i].beta,
                                                               network.linkSet[i].length,
                                                               network.linkSet[i].speedLimit
                                                               ))
        outFile.write(tmpOut + "\n")
    outFile.close()


def load_network(net_file: str,
                 demand_file: str = None,
                 force_net_reprocess: bool = False,
                 verbose: bool = True
                 ) -> FlowTransportNetwork:
    readStart = time.time()

    if demand_file is None:
        demand_file = '_'.join(net_file.split("_")[:-1] + ["trips.tntp"])

    net_name = net_file.split("/")[-1].split("_")[0]

    if verbose:
        print(f"Loading network {net_name}...")

    net_df, demand_df = import_network(
        net_file,
        demand_file,
        force_reprocess=force_net_reprocess
    )

    network = FlowTransportNetwork()

    readDemand(demand_df, network=network)
    readNetwork(net_df, network=network)

    network.originZones = set([k[0] for k in network.tripSet])

    if verbose:
        print("Network", net_name, "loaded")
        print("Reading the network data took", round(time.time() - readStart, 2), "secs\n")

    return network


def computeAssingment(net_file: str,
                      demand_file: str = None,
                      algorithm: str = "FW",  # FW or MSA
                      costFunction=BPRcostFunction,
                      systemOptimal: bool = False,
                      accuracy: float = 0.0001,
                      maxIter: int = 1000,
                      maxTime: int = 60,
                      results_file: str = None,
                      force_net_reprocess: bool = False,
                      verbose: bool = True,
                      step_size = 0.05,
                      ) -> float:
    """
    This is the main function to compute the user equilibrium UE (default) or system optimal (SO) traffic assignment
    All the networks present on https://github.com/bstabler/TransportationNetworks following the tntp format can be loaded


    :param net_file: Name of the network (net) file following the tntp format (see https://github.com/bstabler/TransportationNetworks)
    :param demand_file: Name of the demand (trips) file following the tntp format (see https://github.com/bstabler/TransportationNetworks), leave None to use dafault demand file
    :param algorithm:
           - "FW": Frank-Wolfe algorithm (see https://en.wikipedia.org/wiki/Frank%E2%80%93Wolfe_algorithm)
           - "MSA": Method of successive averages
           For more information on how the algorithms work see https://sboyles.github.io/teaching/ce392c/book.pdf
    :param costFunction: Which cost function to use to compute travel time on edges, currently available functions are:
           - BPRcostFunction (see https://rdrr.io/rforge/travelr/man/bpr.function.html)
           - greenshieldsCostFunction (see Greenshields, B. D., et al. "A study of traffic capacity." Highway research board proceedings. Vol. 1935. National Research Council (USA), Highway Research Board, 1935.)
           - constantCostFunction
    :param systemOptimal: Wheather to compute the system optimal flows instead of the user equilibrium
    :param accuracy: Desired assignment precision gap
    :param maxIter: Maximum nuber of algorithm iterations
    :param maxTime: Maximum seconds allowed for the assignment
    :param results_file: Name of the desired file to write the results,
           by default the result file is saved with the same name as the input network with the suffix "_flow.tntp" in the same folder
    :param force_net_reprocess: True if the network files should be reprocessed from the tntp sources
    :param verbose: print useful info in standard output
    :return: Total system travel time
    """

    network = load_network(net_file=net_file, demand_file=demand_file, verbose=verbose, force_net_reprocess=force_net_reprocess)

    iteration_gaps_file = '_'.join(net_file.split("/")[-1].split("_")[:-1] + [algorithm] + ["gaps.csv"])
    if verbose:
        print("Computing assignment...")
    if algorithm in ["FW", "MSA", "CFW"]:
        TSTT = assignment_loop(network=network, algorithm=algorithm, systemOptimal=systemOptimal, costFunction=costFunction,
                               accuracy=accuracy, maxIter=maxIter, maxTime=maxTime, verbose=verbose, output_file=iteration_gaps_file)
    elif algorithm in ["GP", "GP-E"]:
        TSTT = path_based_gp_method(network=network, algorithm=algorithm, systemOptimal=systemOptimal, costFunction=costFunction,
                                    accuracy=accuracy, maxIter=maxIter, maxTime=maxTime, verbose=verbose, output_file=iteration_gaps_file,
                                    step_size=step_size)

    if results_file is None:
        results_file = '_'.join(net_file.split("_")[:-1] + ["flow.tntp"])

    writeResults(network=network,
                 output_file=results_file,
                 costFunction=costFunction,
                 systemOptimal=systemOptimal,
                 verbose=verbose)

    return TSTT


if __name__ == '__main__':

    # This is an example usage for calculating System Optimal and User Equilibrium with Frank-Wolfe

    net_file = str(PathUtils.sioux_falls_net_file)

    total_system_travel_time_equilibrium_FW = computeAssingment(net_file=net_file,
                                                                algorithm="FW",
                                                                costFunction=BPRcostFunction,
                                                                systemOptimal=False,
                                                                verbose=True,
                                                                accuracy=0.000000001,
                                                                maxIter=20000,
                                                                maxTime=100)
    total_system_travel_time_equilibrium_GP = computeAssingment(net_file=net_file,
                                                                algorithm="GP",
                                                                costFunction=BPRcostFunction,
                                                                systemOptimal=False,
                                                                verbose=True,
                                                                accuracy=0.000000001,
                                                                maxIter=20000,
                                                                maxTime=100,
                                                                step_size=0.05)
    total_system_travel_time_equilibrium_GP_E = computeAssingment(net_file=net_file,
                                                                algorithm="GP-E",
                                                                costFunction=BPRcostFunction,
                                                                systemOptimal=False,
                                                                verbose=True,
                                                                accuracy=0.000000001,
                                                                maxIter=20000,
                                                                maxTime=100)
    total_system_travel_time_equilibrium_CFW = computeAssingment(net_file=net_file,
                                                                algorithm="CFW",
                                                                costFunction=BPRcostFunction,
                                                                systemOptimal=False,
                                                                verbose=True,
                                                                accuracy=0.000000001,
                                                                maxIter=20000,
                                                                maxTime=100)
    total_system_travel_time_equilibrium_MSA = computeAssingment(net_file=net_file,
                                                                algorithm="MSA",
                                                                costFunction=BPRcostFunction,
                                                                systemOptimal=False,
                                                                verbose=True,
                                                                accuracy=0.000000001,
                                                                maxIter=20000,
                                                                maxTime=100)


    print("CFW - FW = ", total_system_travel_time_equilibrium_CFW - total_system_travel_time_equilibrium_FW)
    print("MSA - FW = ", total_system_travel_time_equilibrium_MSA - total_system_travel_time_equilibrium_FW)
    print("GP - FW = ", total_system_travel_time_equilibrium_GP - total_system_travel_time_equilibrium_FW)
    print("GP-E - FW = ", total_system_travel_time_equilibrium_GP_E - total_system_travel_time_equilibrium_FW)
