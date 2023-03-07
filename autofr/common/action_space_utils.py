import json
import logging
import typing
from typing import Tuple

import networkx as nx

from autofr.common.utils import should_skip_perf_url, is_request_js_extension, \
    get_variations_of_domains, get_unique_str, is_real_fqdn, is_real_fqdn_with_path

logger = logging.getLogger(__name__)

ROOT_NODE_ID = "root_node_id"
TYPE_ESLD = "sld"
TYPE_FQDN = "fqdn"
TYPE_FQDN_PATH = "fqdn_path"
TYPE_PATH_ONLY = "path"
FINER_GRAIN_SEQUENCE = [TYPE_ESLD, TYPE_FQDN, TYPE_FQDN_PATH, TYPE_PATH_ONLY]
TYPE_SUPER = "super"
EDGE_TYPE_VIRTUAL = "virtual"


def get_prev_finer_grain_type(finer_grain_type: str) -> typing.Optional[str]:
    if finer_grain_type in FINER_GRAIN_SEQUENCE:
        index = FINER_GRAIN_SEQUENCE.index(finer_grain_type)
        prev_index = index - 1
        if 0 <= prev_index < len(FINER_GRAIN_SEQUENCE):
            return FINER_GRAIN_SEQUENCE[prev_index]


def get_next_finer_grain_type(finer_grain_type: str) -> typing.Optional[str]:
    if finer_grain_type in FINER_GRAIN_SEQUENCE:
        index = FINER_GRAIN_SEQUENCE.index(finer_grain_type)
        next_index = index + 1
        if 0 <= next_index < len(FINER_GRAIN_SEQUENCE):
            return FINER_GRAIN_SEQUENCE[next_index]


def _get_parent_from_script_type(json_obj: typing.Any) -> list:
    _parent_url = None
    if "callFrames" in json_obj:
        for _frame in json_obj["callFrames"]:
            _parent_url = _frame["url"]
            if _parent_url:
                break
    if not _parent_url and "parent" in json_obj:
        _parent_url = _get_parent_from_script_type(json_obj["parent"])

    return _parent_url


def get_initiator_chain_log_entries(file_path: str) -> list:
    log_entries = []
    with open(file_path) as webrequests_file:
        for line in webrequests_file:
            try:
                line_json = json.loads(line.strip())
                message_json = json.loads(line_json["message"])
                if "Network.requestWillBeSent" == message_json["message"]["method"]:
                    if not should_skip_perf_url(message_json["message"]["params"]["documentURL"]):
                        log_entries.append(message_json["message"]["params"])
            except Exception as e:
                logger.warning("Could not parse json of perf log %s", str(e))

    log_entries = sorted(log_entries, key=lambda x: x["timestamp"])

    #logger.debug("Found %d log entries", len(log_entries))
    return log_entries


def get_initiator_chain_info(file_path: str) -> typing.Tuple[list, dict]:
    from autofr.common.selenium_utils import INITIATOR_KEY
    log_entries = get_initiator_chain_log_entries(file_path)

    request_ids_to_log_entry = dict()
    for entry in log_entries:
        request_ids_to_log_entry[entry["requestId"]] = entry

    urls = []
    url_to_parents = dict()
    # entries are sorted by time already, so keep a fake time counter
    time_counter = 1
    for entry in log_entries:
        # logger.debug(entry)
        if "request" in entry and "url" in entry["request"]:
            url = entry["request"]["url"]
            # logger.debug("parsing %s", url)

            if should_skip_perf_url(url):
                continue

            # skip non JS resources if there is an extension
            is_js_ext, has_ext = is_request_js_extension(url)
            if has_ext and not is_js_ext:
                continue

            if url not in urls:
                urls.append(url)

            if INITIATOR_KEY in entry:
                initiator_type = entry[INITIATOR_KEY]["type"]
                parent_url = None
                if initiator_type == "parser":
                    parent_url = entry[INITIATOR_KEY]["url"]

                if initiator_type == "script":
                    # look at call stack
                    if "stack" in entry[INITIATOR_KEY]:
                        stack = entry[INITIATOR_KEY]["stack"]
                        if "callFrames" in stack:
                            for frame in stack["callFrames"]:
                                parent_url = frame["url"]
                                if parent_url:
                                    break
                        if not parent_url and "parent" in stack:
                            # look into the parent
                            parent_url = _get_parent_from_script_type(stack["parent"])

                if not parent_url and "requestId" in entry[INITIATOR_KEY]:
                    # logger.debug("trying to find requestId from initiator %s", entry[INITIATOR_KEY]["requestId"])
                    request_id = entry[INITIATOR_KEY]["requestId"]
                    if request_id in request_ids_to_log_entry:
                        match_log_entry = request_ids_to_log_entry.get(request_id)
                        if "request" in match_log_entry:
                            parent_url = match_log_entry["request"]["url"]
                            # logger.debug("Found parent_url based on requestId: %s for %s", parent_url, url)

                if not parent_url and "documentURL" in entry:
                    parent_url = entry["documentURL"]

                if parent_url and (should_skip_perf_url(parent_url) or parent_url == url):
                    parent_url = None

                if parent_url:
                    if url not in url_to_parents:
                        url_to_parents[url] = []

                    found_parent = False
                    for d, t in url_to_parents[url]:
                        if d == parent_url:
                            found_parent = True
                            break
                    if not found_parent:
                        url_to_parents[url].append((parent_url, time_counter))
                        time_counter += 1

    return urls, url_to_parents


def get_initiator_chain_graph(file_path: str, root: str) -> nx.DiGraph:
    from autofr.common.selenium_utils import INITIATOR_KEY
    log_entries = get_initiator_chain_log_entries(file_path)

    request_ids_to_log_entry = dict()
    for entry in log_entries:
        request_ids_to_log_entry[entry["requestId"]] = entry

    g = nx.DiGraph()
    g.add_node(root, url=root, root=True)

    for entry in log_entries:
        # logger.debug(entry)
        if "request" in entry and "url" in entry["request"]:
            url = entry["request"]["url"]
            # logger.debug("parsing %s", url)

            if should_skip_perf_url(url):
                continue

            # skip non JS resources if there is an extension
            is_js_ext, has_ext = is_request_js_extension(url)
            if has_ext and not is_js_ext:
                continue

            sld, fqdn, fqdn_path, path = get_variations_of_domains(url)
            if sld is None:
                continue

            # add node
            if url not in g.nodes:
                g.add_node(url, url=url, sld=sld or "",
                           fqdn=fqdn or "", fqdn_path=fqdn_path or "",
                           path=path or "", is_main_site=(root == sld))

            if INITIATOR_KEY in entry:
                initiator_type = entry[INITIATOR_KEY]["type"]
                parent_url = None
                if initiator_type == "parser":
                    parent_url = entry[INITIATOR_KEY]["url"]

                if initiator_type == "script":
                    # look at call stack
                    if "stack" in entry[INITIATOR_KEY]:
                        stack = entry[INITIATOR_KEY]["stack"]
                        if "callFrames" in stack:
                            for frame in stack["callFrames"]:
                                parent_url = frame["url"]
                                if parent_url:
                                    break
                        if not parent_url and "parent" in stack:
                            # look into the parent
                            parent_url = _get_parent_from_script_type(stack["parent"])

                if not parent_url and "requestId" in entry[INITIATOR_KEY]:
                    # logger.debug("trying to find requestId from initiator %s", entry[INITIATOR_KEY]["requestId"])
                    request_id = entry[INITIATOR_KEY]["requestId"]
                    if request_id in request_ids_to_log_entry:
                        match_log_entry = request_ids_to_log_entry.get(request_id)
                        if "request" in match_log_entry:
                            parent_url = match_log_entry["request"]["url"]
                            # logger.debug("Found parent_url based on requestId: %s for %s", parent_url, url)

                if not parent_url and "documentURL" in entry:
                    parent_url = entry["documentURL"]
                    # logger.debug(f"got {parent_url} from documentUrl")

                if parent_url and (should_skip_perf_url(parent_url) or parent_url == url):
                    parent_url = None

                if parent_url:
                    added_parent_node = True
                    if parent_url not in g.nodes:
                        parent_sld, parent_fqdn, parent_fqdn_path, parent_fqdn_path_only = get_variations_of_domains(
                            parent_url)
                        if parent_sld:
                            g.add_node(parent_url, url=parent_url, sld=parent_sld or "",
                                       fqdn=parent_fqdn or "", fqdn_path=parent_fqdn_path or "",
                                       path=parent_fqdn_path_only or "",
                                       is_main_site=(root == parent_sld))
                        else:
                            added_parent_node = False
                    if added_parent_node:
                        g.add_edge(parent_url, url)
                else:
                    g.add_edge(root, url)

    # all nodes that do not have parents will have edge to root
    for node in g.nodes():
        predecessors = list(g.predecessors(node))
        if len(predecessors) == 0:
            if node != root:
                #logger.debug("Node %s has no parent, adding root node as parent", node)
                g.add_edge(root, node)

    return g


def get_initiator_chain_graph_raw(file_path: str, root: str,
                                  output_directory: str = None,
                                  save_raw_initiator_chain: bool = True) -> nx.DiGraph:
    """
    Creates digraph from file directly without changing anything
    """
    g = get_initiator_chain_graph(file_path, root)

    return g


def get_initiator_chain_graph_by_type(url_type: str,
                                      file_path: str,
                                      root: str,
                                      g_raw_initiator_chain: nx.DiGraph = None,
                                      output_directory: str = None,
                                      save_raw_initiator_chain: bool = True):
    """
    (1) g = Create a digraph based solely on initiator chain web requests
    (2) simple g = Remove all nodes that share the same url tyoe as main_url.
    (3) g no dups = For all paths p from S -> leaf, remove the leaf if any nodes u in p (u != leaf) have the same url_type.
                    For all current leaf nodes and repeat (3) until there are nothing left to remove.
    (4) g url type = Make the networkx based solely g no dups, where each node is url type level only
    (5) g url type clean = If a node has multiple incoming edges and one of them is the root, then remove all other edges from that node

    """
    file_unique_suffix = get_unique_str()
    if g_raw_initiator_chain is None:
        g = get_initiator_chain_graph_raw(file_path, root,
                                          output_directory=output_directory,
                                          save_raw_initiator_chain=save_raw_initiator_chain)
    else:
        # important to make a copy to not mess up the raw graph
        g = g_raw_initiator_chain.copy()

    # remove args.main_url nodes
    nodes_to_remove = []
    for n in g.nodes:
        if url_type in g.nodes[n] and g.nodes[n][url_type] == root:
            nodes_to_remove.append(n)

    for n in nodes_to_remove:
        g = remove_node_and_connect(g, n)

    #if output_directory and save_raw_initiator_chain:
    #    full_file_path = f"{output_directory}{os.sep}{root}_from_perf_log_simple_{url_type}_{file_unique_suffix}.graphml"
    #    if not os.path.isfile(full_file_path):
    #        nx.write_graphml(g, full_file_path)

    #logger.debug(f"Simple Graph stats {url_type} : nodes {g.number_of_nodes()}, edges {g.number_of_edges()}")

    # remove duplicate nodes. For example if path is
    # root -> a.com -> b.com -> a.com -> c.com , then we only keep the top most nodes
    # root -> a.com -> b.com -> c.com
    g_no_dups = g.copy()

    all_unique_nodes = False
    iteration = 0
    while not all_unique_nodes:
        # logger.debug("iteration %d", iteration)
        nodes_to_remove = []

        leaf_nodes = [x for x in g.nodes() if g.out_degree(x) == 0 and g.in_degree(x) >= 1]
        for path in nx.all_simple_paths(g, source=root, target=leaf_nodes):
            # we ignore the root and last node
            # if an earlier node has same url_type, then set the last_node for deletion
            if len(path) > 2:
                last_node = path[-1]
                last_node_url_type = g.nodes[last_node][url_type]
                for n in path[1:-1]:
                    # logger.debug("current n %s sld %s, looking for %s", n, g.nodes[n]["sld"], last_node)
                    if g.nodes[n][url_type] == last_node_url_type:
                        # logger.debug("MATCH: current n %s sld %s, looking for %s", n, g.nodes[n]["sld"], last_node)
                        nodes_to_remove.append(last_node)

        if len(nodes_to_remove) == 0:
            all_unique_nodes = True
        else:
            for n in set(nodes_to_remove):
                # remove n and connect edges
                # logger.debug("removing node %s", n)
                if n in g_no_dups.nodes:
                    g_no_dups = remove_node_and_connect(g_no_dups, n)

            # we don't care about reconnecting cause we are removing leaf nodes
            for leaf in leaf_nodes:
                g.remove_node(leaf)

            iteration += 1

    #if output_directory and save_raw_initiator_chain:
    #    full_file_path = f"{output_directory}{os.sep}{root}_from_perf_log_simple_no_dups_{url_type}__{file_unique_suffix}.graphml"
    #    if not os.path.isfile(full_file_path):
    #        nx.write_graphml(g_no_dups, full_file_path)

    #logger.debug(
    #    f"No DUPS: Simple Graph stats {url_type}: nodes {g_no_dups.number_of_nodes()}, edges {g_no_dups.number_of_edges()}")

    # make digraph based on url_type
    attrs = dict()
    attrs["label"] = root
    attrs[url_type] = root
    attrs["root"] = True
    g_specific_url_type = nx.DiGraph()
    g_specific_url_type.add_node(root, **attrs)
    for n, n_data in g_no_dups.nodes(data=True):
        if url_type in g_no_dups.nodes[n]:
            value = g_no_dups.nodes[n][url_type]
            if value not in g_specific_url_type.nodes:
                # logger.debug("adding node %s", sld)
                attrs = dict()
                attrs["label"] = value
                attrs[url_type] = value
                attrs.update(n_data)
                g_specific_url_type.add_node(value, **attrs)

            for parent_n in g_no_dups.predecessors(n):
                if url_type in g_no_dups.nodes[parent_n]:
                    parent_value = g_no_dups.nodes[parent_n][url_type]
                else:
                    parent_value = root
                if parent_value != root and parent_value not in g_specific_url_type.nodes:
                    parent_n_data = g_no_dups.nodes[parent_n]
                    attrs = dict()
                    attrs["label"] = parent_value
                    attrs[url_type] = parent_value
                    attrs.update(parent_n_data)
                    g_specific_url_type.add_node(parent_value, **attrs)
                if parent_value != value:
                    g_specific_url_type.add_edge(parent_value, value)

    #if output_directory and save_raw_initiator_chain:
    #    full_file_path = f"{output_directory}{os.sep}{root}_from_perf_log_{url_type}_{file_unique_suffix}.graphml"
    #    if not os.path.isfile(full_file_path):
    #        nx.write_graphml(g_specific_url_type, full_file_path)

    #logger.debug(
    #    f"Graph with {url_type}: nodes {g_specific_url_type.number_of_nodes()}, edges {g_specific_url_type.number_of_edges()}")

    edges_to_remove = []
    for n in g_specific_url_type.nodes():
        # if one of the edge's source is the root, remove the other edges
        edges = list(g_specific_url_type.in_edges(n))

        if len(edges) > 1:
            root_edge_found = False
            for source, target in edges:
                if source == root:
                    root_edge_found = True
                    break

            if root_edge_found:
                for source, target in edges:
                    if source != root:
                        edges_to_remove.append((source, target))

    #logger.debug(f"Edges to remove to clean g {url_type}: {len(edges_to_remove)}")

    for e in set(edges_to_remove):
        g_specific_url_type.remove_edge(*e)

    #if output_directory and save_raw_initiator_chain:
    #    full_file_path = f"{output_directory}{os.sep}{root}_from_perf_log_{url_type}_clean_{file_unique_suffix}.graphml"
    #    if not os.path.isfile(full_file_path):
    #        nx.write_graphml(g_specific_url_type, full_file_path)

    #logger.debug(
    #    f"Clean Graph with {url_type}: nodes {g_specific_url_type.number_of_nodes()}, edges {g_specific_url_type.number_of_edges()}")

    return g_specific_url_type


def get_initiator_chain_graph_esld(file_path: str, root: str,
                                   output_directory: str = None,
                                   g_raw_initiator_chain: nx.DiGraph = None,
                                   save_raw_initiator_chain: bool = True) -> nx.DiGraph:
    return get_initiator_chain_graph_by_type(TYPE_ESLD, file_path, root,
                                             g_raw_initiator_chain=g_raw_initiator_chain,
                                             output_directory=output_directory,
                                             save_raw_initiator_chain=save_raw_initiator_chain)


def get_initiator_chain_graph_fqdn(file_path: str, root: str,
                                   output_directory: str = None,
                                   g_raw_initiator_chain: nx.DiGraph = None,
                                   save_raw_initiator_chain: bool = True
                                   ) -> nx.DiGraph:
    return get_initiator_chain_graph_by_type(TYPE_FQDN, file_path, root,
                                             g_raw_initiator_chain=g_raw_initiator_chain,
                                             output_directory=output_directory,
                                             save_raw_initiator_chain=save_raw_initiator_chain
                                             )


def get_initiator_chain_graph_fqdn_path(file_path: str, root: str,
                                        output_directory: str = None,
                                        g_raw_initiator_chain: nx.DiGraph = None,
                                        save_raw_initiator_chain: bool = True) -> nx.DiGraph:
    return get_initiator_chain_graph_by_type(TYPE_FQDN_PATH, file_path, root,
                                             g_raw_initiator_chain=g_raw_initiator_chain,
                                             output_directory=output_directory,
                                             save_raw_initiator_chain=save_raw_initiator_chain)


def get_initiator_chain_graph_path_only(file_path: str, root: str,
                                        output_directory: str = None,
                                        g_raw_initiator_chain: nx.DiGraph = None,
                                        save_raw_initiator_chain: bool = True) -> nx.DiGraph:
    return get_initiator_chain_graph_by_type(TYPE_PATH_ONLY, file_path, root,
                                             g_raw_initiator_chain=g_raw_initiator_chain,
                                             output_directory=output_directory,
                                             save_raw_initiator_chain=save_raw_initiator_chain)


# https://stackoverflow.com/questions/58799219/how-to-preseve-the-path-when-edge-remved-networkx-graph
def remove_node_and_connect(g, node: str) -> nx.DiGraph:
    import itertools

    if g.is_directed():
        sources = [source for source, _ in g.in_edges(node)]
        targets = [target for _, target in g.out_edges(node)]
    else:
        sources = g.neighbors(node)
        targets = g.neighbors(node)

    new_edges = itertools.product(sources, targets)
    new_edges = [(source, target) for source, target in new_edges if source != target]  # remove self-loops
    g.add_edges_from(new_edges, edge_type=EDGE_TYPE_VIRTUAL)
    g.remove_node(node)

    return g


def transfer_initiator_g(curr_g: nx.DiGraph, url_type: str, root: str, initiator_g: nx.DiGraph, node_time: int = 0) \
        -> Tuple[nx.DiGraph, list]:
    """
    Take initiator information and transfer it to the graph
    Returns: curr_g, list of nodes that could be added to the root
    """

    def _should_consider(curr_node: str) -> bool:
        if curr_node is None:
            return False

        if url_type == TYPE_ESLD:
            return curr_node is not None
        try:
            req_sld, _, _, req_path = get_variations_of_domains(curr_node)
            if url_type == TYPE_FQDN:
                return curr_node not in curr_g.nodes and is_real_fqdn(curr_node, [req_sld])
            if url_type == TYPE_FQDN_PATH:
                return curr_node not in curr_g.nodes and is_real_fqdn_with_path(req_path)
        except Exception as e:
            logger.warning(f"could not get variations of node {curr_node}", str(e))
            raise e
        return True

    root_children = []
    for n, n_data in initiator_g.nodes(data=True):
        if n != root:
            # should ignore it?
            if not _should_consider(n):
                continue
            # else continue
            if n not in curr_g.nodes:
                curr_g.add_node(n, **n_data)

            for parent in initiator_g.predecessors(n):
                if not _should_consider(parent):
                    continue
                if parent not in curr_g.nodes:
                    curr_g.add_node(parent, **initiator_g.nodes.get(parent))

                if parent == root:
                    root_children.append(n)
                elif not curr_g.has_edge(parent, n):
                    # can the child already reach the parent? We try to avoid cycles
                    try:
                        sp = nx.shortest_path(curr_g, source=n, target=parent)
                        # logger.debug("Don't add new edge from parent %s to child %s to avoid cycles. Existing path:  %s", parent, n, str(sp))
                    except nx.exception.NetworkXNoPath:
                        curr_g.add_edge(parent, n)
        else:
            # add all children to root
            root_children += list(initiator_g.predecessors(n))

    return curr_g, root_children
