import collections
import glob
import json
import logging
import os.path
import shutil
import subprocess
import time
import typing

import networkx as nx
from tldextract import tldextract

from autofr.common.action_space_utils import ROOT_NODE_ID, TYPE_ESLD, TYPE_FQDN, TYPE_FQDN_PATH, \
    get_initiator_chain_log_entries
from autofr.common.docker_utils import DATA_DIR_NAME, DOCKER_OUTPUT_PATH, HOST_MACHINE_OUTPUT_PATH, \
    IS_INSIDE_DOCKER
from autofr.common.exceptions import MissingSnapshotException, BuildingSnapshotException, \
    MissingWebRequestFilesException, RootMissingException, SiteSnapshotException
from autofr.common.selenium_utils import CDP_CALLFRAMES, CDP_SCRIPTID, INITIATOR_KEY
from autofr.common.utils import get_variations_of_domains, get_largest_file_from_path, \
    get_file_from_path_by_key, TOPFRAME, JSON_WEBREQUEST_KEY
from autofr.rl.action_space import EDGE_TYPE

INIT_ADGRAPH = "init_adgraph"
ADGRAPH_NETWORKX = "adgraph_networkx"

TAG = "tag"
NODE_TYPE = "node_type"
INFO = "info"
REQUESTED_URL = "requested_url"
FLG_IMAGE = "flg-image"
FLG_TEXTNODE = "flg-textnode"
FLG_AD = "flg-ad"
FLG_IFRAME_ID = "flg-iframe-id"

SNAPSHOT_NODE__NODE = "NODE"
SNAPSHOT_NODE__URL = "URL"
SNAPSHOT_NODE__SCRIPT = "SCRIPT"
SNAPSHOT_NODE_ATTRIBUE__ID = "id"
# Note: these edge types must be in line with adgraphapi code (see folder)
SNAPSHOT_EDGE__DOM = "dom"
SNAPSHOT_EDGE__ACTOR = "actor"
SNAPSHOT_EDGE__REQUESTOR = "requestor"
SNAPSHOT_EDGE__ATTACHED_LATER = "attached_later"
SNAPSHOT_EDGE__NODE_TO_SCRIPT = "node_to_script"
SNAPSHOT_EDGE__VIRTUAL = "virtual"

# edge attribute to denote whether it agreed with callstack from initiator chain
CORRECT_EDGE = "correct_edge"

# from callstack
SNAPSHOT_EDGE__SCRIPT_USED_BY = "script_useed_by"

PARTIAL_VISIT = "partial_visit"
PART_IMPORTANT_PATH = "part_important_path"

IS_IN_MAIN_FRAME = "is_in_main_frame"

logger = logging.getLogger(__name__)


def get_adgraph_rendering_output_dir() -> str:
    """
    This is hardcoded from Adgraph: https://github.com/uiowa-irl/AdGraph#rendering-stream-representation
    """
    return os.path.expanduser("~") + os.sep + "rendering_stream"


def get_adgraphapi_dir() -> str:
    """
    This is where adgraphapi is located.
    Note that for running in docker, the working directory will be the home directory (/home/user),
    for outside of docker, it should be the directory of this project
    """
    if IS_INSIDE_DOCKER:
        return os.path.expanduser("~") + os.sep + "adgraphapi"
    return os.getcwd() + os.sep + "adgraphapi"


def get_adgraph_base_dir() -> str:
    """
    This is the base_dir of where the raw graphs need to go be parsed by adgraphapi
    """
    return get_adgraphapi_dir() + os.sep + "base_dir"


def get_adgraph_data_dir() -> str:
    return get_adgraph_base_dir() + os.sep + DATA_DIR_NAME


def get_adgraph_features_dir() -> str:
    return get_adgraph_base_dir() + os.sep + "features"


def get_adgraph_mapping_dir() -> str:
    return get_adgraph_base_dir() + os.sep + "mapping"


def clean_adgraph_rendering_dir():
    # clean up default dir
    for root, dirs, files in os.walk(get_adgraph_rendering_output_dir()):
        for f in files:
            os.unlink(os.path.join(root, f))
        for d in dirs:
            shutil.rmtree(os.path.join(root, d), ignore_errors=True)


def clean_adgraph_parsing_dir():
    # clean up parsing dir
    for root, dirs, files in os.walk(get_adgraph_base_dir()):
        for f in files:
            os.unlink(os.path.join(root, f))
        for d in dirs:
            shutil.rmtree(os.path.join(root, d), ignore_errors=True)

    # create necessary dirs
    os.makedirs(get_adgraph_data_dir())
    os.makedirs(get_adgraph_features_dir())
    os.makedirs(get_adgraph_mapping_dir())


def copy_adgraph_as_parsed_log(dir_name: str, file_path: str):
    output_dir = get_adgraph_data_dir() + os.sep + dir_name
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.basename(file_path)
    new_file_name = f"parsed_{base_name}"
    logger.info(f"copying file from {file_path} to {output_dir + os.sep + new_file_name}")
    shutil.copyfile(file_path, output_dir + os.sep + new_file_name)


def run_adgraphapi() -> subprocess.CompletedProcess:
    params = ["./adgraph-buildgraph",
              "base_dir" + os.sep,
              "data" + os.sep,
              "features" + os.sep,
              "mapping" + os.sep,
              "timing" + os.sep]
    process = subprocess.run(params,
                             stdout=subprocess.PIPE, universal_newlines=True, cwd=get_adgraphapi_dir())
    return process


def is_node_data_annotated(node_data: dict, node_data_key: str) -> bool:
    return node_data and node_data_key in node_data and node_data[node_data_key].lower() == "true"


def is_node_annotated(g: nx.DiGraph, node: str, node_data_key: str) -> bool:
    node_data = g.nodes.get(node)
    return is_node_data_annotated(node_data, node_data_key)


def is_frg_annotated(data: dict) -> bool:
    """
    Does data contain an frg annotate attribute?
    """
    return (is_node_data_annotated(data, FLG_AD)) or \
           (is_node_data_annotated(data, FLG_IMAGE)) or \
           (is_node_data_annotated(data, FLG_TEXTNODE))


def is_flg_image_node(g: nx.DiGraph, node: str) -> bool:
    return is_node_annotated(g, node, FLG_IMAGE)


def is_flg_textnode(g: nx.DiGraph, node: str) -> bool:
    return is_node_annotated(g, node, FLG_TEXTNODE)


def is_flg_ad_node(g: nx.DiGraph, node: str) -> bool:
    return is_node_annotated(g, node, FLG_AD)


def should_skip_node(node_str: str) -> bool:
    """
    Should we skip this node based on its value
    """
    return node_str.startswith("chrome://") or node_str.startswith("data") or \
           "new-tab" in node_str or "newtab" in node_str


def is_non_dom_edge(edge_data: typing.Any) -> bool:
    return EDGE_TYPE in edge_data and \
           (edge_data[EDGE_TYPE] != SNAPSHOT_EDGE__DOM and
            edge_data[EDGE_TYPE] != SNAPSHOT_EDGE__VIRTUAL)


def has_non_dom_predecessor_edges(g: nx.DiGraph, node_str: str,
                                  ignore_cycles: bool = True) -> bool:
    """
    Returns whether the node has parents that have edges other than type SNAPSHOT_EDGE__DOM and SNAPSHOT_EDGE__VIRTUAL
    Treat cycles differently using ignore_cycles
    """
    # predecessors = immediate parents of node_str
    for parent in g.predecessors(node_str):
        edge_data = g.get_edge_data(parent, node_str)
        if is_non_dom_edge(edge_data):
            if ignore_cycles:
                # if node can reach its parent, that means there is a cycle, ignore it
                if nx.has_path(g, node_str, parent):
                    continue
                else:
                    return True
            else:
                return True
    return False


def get_nodes_by_data_key(g: nx.DiGraph, node_key: str, node_value: typing.Any) -> list:
    """
    Given graph g, return nodes that have a certain node_key attribute with node_value
    """
    nodes = []
    for n, n_data in g.nodes(data=True):
        if node_key in n_data and n_data[node_key] == node_value:
            nodes.append(n)
    return nodes


def get_edges_by_data_key(g: nx.DiGraph, edge_key: str, edge_value: typing.Any) -> list:
    """
    Given a graph, return edges that have a certain edge_key attribute with edge_value
    """
    edges = []
    for u, v, e_data in g.edges(data=True):
        if edge_key in e_data and e_data[edge_key] == edge_value:
            edges.append((u, v))
    return edges


def get_url_counts_from_snapshot(snapshot: nx.DiGraph, first_party: str) -> dict:
    """
    Returns a dict of counts based on different URL variations
    """
    results = dict()
    for n, n_data in snapshot.nodes(data=True):
        if NODE_TYPE in n_data and n_data[NODE_TYPE] == SNAPSHOT_NODE__URL:
            url = n_data[INFO]
            if first_party in url:
                continue
            if len(url) > 0:
                sld, fqdn, fqdn_path, _, = get_variations_of_domains(url)
                if not sld:
                    continue
                has_parents = False
                for parent in snapshot.predecessors(n):
                    has_parents = True
                    parent_data = snapshot.nodes.get(parent)
                    parent_node_info = ""
                    if NODE_TYPE in parent_data:
                        parent_node_info = parent_data[NODE_TYPE]
                    # add key counters based on url variation and the parent node type
                    for url_variation in [url]:
                        if url_variation:
                            key = parent_node_info + url_variation
                            if key not in results:
                                results[key] = 0
                            results[key] += 1

                # else just add the key based on url variation
                if not has_parents:
                    for url_variation in [url]:
                        if url_variation:
                            key = url_variation
                            if key not in results:
                                results[key] = 0
                            results[key] += 1

    return results


def get_simple_path_data_from_snapshots(snapshot: nx.DiGraph, first_party: str) -> dict:
    """
    Returns a dict of keys based on simple paths to FRG nodes
    """
    results = dict()

    # get all FRG nodes
    frg_nodes_to_type = dict()
    root = None
    for n, n_data in snapshot.nodes(data=True):
        if n_data["id"] == "root":
            root = n
        for frg_type in [FLG_AD, FLG_IMAGE, FLG_TEXTNODE]:
            if frg_type in n_data and n_data[frg_type] == "true":
                frg_nodes_to_type[n] = frg_type

    if root is None:
        raise RootMissingException(f"Root cannot be None {first_party}")

    # get all simple paths from root to FRG nodes
    for path in nx.all_simple_paths(snapshot, source=root, target=list(frg_nodes_to_type.keys())):
        key = ""
        for node_tmp in path:
            n_data = snapshot.nodes.get(node_tmp)
            frg_type = frg_nodes_to_type.get(node_tmp, "")
            key += frg_type
            if REQUESTED_URL in n_data and len(n_data[REQUESTED_URL]) > 0:
                key += n_data[REQUESTED_URL]
            if INFO in n_data and len(n_data[INFO]) > 0:
                key += n_data[INFO]
        if key not in results:
            results[key] = 0
        results[key] += 1

    return results


def get_simple_path_data_from_snapshots_all(snapshot: nx.DiGraph, first_party: str, max_time_sec: int = 0) -> dict:
    """
    Returns a dict of keys based on simple paths to all URL nodes
    """
    results = dict()
    time_start = time.time()

    # get all FRG nodes
    url_nodes_to_type = dict()
    root = None
    for n, n_data in snapshot.nodes(data=True):
        if n_data["id"] == "root":
            root = n
        if NODE_TYPE in n_data and n_data[NODE_TYPE] == SNAPSHOT_NODE__URL \
                and n not in url_nodes_to_type:
            url_nodes_to_type[n] = 1

    if root is None:
        raise RootMissingException(f"Root cannot be None {first_party}")

    url_to_fqdn = dict()
    # get all simple paths from root to FRG nodes
    key_count = 0
    for path in nx.all_simple_paths(snapshot, source=root, target=list(url_nodes_to_type.keys())):
        key = ""
        for node_tmp in path:
            n_data = snapshot.nodes.get(node_tmp)
            # when we get to the http info, keep the fqdn_path version only
            if INFO in n_data and len(n_data[INFO]) > 0:
                if "http" in n_data[INFO]:
                    fqdn = url_to_fqdn.get(n_data[INFO])
                    if not fqdn:
                        _, fqdn, _, _ = get_variations_of_domains(n_data[INFO])
                        url_to_fqdn[n_data[INFO]] = fqdn
                    key += fqdn
                else:
                    key += n_data[INFO]

        # logger.debug(f"get_simple_path_data_from_snapshots_all: Found key: {key}")
        if key not in results:
            results[key] = 1
            key_count += 1

        if key_count % 10 == 0 and 0 < max_time_sec < int(time.time() - time_start):
            logger.warning(f"Time exceeded {max_time_sec}")
            return None

    return results


def get_main_raw_adgraph_file_path(input_directory: str, url: str) -> typing.Optional[str]:
    """
    The main raw adgraph will be in a directory with the sld in the name and it the largest file without the TOPFRAME name
    """
    # logger.info(f"finding main raw adgraph from {input_directory} for {url}")
    main_file_path = None
    sld, _, _, _ = get_variations_of_domains(url)
    for dir in os.listdir(input_directory):
        if os.path.isdir(input_directory + os.sep + dir):
            if sld and sld not in dir:
                logger.debug(f"Possible adgraph subdirectory that we did not expect {input_directory + os.sep + dir}")
                continue

            adgraph_dir_with_sld = input_directory + os.sep + dir

            main_file_path = get_largest_file_from_path(adgraph_dir_with_sld, "log*" + sld + "*.json",
                                                        ignore=[TOPFRAME])
            if main_file_path:
                break

    # try last chance with input_directory
    if not main_file_path:
        main_file_path = get_largest_file_from_path(input_directory, "log*" + sld + "*.json",
                                                    ignore=[TOPFRAME])

    if not main_file_path:
        logger.warning(f"Could not find main raw adgraph for {input_directory}")

    return main_file_path


def convert_adgrahph_to_site_snapshot(adgraph_json_file_path: str, main_url: str, output_directory: str) \
        -> typing.Tuple[nx.DiGraph, str]:
    """
    Converts the JSON parsed file into networkx digraph. Outputs as graphml file as well.
    Input MUST have already been parsed by adgraph-buildgraph
    """

    def _is_adgraph_root_node(node: dict) -> bool:
        return node[NODE_TYPE] == "NODE" \
               and INFO in node \
               and (node[INFO] == "UNAVAILABLE" or node[INFO] == "HTML")

    g = nx.DiGraph()
    root = main_url
    root_key = f"{root}_ROOT"
    g.graph[ROOT_NODE_ID] = root_key
    # add the root
    g.add_node(root_key, root="true", id="root")

    nodes_to_remove = []
    # find root node to link virtual root later
    adgraph_root_nodes = []
    with open(adgraph_json_file_path) as adgraph_file:
        adgraph_JSON = json.load(adgraph_file)

        nodes_with_types = []
        for node in adgraph_JSON["nodes"]:
            node[NODE_TYPE] = node["id"].split("_")[0]
            if node[NODE_TYPE] in [SNAPSHOT_NODE__URL, SNAPSHOT_NODE__SCRIPT]:
                tld_result = tldextract.extract(node["info"])
                node["sld"] = tld_result.domain + "." + tld_result.suffix
                node["is_main_site"] = root == node["sld"]
                node["root"] = "false"
                # remove data only
                if should_skip_node(node["info"]):
                    nodes_to_remove.append(node["id"])
            else:
                if _is_adgraph_root_node(node):
                    adgraph_root_nodes.append((node["id"], int(node["id"].split("_")[1])))
                elif not is_frg_annotated(node):
                    nodes_to_remove.append(node["id"])

            nodes_with_types.append(node)

        nodes = [(x["id"], x) for x in nodes_with_types]
        g.add_nodes_from(nodes)

        for edge_data in adgraph_JSON["links"]:
            g.add_edge(edge_data["source"], edge_data["target"], edge_type=edge_data["edge_type"])

        #logger.debug("Built new graph from adgraph data: nodes %d, edges %d",
        #             g.number_of_nodes(),
        #             g.number_of_edges())

    # add edge from root_key to adgraph_root_node
    adgraph_root_node, adgraph_root_node_index = min(adgraph_root_nodes, key=lambda x: x[1])
    if adgraph_root_node:
        g.add_edge(root_key, adgraph_root_node, edge_type=SNAPSHOT_EDGE__VIRTUAL)
        # then label it as to remove
        nodes_to_remove.append(adgraph_root_node)
    else:
        logger.warning(f"Did not find adgraph root node")

    # add all nodes with no parent to the root
    for node, node_data in g.nodes(data=True):
        predecessors = list(g.predecessors(node))
        if len(predecessors) == 0:
            if node != root_key:
                g.add_edge(root_key, node, edge_type=SNAPSHOT_EDGE__VIRTUAL)

    base_name_no_ext = os.path.basename(adgraph_json_file_path)[:-len(".json")] + ".graphml"
    os.makedirs(output_directory, exist_ok=True)
    nx.write_graphml(g, output_directory + os.sep + base_name_no_ext)
    logger.info(f"Copying processed site snapshot from {adgraph_json_file_path} to {output_directory}")
    shutil.copy2(adgraph_json_file_path, output_directory)
    return g, base_name_no_ext


def has_path_to_ads_without_script_used_by_edge(script_node_id: str,
                                                node_to_ads_cache: dict,
                                                snapshot: nx.DiGraph,
                                                max_check_paths_threshold: int = 10) -> bool:
    """
    Experimental
    """
    # if the script_node already has a path to an ad without any SNAPSHOT_EDGE__SCRIPT_USED_BY, return True
    if script_node_id in node_to_ads_cache:
        return node_to_ads_cache[script_node_id]
    for node, node_data in snapshot.nodes(data=True):
        if FLG_AD in node_data and node_data[FLG_AD] == "true":
            path_check_count = 0
            for path in nx.all_simple_paths(snapshot, script_node_id, node):
                path_edges = nx.utils.pairwise(path)
                found_script_used_by = False
                for src_node, target_node in path_edges:
                    if snapshot.get_edge_data(src_node, target_node)[EDGE_TYPE] == SNAPSHOT_EDGE__SCRIPT_USED_BY:
                        found_script_used_by = True
                if not found_script_used_by:
                    return True
                path_check_count += 1
                if path_check_count > max_check_paths_threshold:
                    #logger.debug(f"Too many paths to check: stop checking between {script_node_id} and {node}")
                    break

    return False

class SiteSnapshot:
    # example key made from AdGraph based on time: 1655747065.993929
    SNAPSHOT_UNIQUE_KEY_LEN = 17
    SNAPSHOT_DIRECTORY_PARTIAL = "AdGraph_Snapshots"
    # must have parity with adgraph timeline.cc
    FRAMEOWNER = "frameowner"
    FRAMEOWNER_ID = "frame_owner_id"

    def __init__(self,
                 url: str,
                 adgraph_raw_file_path: str = None,
                 snapshot_nx_file_path: str = None,
                 snapshot_name: str = "",
                 base_name: str = "",
                 output_directory: str = "",
                 site_snapshot_dir_name: str = ADGRAPH_NETWORKX):
        self.url = url
        # raw file that has not been processed
        self.adgraph_raw_file_path = adgraph_raw_file_path
        # snapshot file that has been processed already
        self.snapshot_nx_file_path = snapshot_nx_file_path
        self.base_name = base_name
        self.site_snapshot_dir_name = site_snapshot_dir_name
        self.snapshot_name = snapshot_name
        # this is only used to output the site snapshot if we need to convert from raw adgraph to site snapshot
        # if snapshot_nx_file_path is given, then we basically ignore output_directory
        self.output_directory = output_directory

        # cache whether a node has a path to a ad node where the path has no SCRIPT_USED_BY edge
        self.node_to_ads_cache = dict()

        if adgraph_raw_file_path is None and snapshot_nx_file_path is None:
            raise MissingSnapshotException(f"Raw file and snapshot file cannot both be None")

        self._snapshot: nx.DiGraph = None
        # read in snapshot if available
        self._read_snapshot()
        # or process the raw file into a snapshot file
        self._convert_into_snapshot_file()
        # infuse callstack into snapshot
        self._infuse_call_stack_to_snapshot()

    def _read_snapshot(self):
        # read in snapshot file
        if self.snapshot_nx_file_path:
            self._snapshot = nx.read_graphml(self.snapshot_nx_file_path)
            if not self.snapshot_name:
                self.snapshot_name = os.path.basename(self.snapshot_nx_file_path)

    def _convert_into_snapshot_file(self):
        if self._snapshot is None and self.adgraph_raw_file_path:

            # get name based on file name but remove extension
            self.snapshot_name = os.path.basename(self.adgraph_raw_file_path)[:-len(".json")]

            # first stitch together multiple raw files for one given site
            input_dir = os.path.dirname(self.adgraph_raw_file_path)
            stitched_adgraph_file = self.stitch_adgraphs(input_dir, self.url)

            if not os.path.isfile(stitched_adgraph_file):
                raise MissingSnapshotException(f"Could not find stitched file {stitched_adgraph_file}")

            # copy the stitched file to adgraphapi to be processed
            clean_adgraph_parsing_dir()
            # copy files to data dir ready to be processed
            dir_name = f"snapshot_{self.snapshot_name}"
            copy_adgraph_as_parsed_log(dir_name, stitched_adgraph_file)

            # delete the stitched file, no longer need it
            os.remove(stitched_adgraph_file)

            # run adgraphpi
            p = run_adgraphapi()
            if p.returncode == 0:
                parsed_file_path = get_adgraph_mapping_dir() + os.sep + dir_name + ".json"
                adgraph_nx_g, g_name = convert_adgrahph_to_site_snapshot(parsed_file_path,
                                                                         self.url,
                                                                         self.get_base_site_snapshots_dir())
                self._snapshot = adgraph_nx_g
                if not self.snapshot_name:
                    self.snapshot_name = g_name
            else:
                raise BuildingSnapshotException(
                    f"Could not convert adgraph file {self.adgraph_raw_file_path} into a SiteSnapshot")

    def _find_individual_init_adgraph_dir(self) -> typing.Optional[str]:
        """
        TODO: rewrite this or just make the caller pass in the necessary directory
        Brittle code to find init_adgraph_dir. Each site snapshot is held in an individual folder for INIT_ADGRAPH.
        Find the directory based on the given self.adgraph_raw_file_path or self.snapshot_nx_file_path
        """
        init_adgraph_dir = None
        if self.adgraph_raw_file_path:
            # we don't need to do more work like from snapshots because the raw adgraph file lies within the init dir that we want already
            init_adgraph_dir = self.adgraph_raw_file_path
        elif self.snapshot_nx_file_path:
            # identify path until we found the top-level SiteSnapshot.SNAPSHOT_DIRECTORY_PARTIAL
            top_level_dir = self.snapshot_nx_file_path
            while SiteSnapshot.SNAPSHOT_DIRECTORY_PARTIAL not in os.path.basename(top_level_dir):
                top_level_dir = os.path.dirname(top_level_dir)
            path_split = os.path.basename(self.snapshot_nx_file_path).split("_")

            # find the snapshot_unique_key
            snapshot_unique_key = None
            for path in reversed(path_split):
                path_clean = path.replace(".graphml", "")
                if len(path_clean) == SiteSnapshot.SNAPSHOT_UNIQUE_KEY_LEN:
                    snapshot_unique_key = path_clean
                    break

            if not snapshot_unique_key:
                raise MissingSnapshotException(
                    f"Expected key length to be {SiteSnapshot.SNAPSHOT_UNIQUE_KEY_LEN} from path {path_split}")

            # use it to get where the raw adgraph file is location is
            adgraph_raw_file_paths = glob.glob(top_level_dir + os.sep + "**" + os.sep + f"*{snapshot_unique_key}*.json",
                                               recursive=True)

            # if we find multiple, just find at least one file with INIT_ADGRAPH
            if len(adgraph_raw_file_paths) > 0:
                for f in adgraph_raw_file_paths:
                    if INIT_ADGRAPH in f:
                        init_adgraph_dir = f
                        break

        if init_adgraph_dir:
            # keep looping until we find the directory with INIT_ADGRAPH as the os.path.basename
            while os.path.basename(init_adgraph_dir) and INIT_ADGRAPH not in os.path.basename(init_adgraph_dir):
                init_adgraph_dir = os.path.dirname(init_adgraph_dir)

            #logger.debug(f"Found {init_adgraph_dir} from {self.snapshot_nx_file_path} or {self.adgraph_raw_file_path}")
            return init_adgraph_dir

    def _find_callstack_files(self) -> typing.Optional[list]:
        """
        Brittle code to find callstack files within the AdGraph_Snapshots directory
        """
        init_adgraph_dir = self._find_individual_init_adgraph_dir()
        if init_adgraph_dir:
            # now we can find the callstack files (which are webrequests files)
            callstack_files = glob.glob(init_adgraph_dir + os.sep + "**" + os.sep + f"*{JSON_WEBREQUEST_KEY}.json",
                                        recursive=True)
            return callstack_files

    def _infuse_callstack_entry_to_snapshot(self, entry: dict, url_to_script_nodes: dict) -> int:
        """
        Entry is given from chrome https://chromedevtools.github.io/devtools-protocol/tot/Network/#event-requestWillBeSent
        """

        def _try_to_fix_edge(stack: dict, orig_script_node: str) -> int:
            fix_edge_count = 0
            try:
                if CDP_CALLFRAMES in stack and len(stack[CDP_CALLFRAMES]) > 0:
                    frame = stack[CDP_CALLFRAMES][0]
                    curr_script_node = None
                    script_id = frame[CDP_SCRIPTID]
                    node_key = f"{SNAPSHOT_NODE__SCRIPT}_{script_id}"
                    if self._snapshot.nodes.get(node_key):
                        curr_script_node = node_key
                        # check if actor is correct
                        # NOTE: We take the opportunity to also fix wrong edges that were retrieved from adgraph
                        if orig_script_node:
                            should_disconnect = False
                            for p in self._snapshot.predecessors(orig_script_node):
                                edge_data = self._snapshot.get_edge_data(p, orig_script_node)
                                if "edge_type" in edge_data and edge_data["edge_type"] == SNAPSHOT_EDGE__ACTOR:
                                    if p != curr_script_node:
                                        should_disconnect = True
                                        break

                            if should_disconnect:
                                # remove all incoming edges to orig_script_node
                                for p in list(self._snapshot.predecessors(orig_script_node)):
                                    self._snapshot.remove_edge(p, orig_script_node)
                                # reconnect orig_script_node to curr_script_node
                                #logger.debug(f"(v1) Updating edge to be {curr_script_node} to {orig_script_node}")
                                self._snapshot.add_edge(curr_script_node, orig_script_node,
                                                        edge_type=SNAPSHOT_EDGE__ACTOR)
                                fix_edge_count += 1
            except KeyError as e:
                logger.debug(f"(v1) Could not attempt to fix edges {str(e)}")

            return fix_edge_count

        def _parse_stack(stack: dict):
            # print("\nStarting new _parse_stack")
            if CDP_CALLFRAMES in stack:
                stack_history = []
                curr_script_node = None
                # replay the stack, so we gotta reverse it
                for frame in reversed(stack[CDP_CALLFRAMES]):
                    try:
                        script_id = frame[CDP_SCRIPTID]
                        script_url = frame["url"]
                        script_url_node = url_to_script_nodes.get(script_url)
                        # skip inline nodes
                        if not script_url_node:
                            continue

                        node_key = f"{SNAPSHOT_NODE__SCRIPT}_{script_id}"
                        if node_key == curr_script_node:
                            continue

                        if self._snapshot.nodes.get(node_key):
                            if not curr_script_node:
                                curr_script_node = node_key
                                stack_history.append(script_url)
                            elif node_key != curr_script_node:
                                # if len(stack_history) > 1:
                                # print(f"{script_url} and top of stack {stack_history[-2]}")

                                # only set new edge if this is a new use and not a return
                                if len(stack_history) == 1 or script_url != stack_history[-2]:
                                    stack_history.append(script_url)
                                    # add edge from curr_script_node to node_key
                                    if not self._snapshot.has_edge(node_key, curr_script_node):
                                        #logger.debug(f"Add edge from {node_key} to {curr_script_node}")
                                        self._snapshot.add_edge(node_key, curr_script_node,
                                                                edge_type=SNAPSHOT_EDGE__SCRIPT_USED_BY)
                                        # TODO: explore has_path_to_ads
                                        # has_path_to_ads_result = has_path_to_ads(node_key, self.node_to_ads_cache, self._snapshot)
                                        # self.node_to_ads_cache[script_id] = has_path_to_ads_result
                                        # if not has_path_to_ads_result:
                                        #    self._snapshot.add_edge(node_key, curr_script_node,
                                        #                            edge_type=SNAPSHOT_EDGE__SCRIPT_USED_BY)
                                        # else:
                                        #    logger.debug(f"skip adding {SNAPSHOT_EDGE__SCRIPT_USED_BY} for {node_key} cause has path to ads")
                                else:
                                    # pop from the end
                                    if len(stack_history) > 0:
                                        tmp_script_url = stack_history.pop()
                                        # print(f"Popping stack {tmp_script_url}")

                                curr_script_node = node_key
                    except KeyError as e:
                        logger.debug(f"Could not find scriptId in frame {frame}, {str(e)}")

            if "parent" in stack:
                _parse_stack(stack["parent"])

        total_fix_edges = 0
        if INITIATOR_KEY in entry:
            initiator_type = entry[INITIATOR_KEY]["type"]

            if initiator_type == "script":
                # get url of entry
                url = entry["request"]["url"]
                orig_script_node = url_to_script_nodes.get(url)
                # look at call stack
                if "stack" in entry[INITIATOR_KEY]:
                    _parse_stack(entry[INITIATOR_KEY]["stack"])
                    total_fix_edges += _try_to_fix_edge(entry[INITIATOR_KEY]["stack"], orig_script_node)
        return total_fix_edges

    def _get_script_url_to_url_node(self) -> dict:
        """
        AdGraph has SCRIPT (actor) -> URL NODE -> New Script
        and possible NODE (requestor) -> URL NODE -> New Script
        Returns dict of url of scripts -> url_node that caused the New Script
        Right now we don't deal with inline scripts with no URL
        """
        url_to_script_node = dict()
        if self._snapshot:
            for n, n_data in self._snapshot.nodes(data=True):
                if NODE_TYPE in n_data and n_data[NODE_TYPE] == SNAPSHOT_NODE__SCRIPT:
                    for p in self._snapshot.predecessors(n):
                        edge_data = self._snapshot.get_edge_data(p, n)
                        if EDGE_TYPE in edge_data and edge_data[EDGE_TYPE] == SNAPSHOT_EDGE__NODE_TO_SCRIPT:
                            p_data = self._snapshot.nodes.get(p)
                            if INFO in p_data and "http" in p_data[INFO]:
                                url_to_script_node[p_data[INFO]] = p
                                break

        return url_to_script_node

    def _infuse_call_stack_to_snapshot(self):
        """
        First search for the callstack file, then use it to add to the snapshot
        Callstack files are json files retrieved from Chrome https://chromedevtools.github.io/devtools-protocol/tot/Network/#event-requestWillBeSent
        """
        if self._snapshot:
            #logger.debug(f"_infuse_call_stack_to_snapshot")
            callstack_files = self._find_callstack_files()
            #logger.debug(
            #    f"Found callstack files {callstack_files} from self.snapshot_nx_file_path {self.snapshot_nx_file_path} or self.adgraph_raw_file_path {self.adgraph_raw_file_path}")
            if callstack_files:
                url_to_script_nodes = self._get_script_url_to_url_node()
                for f in callstack_files:
                    total_fixed_edges = 0
                    callstack_entries = get_initiator_chain_log_entries(f)
                    for entry in callstack_entries:
                        total_fixed_edges += self._infuse_callstack_entry_to_snapshot(entry, url_to_script_nodes)
                    #logger.debug(f"Fixed total {total_fixed_edges} from JS Callstack {f}")
            else:
                raise MissingWebRequestFilesException(f"Could not infuse callstack information {self.snapshot_name}")

    def get_graph(self) -> nx.DiGraph:
        return self._snapshot

    def remove_edge_types(self, edge_type: str) -> int:
        """
        Helper method to remove edge types
        Returns number of edges removed
        """
        edges_to_remove = []
        for u, v, edge_data in self.get_graph().edges.data():
            if EDGE_TYPE in edge_data and edge_data[EDGE_TYPE] == edge_type:
                edges_to_remove.append((u, v))
        for u, v in edges_to_remove:
            self.get_graph().remove_edge(u, v)

        return len(edges_to_remove)

    def get_base_site_snapshots_dir(self) -> str:
        return self.get_base_data_dir() + os.sep + self.site_snapshot_dir_name

    def get_base_data_dir(self) -> str:
        if self.output_directory:
            if self.base_name not in self.output_directory:
                return self.output_directory + os.sep + self.base_name
            return self.output_directory

        if IS_INSIDE_DOCKER:
            return DOCKER_OUTPUT_PATH + os.sep + self.base_name
        return HOST_MACHINE_OUTPUT_PATH + os.sep + self.base_name

    def stitch_adgraphs(self, input_directory: str, site_url: str) -> str:
        """
        Since each iframe will be outputted as its own adgraph JSON file, we need to stitch together
        all raw adgraphs in rendering_stream by using the frameowner of each JSON file to map with node ids in the main JSON.
        input_directory: is already the directory that holds all raw adgraph files for a given site
        Returns: the file path of the new stitched together adgraph file
        """

        def _get_first_html_node_id(json_obj) -> int:
            main_node_id = -1
            for event in json_obj["timeline"]:
                if "tag_name" in event and event["tag_name"].lower() == "html":
                    if "node_id" in event:
                        main_node_id = int(event["node_id"])
                        break
            return main_node_id

        def _should_stitch(main_json, other_json, double_check_main_node_id: int = -1) -> bool:
            main_url = main_json["url"]
            other_url = other_json["url"]
            if main_url != other_url:
                return True

            main_node_id = _get_first_html_node_id(main_json)
            other_node_id = _get_first_html_node_id(other_json)

            if double_check_main_node_id != -1 and main_node_id != double_check_main_node_id:
                raise SiteSnapshotException(
                    f"Could not stitch adgraphs, first HTML node id is wrong. Expected {double_check_main_node_id} vs. Got {main_node_id}")

            # don't stitch if the doc URLs are the same and the node_ids overlap. This is due to a bug
            #logger.info(f"Should stitch: {main_node_id} vs. {other_node_id}")
            return main_node_id < other_node_id

        def _get_iframe_node_id(timeline_event: typing.Any) \
                -> typing.Optional[str]:

            if "event_type" in timeline_event and timeline_event["event_type"] == "NodeInsertion":
                if "tag_name" in timeline_event and timeline_event["tag_name"].lower() == "iframe":
                    node_id = timeline_event["node_id"]
                    return node_id

            return None

        def _event_has_ad(timeline_event: typing.Any) -> bool:
            """ Example:
                "node_id": "20979",
                "actor_id": "0",
                "node_type": 1,
                "tag_name": "DIV",
                "event_type": "NodeInsertion",
                "node_parent_id": "20978",
                "node_previous_sibling_id": "0",
                "parent_node_type": 11,
                "node_attributes": [
                    {
                    "event_type": "NodeAttribute",
                    "attr_name": "class",
                    "attr_value": "CITP_adBlockerCover ByURL CITP_isAnAd"
                    },
                ]
            """
            if "event_type" in timeline_event and timeline_event["event_type"] == "NodeInsertion":
                if "node_attributes" in timeline_event and len(timeline_event["node_attributes"]) > 0:
                    for node_attr in timeline_event["node_attributes"]:
                        if node_attr["attr_name"] == "class" and "CITP_isAnAd" in node_attr["attr_value"]:
                            return True

            return False

        def _create_annotate_flg_ad_event(_node_id: str, _actor_id: str = "0") -> dict:
            """
                {
                "actor_id": "107",
                "node_id": "18380",
                "node_attribute": {
                    "event_type": "NodeAttribute",
                    "attr_name": "flg-ad",
                    "attr_value": "true"
                },
                "event_type": "AttrAddition"
                },
            """
            _event = dict()
            _event["actor_id"] = _actor_id
            _event["node_id"] = _node_id
            _event["event_type"] = "AttrAddition"
            _event["node_attribute"] = dict()
            _event["node_attribute"]["event_type"] = "NodeAttribute"
            _event["node_attribute"]["attr_name"] = FLG_AD
            _event["node_attribute"]["attr_value"] = "true"
            return _event

        # logger.debug(f"Finding largest raw adgraph file from {input_directory}")
        main_file_path = get_main_raw_adgraph_file_path(input_directory, site_url)

        if main_file_path is None:
            raise MissingSnapshotException(f"A main raw file needs to be found in {input_directory}")

        #logger.debug(f"Found main_file_path {main_file_path}")

        main_file_html_node_id = -1
        with open(main_file_path, "r") as f:
            main_file_json = json.load(f)
            if IS_IN_MAIN_FRAME in main_file_json and main_file_json[IS_IN_MAIN_FRAME] != True:
                raise SiteSnapshotException(
                    f"Did not find correct main file json {main_file_path} , is in main frame: {main_file_json[IS_IN_MAIN_FRAME]}")
            main_file_html_node_id = _get_first_html_node_id(main_file_json)
            if self.FRAMEOWNER_ID not in main_file_json:
                logger.debug(f"{self.FRAMEOWNER_ID} keyword not there, using old stitching strategy")
                return self.stitch_adgraphs_old(input_directory, site_url)

        # keep hierarchy of iframe nodes
        iframe_node_g = nx.DiGraph()

        flg_iframe_ids = set()
        flg_iframe_id_queue = collections.deque()
        for event in main_file_json["timeline"]:
            node_id = _get_iframe_node_id(event)
            if node_id is not None and node_id not in flg_iframe_ids:
                #logger.debug(f"found flg-frame-id to parse  {node_id}")
                flg_iframe_id_queue.append(node_id)
                flg_iframe_ids.add(node_id)
                iframe_node_g.add_node(node_id)

        #logger.info(f"Iframes found in main JSON: {flg_iframe_ids}")

        # find the file that matches each flg_iframe_id
        ad_nodes = []
        while  flg_iframe_id_queue:
            node_id_curr = flg_iframe_id_queue.popleft()

            # find the file
            match_file = get_file_from_path_by_key(input_directory, f"log*{self.FRAMEOWNER}{node_id_curr}*.json")

            if not match_file:
                logger.debug(f"Cannot find adgraph corresponding to {node_id_curr}")
                continue

            # get the first node parent id, and replace all instances of that with the current node_id
            timeline_to_add = None
            with open(match_file) as f:
                match_file_json = json.load(f)
                # check to see if the match file is a valid file to stitch
                should_stitch_with_match_file = _should_stitch(main_file_json, match_file_json,
                                                               double_check_main_node_id=main_file_html_node_id)

                if not should_stitch_with_match_file:
                    logger.debug(f"Skipping stitching of {match_file}")

                if should_stitch_with_match_file:
                    #logger.debug(f"Stitching of {match_file} into {main_file_path}")
                    wrong_node_parent_id = None

                    # update the match_file_json because it will have the wrong node_parent_id
                    for tmp_event in match_file_json["timeline"]:
                        if not wrong_node_parent_id and "node_parent_id" in tmp_event:
                            wrong_node_parent_id = tmp_event["node_parent_id"]
                            #logger.debug(
                            #    f"wrong node parent id found: {wrong_node_parent_id}, will replace with {node_id_curr}")

                        # for every event that has the wrong_node_parent_id, replace it with the node_id_curr
                        if wrong_node_parent_id and "node_parent_id" in tmp_event \
                                and tmp_event["node_parent_id"] == wrong_node_parent_id:
                            tmp_event["node_parent_id"] = node_id_curr

                        tmp_event_has_ads = _event_has_ad(tmp_event)
                        if tmp_event_has_ads:
                            ad_nodes.append(node_id_curr)

                        # add more if this file also has flg_iframe_id to deal with nested iframes
                        node_id_tmp = _get_iframe_node_id(tmp_event)
                        if node_id_tmp is not None and node_id_tmp not in flg_iframe_ids:
                            #logger.debug(f"found iframe node to parse {node_id_tmp}")
                            flg_iframe_id_queue.append(node_id_tmp)
                            flg_iframe_ids.add(node_id_tmp)
                            iframe_node_g.add_node(node_id_tmp)
                            iframe_node_g.add_edge(node_id_curr, node_id_tmp)

                    timeline_to_add = match_file_json["timeline"]

            if timeline_to_add:
                # find the last occurrence of node_id in the main_file_json
                index_found = None
                remove_event_at_index = False
                for index, tmp_event in enumerate(reversed(main_file_json["timeline"]), start=0):
                    if "node_id" in tmp_event and tmp_event["node_id"] == node_id_curr:
                        index_found = index
                        # if the last event is a NodeRemoval event, then remove it, since we want to ignore it
                        if "event_type" in tmp_event and tmp_event["event_type"] == "NodeRemoval":
                            remove_event_at_index = True
                        break

                if index_found is None:
                    raise BuildingSnapshotException(
                        f"Index to add cannot be None for {node_id_curr}")

                if remove_event_at_index:
                    remove_at_index = (-1 * index_found) - 1
                    del main_file_json["timeline"][remove_at_index]
                    #logger.debug(f"removing event from main file at index: {remove_at_index}")
                    # replace it at the node we just deleted
                    replace_at_index = (-1 * index_found)
                else:
                    # replace it at the node+1 of index_found
                    replace_at_index = (-1 * index_found) + 1

                #logger.debug(f"inserting new timeline into index: {replace_at_index}")
                if replace_at_index < 0:
                    # update the main_file_json
                    main_file_json["timeline"][replace_at_index:replace_at_index] = timeline_to_add
                else:
                    main_file_json["timeline"] += timeline_to_add

        # annotate the found ad_nodes in the main_file_json
        #logger.debug(f"Number of ad nodes found {set(ad_nodes)}")
        top_most_ad_nodes = []
        for ad_node in set(ad_nodes):
            found_anc = False
            for anc in nx.ancestors(iframe_node_g, ad_node):
                if iframe_node_g.in_degree(anc) == 0:
                    top_most_ad_nodes.append(anc)
                    found_anc = True
                    break
            if not found_anc:
                top_most_ad_nodes.append(ad_node)

        # must be sorted because we are going through the timeline once
        top_most_ad_nodes = list(set(top_most_ad_nodes))
        top_most_ad_nodes.sort(key=lambda x: int(x))
        #logger.debug(f"Number of top ad nodes found {top_most_ad_nodes}")

        curr_index = 0
        curr_len = len(main_file_json["timeline"])
        for node_id in top_most_ad_nodes:
            # main_file_json["timeline"].append(_create_annotate_flg_ad_event(node_id))
            while (curr_index < curr_len):
                event = main_file_json["timeline"][curr_index]
                found_match = False
                if "event_type" in event and event["event_type"] == "NodeInsertion" and event["node_id"] == node_id:
                    #logger.debug(f"Found location {curr_index + 1} to add flg-ad=true event")
                    main_file_json["timeline"].insert(curr_index + 1, _create_annotate_flg_ad_event(node_id))
                    curr_index += 1
                    curr_len += 1
                    found_match = True
                curr_index += 1
                if found_match:
                    break

        # output a new json with everything stitched together
        new_main_file_path = main_file_path[:-len(".json")] + "_all.json"
        with open(new_main_file_path, "w") as f:
            json.dump(main_file_json, f)
            #logger.debug(f"outputted new stitched raw adgraph at {new_main_file_path}")

        return new_main_file_path

    def stitch_adgraphs_old(self, input_directory: str, site_url: str) -> str:
        """
        Since each iframe will be outputted as its own adgraph JSON file, we need to stitch together
        all raw adgraphs in rendering_stream by using the flg-iframe-id annotations.
        input_directory: is already the directory that holds all raw adgraph files for a given site
        Returns: the file path of the new stitched together adgraph file
        """

        def _get_first_html_node_id(json_obj) -> int:
            main_node_id = -1
            for event in json_obj["timeline"]:
                if "tag_name" in event and event["tag_name"].lower() == "html":
                    if "node_id" in event:
                        main_node_id = int(event["node_id"])
                        break
            return main_node_id

        def _should_stitch(main_json, other_json, double_check_main_node_id: int = -1) -> bool:
            main_url = main_json["url"]
            other_url = other_json["url"]
            if main_url != other_url:
                return True

            main_node_id = _get_first_html_node_id(main_json)
            other_node_id = _get_first_html_node_id(other_json)

            if double_check_main_node_id != -1 and main_node_id != double_check_main_node_id:
                raise SiteSnapshotException(
                    f"Could not stitch adgraphs, first HTML node id is wrong. Expected {double_check_main_node_id} vs. Got {main_node_id}")

            # don't stitch if the doc URLs are the same and the node_ids overlap. This is due to a bug
            #logger.debug(f"Should stitch: {main_node_id} vs. {other_node_id}")
            return main_node_id < other_node_id

        def _get_flg_iframe_id_from_event(timeline_event: typing.Any) \
                -> typing.Tuple[typing.Optional[str], typing.Optional[str]]:

            if "event_type" in timeline_event and timeline_event["event_type"] == "AttrAddition":
                if timeline_event["node_attribute"]["attr_name"] == FLG_IFRAME_ID:
                    flg_iframe_id = timeline_event["node_attribute"]["attr_value"]
                    node_id = timeline_event["node_id"]
                    return flg_iframe_id, node_id

            return None, None

        # logger.debug(f"Finding largest raw adgraph file from {input_directory}")
        main_file_path = get_main_raw_adgraph_file_path(input_directory, site_url)

        if main_file_path is None:
            raise MissingSnapshotException(f"A main raw file needs to be found in {input_directory}")

        main_file_html_node_id = -1
        with open(main_file_path, "r") as f:
            main_file_json = json.load(f)
            main_file_html_node_id = _get_first_html_node_id(main_file_json)

        flg_iframe_ids = set()
        flg_iframe_id_queue = collections.deque()
        for event in main_file_json["timeline"]:
            flg_iframe_id, node_id = _get_flg_iframe_id_from_event(event)
            if flg_iframe_id is not None and flg_iframe_id not in flg_iframe_ids:
                #logger.debug(f"found flg-frame-id to parse {flg_iframe_id}, {node_id}")
                flg_iframe_id_queue.append((flg_iframe_id, node_id))
                flg_iframe_ids.add(flg_iframe_id)

        # find the file that matches each flg_iframe_id
        while flg_iframe_id_queue:
            flg_iframe_id_curr, node_id_curr = flg_iframe_id_queue.popleft()

            # find the file
            match_file = get_file_from_path_by_key(input_directory, f"log*{flg_iframe_id_curr}.json")

            if not match_file:
                logger.debug(f"Cannot find adgraph corresponding to {flg_iframe_id_curr}")
                continue

            # get the first node parent id, and replace all instances of that with the current node_id
            timeline_to_add = None
            with open(match_file) as f:
                match_file_json = json.load(f)
                # check to see if the match file is a valid file to stitch
                should_stitch_with_match_file = _should_stitch(main_file_json, match_file_json,
                                                               double_check_main_node_id=main_file_html_node_id)

                if not should_stitch_with_match_file:
                    logger.debug(f"Skipping stitching of {match_file}")

                if should_stitch_with_match_file:
                    wrong_node_parent_id = None

                    # update the match_file_json because it will have the wrong node_parent_id
                    for tmp_event in match_file_json["timeline"]:
                        if not wrong_node_parent_id and "node_parent_id" in tmp_event:
                            wrong_node_parent_id = tmp_event["node_parent_id"]
                            #logger.debug(
                            #    f"wrong node parent id found: {wrong_node_parent_id}, will replace with {node_id_curr}")

                        # for every event that has the wrong_node_parent_id, replace it with the node_id_curr
                        if wrong_node_parent_id and "node_parent_id" in tmp_event \
                                and tmp_event["node_parent_id"] == wrong_node_parent_id:
                            tmp_event["node_parent_id"] = node_id_curr

                        # add more if this file also has flg_iframe_id to deal with nested iframes
                        flg_iframe_id_tmp, node_id_tmp = _get_flg_iframe_id_from_event(tmp_event)
                        if flg_iframe_id_tmp is not None and flg_iframe_id_tmp not in flg_iframe_ids:
                            #logger.debug(f"found flg-frame-id to parse {flg_iframe_id_tmp}, {node_id_tmp}")
                            flg_iframe_id_queue.append((flg_iframe_id_tmp, node_id_tmp))
                            flg_iframe_ids.add(flg_iframe_id_tmp)

                    timeline_to_add = match_file_json["timeline"]

            if timeline_to_add:
                # find the last occurrence of node_id in the main_file_json
                index_found = None
                remove_event_at_index = False
                for index, tmp_event in enumerate(reversed(main_file_json["timeline"]), start=0):
                    if "node_id" in tmp_event and tmp_event["node_id"] == node_id_curr:
                        index_found = index
                        # if the last event is a NodeRemoval event, then remove it, since we want to ignore it
                        if "event_type" in tmp_event and tmp_event["event_type"] == "NodeRemoval":
                            remove_event_at_index = True
                        break

                if index_found is None:
                    raise BuildingSnapshotException(
                        f"Index to add cannot be None for {node_id_curr} and {flg_iframe_id_curr}")

                if remove_event_at_index:
                    remove_at_index = (-1 * index_found) - 1
                    del main_file_json["timeline"][remove_at_index]
                    #logger.debug(f"removing event from main file at index: {remove_at_index}")
                    replace_at_index = (-1 * index_found)
                else:
                    replace_at_index = (-1 * index_found) + 1

                #logger.debug(f"inserting new timeline into index: {replace_at_index}")
                # update the main_file_json
                if replace_at_index < 0:
                    main_file_json["timeline"][replace_at_index:replace_at_index] = timeline_to_add
                else:
                    main_file_json["timeline"] += timeline_to_add

        # output a new json with everything stitched together
        new_main_file_path = main_file_path[:-len(".json")] + "_all.json"
        with open(new_main_file_path, "w") as f:
            json.dump(main_file_json, f)
            #logger.debug(f"outputted new stitched raw adgraph at {new_main_file_path}")

        return new_main_file_path

    def has_url_variation_in_graph(self, url_variation: str, url_type: str = None) -> bool:
        """
        Returns whether our graph holds any nodes that matches url_variation based on url_type as well
        """
        url_found = ""
        for n, node_data in self._snapshot.nodes(data=True):
            if REQUESTED_URL in node_data:
                url_found = node_data[REQUESTED_URL]
            if INFO in node_data and NODE_TYPE in node_data \
                    and node_data[NODE_TYPE] == "URL":
                url_found = node_data[INFO]

            if url_found and url_variation in url_found:
                # check against the type to not over-match things like ads-twitter.com with twitter.com
                sld, fqdn, fqdn_path, _ = get_variations_of_domains(url_found)
                if not url_type:
                    if sld == url_variation or fqdn == url_variation or fqdn_path == url_variation:
                        return True
                else:
                    if url_type == TYPE_ESLD and sld == url_variation:
                        return True
                    if url_type == TYPE_FQDN and fqdn == url_variation:
                        return True
                    if url_type == TYPE_FQDN_PATH and fqdn_path == url_variation:
                        return True

        return False

    def get_number_of_ads(self) -> int:
        found_ads_list = get_nodes_by_data_key(self.get_graph(), FLG_AD, "true")
        return len(found_ads_list) if found_ads_list else 0

    def get_number_of_images(self) -> int:
        found_list = get_nodes_by_data_key(self.get_graph(), FLG_IMAGE, "true")
        return len(found_list) if found_list else 0

    def get_number_of_textnodes(self) -> int:
        found_list = get_nodes_by_data_key(self.get_graph(), FLG_TEXTNODE, "true")
        return len(found_list) if found_list else 0

    def has_ads(self) -> bool:
        return self.get_number_of_ads() > 0

    def has_page_content(self) -> bool:
        return self.get_number_of_images() > 0 or self.get_number_of_textnodes() > 0

    def does_domain_affect_ads(self, domain: str) -> bool:
        found_ads_list = get_nodes_by_data_key(self.get_graph(), FLG_AD, "true")

        for n, n_data in self.get_graph().nodes(data=True):
            if (INFO in n_data and domain in n_data[INFO]) or \
                    (REQUESTED_URL in n_data and domain in n_data[REQUESTED_URL]):
                for ad_node in found_ads_list:
                    if nx.has_path(self.get_graph(), n, ad_node):
                        return True

        return False

    def __str__(self):
        return self.snapshot_name

    def extract_script_from_annotated_iframes(self) -> set:
        """
        For every annotated iframe, go through every SCRIPT node and return the URL
        """
        iframe_nodes = get_nodes_by_data_key(self.get_graph(), FLG_AD, "true")
        # logger.debug(f"found iframe nodes {iframe_nodes}")
        script_urls_found = []
        for iframe_node in iframe_nodes:
            subgraph = nx.induced_subgraph(self.get_graph(),
                                           [iframe_node] + list(nx.descendants(self.get_graph(), iframe_node)))
            # for every script node (with id SCRIPT_XXX) in subgraph, find if it has descendents of NODE_ type
            for node, node_data in subgraph.nodes(data=True):
                if SNAPSHOT_NODE_ATTRIBUE__ID in node_data and SNAPSHOT_NODE__SCRIPT in node_data[
                    SNAPSHOT_NODE_ATTRIBUE__ID]:
                    for pred in subgraph.predecessors(node):
                        edge_data = subgraph.get_edge_data(pred, node)
                        if EDGE_TYPE in edge_data and edge_data[EDGE_TYPE] == SNAPSHOT_EDGE__NODE_TO_SCRIPT:
                            pred_data = subgraph.nodes.get(pred)
                            if INFO in pred_data and "http" in pred_data[INFO]:
                                script_urls_found.append(pred_data[INFO])
        # logger.debug(f"found {len(script_urls_found)} urls from {self.snapshot_name}")
        return set(script_urls_found)

    def extract_script_from_annotated_iframes_that_affect_DOM(self) -> set:
        """
        For every annotated iframe, go through every SCRIPT node.
        If the SCRIPT node has descendents of a DOM node, then retrieve the URL for that script

        Return the set of URLS of scripts that affected the DOM.
        """
        iframe_nodes = get_nodes_by_data_key(self.get_graph(), FLG_AD, "true")
        #logger.debug(f"found iframe nodes {iframe_nodes}")
        script_urls_found = []
        for iframe_node in iframe_nodes:
            subgraph = nx.induced_subgraph(self.get_graph(),
                                           [iframe_node] + list(nx.descendants(self.get_graph(), iframe_node)))
            # for every script node (with id SCRIPT_XXX) in subgraph, find if it has descendents of NODE_ type
            for node, node_data in subgraph.nodes(data=True):
                affected_dom = False
                if SNAPSHOT_NODE_ATTRIBUE__ID in node_data and SNAPSHOT_NODE__SCRIPT in node_data[
                    SNAPSHOT_NODE_ATTRIBUE__ID]:
                    for desc in nx.descendants(subgraph, node):
                        desc_data = subgraph.nodes.get(desc)
                        if SNAPSHOT_NODE_ATTRIBUE__ID in desc_data and SNAPSHOT_NODE__NODE in desc_data[
                            SNAPSHOT_NODE_ATTRIBUE__ID]:
                            affected_dom = True
                            #logger.debug(f"script node {node} affected dom node {desc}")
                            break
                # if the script node affected the DOM, then get the URL
                if affected_dom:
                    for pred in subgraph.predecessors(node):
                        edge_data = subgraph.get_edge_data(pred, node)
                        if EDGE_TYPE in edge_data and edge_data[EDGE_TYPE] == SNAPSHOT_EDGE__NODE_TO_SCRIPT:
                            pred_data = subgraph.nodes.get(pred)
                            if INFO in pred_data and "http" in pred_data[INFO]:
                                script_urls_found.append(pred_data[INFO])

        return set(script_urls_found)
