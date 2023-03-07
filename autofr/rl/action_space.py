import logging
import os
from typing import List

import networkx as nx
import pandas as pd
from networkx.classes.reportviews import NodeView

from autofr.common.action_space_utils import ROOT_NODE_ID, TYPE_ESLD, TYPE_FQDN, TYPE_FQDN_PATH, \
    get_initiator_chain_graph_raw, get_initiator_chain_graph_esld, get_initiator_chain_graph_fqdn, \
    get_initiator_chain_graph_fqdn_path, remove_node_and_connect, transfer_initiator_g
from autofr.common.exceptions import RootMissingException, MissingActionSpace, ActionSpaceException
from autofr.common.utils import get_variations_of_domains, is_real_fqdn, is_real_fqdn_with_path

NAME = "name"
LABEL = "label"
TEXT = "Text"
ACTION_ATTEMPTS = "action_attempts"
FILTER_MATCHES = "filter_matches"
SLEEPING_ARM = "sleeping"
Q_VALUE = "q_value"
QUCB_VALUE = "qucb_value"
AVG_REWARD = "avg_reward"
REWARD = "reward"
TIME = "time"
TYPE = "type"
EDGE_TYPE = "edge_type"
MIN_Q_VALUE = -9999999
DEFAULT_Q_VALUE = 0.2
UNKNOWN_ARM = "unknown"
Q_VALUE_FROM_PRIOR = "q_value_from_prior"
AVG_REWARD_FROM_PRIOR = "avg_reward_from_prior"
STD_HISTORY = "std_history"
VARIANCE = "variance"
AD_COUNTER = "ad_counter"
IMAGE_COUNTER = "image_counter"
TEXTNODE_COUNTER = "textnode_counter"
AD_REMOVED = "ad_removed"
TEXTNODE_MISSING = "textnode_missing"
IMAGE_MISSING = "image_missing"
EXPLORED = "explored"
EDGE_TYPE_INITIATOR = "initiator"
EDGE_TYPE_FINER_GRAIN = "finer_grain"
INIT_NODE_HISTORY_ACTION_TIMES = "init_action_times"
NODE_HISTORY_ACTION_TIMES = "action_times"
NO_MATCH_NODE_HISTORY_ACTION_TIMES = "no_match_action_times"
NODE_HISTORY_Q = "q_values"
NODE_HISTORY_AGENT_INFO = "agent_info"
NODE_HISTORY_AGENT_INFO__INIT_STATE_INFO = "agent_info_init_state"
NODE_HISTORY_AGENT_INFO__INIT_STATE_MIN = "agent_info_state_min"
NODE_HISTORY_AGENT_INFO__INIT_STATE_MAX = "agent_info_state_max"
NODE_HISTORY_AGENT_INFO__INIT_STATE_AVERAGE = "agent_info_state_average"
ROUND_HISTORY = "round_history"
GOOD_COUNT = "good_count"
BAD_COUNT = "bad_count"
TRACKING_COUNT = "tracking_count"
ACTION_SPACE = "action_space"
ACTION_SPACE_TOTAL_NODES = "total_nodes"
ACTION_SPACE_TOTAL_EDGES = "total_edges"
ACTION_SPACE_EXPLORED_NODES = "explored_nodes"
CHOSEN_ACTIONS = "chosen_actions"
DH_GRAPH = "dh_graph"

SLEEPING_ARM_THRESHOLD = 2
CHUNK_LIST_THRESHOLD = 2
INVALID_VALUE = -1

logger = logging.getLogger(__name__)


def create_default_node_attributes(node_type: str, node_time: int, default_q_value: float = DEFAULT_Q_VALUE) -> dict:
    attributes = dict()
    attributes[ACTION_ATTEMPTS] = 0
    attributes[Q_VALUE] = default_q_value
    attributes[QUCB_VALUE] = 0
    attributes[FILTER_MATCHES] = 0
    attributes[SLEEPING_ARM] = False
    attributes[TYPE] = node_type
    attributes[TIME] = node_time
    attributes[UNKNOWN_ARM] = False
    attributes[Q_VALUE_FROM_PRIOR] = False
    attributes[AVG_REWARD] = 0
    attributes[AVG_REWARD_FROM_PRIOR] = False
    attributes[STD_HISTORY] = 0
    attributes[VARIANCE] = 0
    attributes[EXPLORED] = False
    return attributes


class ActionSpace:

    def __init__(self, output_directory: str,
                 unique_suffix: str,
                 default_q_value: float = DEFAULT_Q_VALUE):
        self._dh_graph = nx.DiGraph()
        self.output_directory = output_directory
        self.unique_suffix = unique_suffix
        self.default_q_value = default_q_value
        self.copy_dh_graph = nx.DiGraph()
        self.built_graph = False

    @classmethod
    def get_classname(cls):
        return cls.__name__

    def reset(self):
        if self.built_graph is None:
            raise MissingActionSpace("Cannot reset action space without building graph first")

        self._dh_graph = self.copy_dh_graph.copy()

    def get_nodes(self) -> NodeView:
        return self._dh_graph.nodes

    def contains(self, node: str) -> bool:
        return self._dh_graph.nodes.get(node) is not None

    def get_graph(self) -> nx.DiGraph:
        return self._dh_graph

    def get(self, node: str):
        return self._dh_graph.nodes.get(node)

    def get_number_of_awake_nodes(self, node_type: str = None) -> int:
        if self._dh_graph:
            count = 0
            for n, n_data in self._dh_graph.nodes(data=True):
                if n == self.get_root():
                    continue
                if SLEEPING_ARM in n_data and not n_data[SLEEPING_ARM]:
                    if node_type:
                        if TYPE in n_data and n_data[TYPE] == node_type:
                            count += 1
                    else:
                        count += 1
            return count
        return 0

    def set_nodes_as_explored(self, nodes: list):
        """
        Keep track of which nodes are explored
        """
        for n in nodes:
            if self.contains(n):
                self._dh_graph.nodes[n][EXPLORED] = True

    def get_number_of_nodes(self) -> int:
        return self._dh_graph.number_of_nodes()

    def get_number_of_edges(self) -> int:
        return self._dh_graph.number_of_edges()

    def get_number_of_explored_nodes(self) -> int:
        count = 0
        for n, n_data in self._dh_graph.nodes(data=True):
            if EXPLORED in n_data and n_data[EXPLORED]:
                count += 1
        return count

    def get_explored_nodes_with_q_values(self) -> list:
        """
        For every explored node, get its Q_VALUE
        """
        records = []
        for n, n_data in self._dh_graph.nodes(data=True):
            if EXPLORED in n_data and n_data[EXPLORED]:
                records.append({"action": n, Q_VALUE: n_data[Q_VALUE]})
        return records

    def get_action_attempts_of_nodes(self) -> list:
        """
        For every node, get the number of times it been pulled
        """
        records = []
        for n, n_data in self._dh_graph.nodes(data=True):
            if EXPLORED in n_data and n_data[EXPLORED]:
                attempted = 0
                if ACTION_ATTEMPTS in n_data:
                    attempted = n_data[ACTION_ATTEMPTS]
                records.append({"action": n, ACTION_ATTEMPTS: attempted})
        return records

    def save(self):

        graph_graphml_file = f"{DH_GRAPH}_{self.unique_suffix}.graphml"
        if self.output_directory:
            graph_graphml_file = self.output_directory + os.sep + graph_graphml_file

        nx.write_graphml(self._dh_graph, graph_graphml_file)

        # write out csv
        action_values_file = f"action_values_{self.unique_suffix}.csv"
        if self.output_directory:
            action_values_file = self.output_directory + os.sep + action_values_file

        rows = []
        columns = None
        for n, n_data in self._dh_graph.nodes(data=True):
            if n != self.get_root() and EXPLORED in n_data:
                n_dict = dict()
                n_dict["name"] = n
                n_dict.update(n_data)
                rows.append(n_dict)
                if not columns:
                    columns = list(n_dict.keys())
        df = pd.DataFrame(columns=columns)
        df = df.from_dict(rows)
        df.to_csv(action_values_file, index=False)

    def add_node(self, node: str, attributes: dict, parent: str = None, edge_types: dict = None) -> bool:
        if node not in self._dh_graph.nodes:
            attributes[NAME] = node
            attributes[TEXT] = node
            self._dh_graph.add_nodes_from([(node, attributes)])
            if parent:
                if not edge_types:
                    self._dh_graph.add_edge(parent, node)
                else:
                    self._dh_graph.add_edge(parent, node, **edge_types)
            return True
        return False

    def add_child_to_root(self, domain: str, node_time: int = 0) -> bool:

        sld, fqdn, fqdn_and_path, path = get_variations_of_domains(domain)
        if sld is not None and sld not in self._dh_graph.nodes:
            self.add_node(sld,
                          create_default_node_attributes(TYPE_ESLD, node_time, default_q_value=self.default_q_value),
                          parent=self.get_root(), edge_types={"edge_type": EDGE_TYPE_INITIATOR})
            return True
        return False

    def add_child_to_root_fqdn(self, domain: str, node_time: int = 0):
        self.add_fqdn_to_parent(self.get_root(), domain, node_time=node_time)

    def add_fqdn_to_parent(self, parent: str, url: str, node_time: int = 0) -> bool:

        sld, fqdn, fqdn_and_path, path = get_variations_of_domains(url)

        if sld is not None and is_real_fqdn(fqdn, [sld]) and fqdn not in self._dh_graph.nodes:
            self.add_node(fqdn,
                          create_default_node_attributes(TYPE_FQDN, node_time, default_q_value=self.default_q_value),
                          parent=parent, edge_types={"edge_type": EDGE_TYPE_FINER_GRAIN})
            return True

        return False

    def get_root(self) -> str:
        root = None
        try:
            root = self._dh_graph.graph[ROOT_NODE_ID]
        except:
            logger.warning("Could not find root node")
        return root

    def get_root_url(self) -> str:
        return self.get(self.get_root())[NAME]

    def add_root(self, root: str):
        # keep track of where the root is
        root_key = f"{root}_ROOT"
        self._dh_graph.graph[ROOT_NODE_ID] = root_key
        # add the root
        self._dh_graph.add_node(root_key)
        self._dh_graph.nodes[root_key][NAME] = root
        self._dh_graph.nodes[root_key][TEXT] = root
        self._dh_graph.nodes[root_key][SLEEPING_ARM] = False
        self._dh_graph.nodes[root_key][UNKNOWN_ARM] = False
        #logger.debug(f"Added root {root}, graph root info: {self._dh_graph.nodes[root_key]}")

    def check_for_no_parents(self):
        """
        Ensure that for all nodes, if it has no parent, then it should connect to the root
        """
        for node, node_data in self._dh_graph.nodes(data=True):
            predecessors = list(self._dh_graph.predecessors(node))
            if len(predecessors) == 0:
                if node != self.get_root() and TYPE in node_data and node_data[TYPE] == TYPE_ESLD:
                    # logger.warning("Node %s has no parent, adding root node as parent", node)
                    self._dh_graph.add_edge(self.get_root(), node, edge_type=EDGE_TYPE_INITIATOR)

    def transfer_initiator_g_to_action_space(self, url_type: str, root: str, initiator_g: nx.DiGraph,
                                             node_time: int = 0) -> list:
        """
        Take initiator information and transfer it to the action space
        Returns: list of nodes that could be added to the root
        """

        def _should_consider(curr_node: str) -> bool:
            if curr_node is None:
                return False

            if url_type == TYPE_ESLD:
                return curr_node is not None

            req_sld, _, _, req_path = get_variations_of_domains(curr_node)
            if url_type == TYPE_FQDN:
                return not self.contains(curr_node) and is_real_fqdn(curr_node, [req_sld])
            if url_type == TYPE_FQDN_PATH:
                return not self.contains(curr_node) and is_real_fqdn_with_path(req_path)

            return True

        root_children = []
        for n in initiator_g.nodes():
            if n != root:
                # should ignore it?
                if not _should_consider(n):
                    continue
                # else continue
                if not self.contains(n):
                    self.add_node(n, create_default_node_attributes(url_type, node_time,
                                                                    default_q_value=self.default_q_value))
                for parent in initiator_g.predecessors(n):
                    if not _should_consider(parent):
                        continue
                    if not self.contains(parent):
                        self.add_node(parent, create_default_node_attributes(url_type, node_time,
                                                                             default_q_value=self.default_q_value))
                    if parent == root:
                        root_children.append(n)
                    elif not self._dh_graph.has_edge(parent, n):
                        # can the child already reach the parent? We try to avoid cycles
                        try:
                            sp = nx.shortest_path(self._dh_graph, source=n, target=parent)
                            # logger.debug(
                            #    "Don't add new edge from parent %s to child %s to avoid cycles. Existing path:  %s",
                            #    parent, n, str(sp))
                        except nx.exception.NetworkXNoPath:
                            self._dh_graph.add_edge(parent, n, edge_type=EDGE_TYPE_INITIATOR)
            else:
                # add all children to root
                root_children += list(initiator_g.predecessors(n))

        return root_children

    def add_with_initiator_graph_esld(self, initiator_g: nx.DiGraph, node_time: int = 0):
        """
        Take nodes from initiator_g and add it into our action space for ESLD
        """
        root_url = self.get_root_url()
        root_sld, _, _, _ = get_variations_of_domains(root_url)
        if root_sld is None:
            raise RootMissingException(f"Root cannot be none: {root_url}")

        root_sld_children = self.transfer_initiator_g_to_action_space(TYPE_ESLD, root_sld, initiator_g,
                                                                      node_time=node_time)

        for n in set(root_sld_children):
            if self._dh_graph.nodes.get(n) is None:
                self.add_child_to_root(n, node_time=node_time)
            else:
                self._dh_graph.add_edge(self.get_root(), n, edge_type=EDGE_TYPE_INITIATOR)

        # don't forget to add the actual first party node to the virtual root
        if self._dh_graph.nodes.get(root_sld) is None:
            self.add_child_to_root(root_sld, node_time=node_time)
        else:
            # add edge from first party node to root
            self._dh_graph.add_edge(self.get_root(), root_sld, edge_type=EDGE_TYPE_INITIATOR)

    def add_with_initiator_graph_fqdn(self, initiator_g: nx.DiGraph, node_time: int = 0):
        """
        Take nodes from initiator_g and add it into our action space for FQDN
        """
        root_url = self.get_root_url()
        root_sld, _, _, _ = get_variations_of_domains(root_url)
        if root_sld is None:
            raise RootMissingException(f"Root cannot be none: {root_url}")

        self.transfer_initiator_g_to_action_space(TYPE_FQDN, root_sld, initiator_g,
                                                  node_time=node_time)

        # get all nodes that have no parents with type fqdn
        for node, node_data in self._dh_graph.nodes(data=True):
            if TYPE in node_data and node_data[TYPE] == TYPE_FQDN \
                    and len(list(self._dh_graph.predecessors(node))) == 0:
                sld, _, _, _ = get_variations_of_domains(node)
                if self.contains(sld):
                    self._dh_graph.add_edge(sld, node, edge_type=EDGE_TYPE_FINER_GRAIN)
                else:
                    raise ActionSpaceException(f"Missing SLD {sld} when adding FQDN node")

    def add_with_initiator_graph_fqdn_path(self, initiator_g: nx.DiGraph, node_time: int = 0):
        """
        Take nodes from initiator_g and add it into our action space for FQDN_PATH
        """
        root_url = self.get_root_url()
        root_sld, _, _, _ = get_variations_of_domains(root_url)
        if root_sld is None:
            raise RootMissingException(f"Root cannot be none: {root_url}")

        self.transfer_initiator_g_to_action_space(TYPE_FQDN_PATH, root_sld, initiator_g,
                                                  node_time=node_time)

        # get all nodes that have no parents with type fqdn_path
        for node, node_data in self._dh_graph.nodes(data=True):
            if TYPE in node_data and node_data[TYPE] == TYPE_FQDN_PATH \
                    and len(list(self._dh_graph.predecessors(node))) == 0:
                sld, fqdn, _, _ = get_variations_of_domains(node)
                if self.contains(fqdn):
                    self._dh_graph.add_edge(fqdn, node, edge_type=EDGE_TYPE_FINER_GRAIN)
                elif self.contains(sld):
                    self._dh_graph.add_edge(sld, node, edge_type=EDGE_TYPE_FINER_GRAIN)

    def get_successors_by_type(self, node: str, node_type: str = None) -> list:
        successors = []
        for s in self._dh_graph.successors(node):
            if node_type:
                if self._dh_graph.nodes.get(s)[TYPE] == node_type:
                    successors.append(s)
            else:
                successors.append(s)
        return successors

    def get_successors_by_edge_type(self, node: str, edge_type: str = None) -> list:
        successors = []
        for s in self._dh_graph.successors(node):
            if edge_type:
                if self._dh_graph.get_edge_data(node, s)[EDGE_TYPE] == edge_type:
                    successors.append(s)
            else:
                successors.append(s)
        return successors

    def get_number_of_nodes_by_type(self, node_type: str) -> int:
        count = 0
        for n in self._dh_graph.nodes():
            if self._dh_graph.nodes.get(n)[TYPE] == node_type:
                count += 1
        return count

    def get_number_of_edges_by_type(self, edge_type: str) -> int:
        count = 0
        for e in self._dh_graph.edges():
            if self._dh_graph.edges.get(e)[EDGE_TYPE] == edge_type:
                count += 1
        return count

    def get_arms_to_initialize(self, node_type: str = None) -> list:
        current_node_id = self._dh_graph.graph[ROOT_NODE_ID]

        arms = []
        for succ in self.get_successors_by_type(current_node_id, node_type):
            # ignore sleeping arms
            if not self._dh_graph.nodes[succ][SLEEPING_ARM] and not self._dh_graph.nodes[succ][UNKNOWN_ARM]:
                arms.append(succ)

        logger.info("Found %d arms to init", len(arms))
        return arms

    @staticmethod
    def build_graph_for_node(url_type: str, node: str, g: nx.DiGraph) -> nx.DiGraph:
        """
        Create a copy of a G with specific nodes that fall under a specific node
        For example, remove nodes from g until only nodes that fall under yahoo.com exist.
        """
        g_tmp = g.copy()
        nodes_to_remove = []

        clean_node = node.replace("www.", "")
        for tmp_node, tmp_node_data in g_tmp.nodes(data=True):
            if url_type in tmp_node_data:
                if tmp_node_data[url_type].replace("www.", "") != clean_node:
                    nodes_to_remove.append(tmp_node)

        for tmp_node_to_remove in set(nodes_to_remove):
            g_tmp = remove_node_and_connect(g_tmp, tmp_node_to_remove)

        return g_tmp

    def _add_fqdn_path_nodes(self, initiator_g_fqdn_path_list: List[nx.DiGraph], root_sld: str, node_time: int):
        # for finer grain nodes, we need to use a diff strategy.
        # Build a graph for all fqdn paths under a fqdn nodes
        fqdn_to_fqdn_path = dict()
        for g_fqdn_path in initiator_g_fqdn_path_list:
            for node, node_data in self._dh_graph.nodes(data=True):
                # SPECIAL CASE: get all nodes for TYPE_FQDN AND nodes that are ESLD but does not have children
                #               since ESLD nodes can attach to FQDN_PATH nodes
                if TYPE in node_data and \
                        (node_data[TYPE] == TYPE_FQDN or
                         (node_data[TYPE] == TYPE_ESLD and len(list(self._dh_graph.successors(node))) == 0)):
                    # build the first fqdn graph
                    g_fqdn_path_tmp = self.build_graph_for_node(TYPE_FQDN, node, g_fqdn_path)
                    if node not in fqdn_to_fqdn_path:
                        fqdn_to_fqdn_path[node] = g_fqdn_path_tmp
                    else:
                        # add to existing G
                        fqdn_to_fqdn_path[node], _ = transfer_initiator_g(fqdn_to_fqdn_path[node],
                                                                          TYPE_FQDN,
                                                                          root_sld,
                                                                          g_fqdn_path_tmp)

        for g in fqdn_to_fqdn_path.values():
            self.add_with_initiator_graph_fqdn_path(g, node_time=node_time + 1)

    def build_graph(self, url, perf_log_files: list,
                    outgoing_requests: list,
                    node_time: int = 0,
                    save_raw_initiator_chain: bool = True):
        """
        Main method to init the action space
        """

        def _add_fqdn_nodes():
            # for finer grain nodes, we need to use a diff strategy. Build a graph for all fqdns under a esld
            esld_to_fqdn_dict = dict()
            for g_fqdn in initiator_g_fqdn_list:
                for node, node_data in self._dh_graph.nodes(data=True):
                    if TYPE in node_data and node_data[TYPE] == TYPE_ESLD:
                        # build the first fqdn graph
                        g_fqdn_tmp = self.build_graph_for_node(TYPE_ESLD, node, g_fqdn)
                        if node not in esld_to_fqdn_dict:
                            esld_to_fqdn_dict[node] = g_fqdn_tmp
                        else:
                            # add to existing G
                            esld_to_fqdn_dict[node], _ = transfer_initiator_g(esld_to_fqdn_dict[node],
                                                                              TYPE_ESLD,
                                                                              root_sld,
                                                                              g_fqdn_tmp)

            for g in esld_to_fqdn_dict.values():
                self.add_with_initiator_graph_fqdn(g, node_time=node_time + 1)

        # build individual graphs
        self._dh_graph = nx.DiGraph()
        self.add_root(url)

        perf_log_files.sort()

        root_url = self.get_root_url()
        root_sld, _, _, _ = get_variations_of_domains(root_url)
        if root_sld is None:
            raise RootMissingException(f"Root cannot be none: {root_url}")

        initiator_g_raw_list = [get_initiator_chain_graph_raw(x, root_sld,
                                                              output_directory=self.output_directory,
                                                              save_raw_initiator_chain=save_raw_initiator_chain) for x
                                in perf_log_files]

        # build up graph with ESLD nodes (initiator chain information)
        initiator_g_esld_list = [get_initiator_chain_graph_esld(x, root_sld, g_raw_initiator_chain=g_raw,
                                                                save_raw_initiator_chain=save_raw_initiator_chain)
                                 for x, g_raw in zip(perf_log_files, initiator_g_raw_list)]
        for index, g in enumerate(initiator_g_esld_list, start=1):
            self.add_with_initiator_graph_esld(g, node_time=node_time + index)

        # connect orphan nodes to root
        self.check_for_no_parents()

        # add in fqdn nodes + initiator
        node_time += len(initiator_g_esld_list)
        initiator_g_fqdn_list = [get_initiator_chain_graph_fqdn(x, root_sld,
                                                                g_raw_initiator_chain=g_raw,
                                                                output_directory=self.output_directory,
                                                                save_raw_initiator_chain=save_raw_initiator_chain)
                                 for x, g_raw in zip(perf_log_files, initiator_g_raw_list)]

        _add_fqdn_nodes()

        # add in fqdn_path nodes + initiator
        node_time += len(initiator_g_fqdn_list)
        initiator_g_fqdn_path_list = [get_initiator_chain_graph_fqdn_path(x, root_sld, g_raw_initiator_chain=g_raw,
                                                                          save_raw_initiator_chain=save_raw_initiator_chain)
                                      for x, g_raw in zip(perf_log_files, initiator_g_raw_list)]

        self._add_fqdn_path_nodes(initiator_g_fqdn_path_list, root_sld, node_time)

        # keep a copy for resetting if possible
        self.copy_dh_graph = self.get_graph().copy()
        self.built_graph = True

