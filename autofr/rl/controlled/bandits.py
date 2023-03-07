import collections
import concurrent
import glob
import logging
import os
import random
import time
import typing
from typing import Tuple, List

import networkx as nx
from adblockparser import AdblockRule

from autofr.common.action_space_utils import ROOT_NODE_ID
from autofr.common.adblockparser_utils import AutoFRAdblockRules
from autofr.common.docker_utils import HOST_MACHINE_OUTPUT_PATH, InitSiteFeedbackDockerResponse, \
    SiteFeedbackFilterRulesDockerResponse
from autofr.common.exceptions import AutoFRException
from autofr.common.filter_rules_utils import FilterRuleBlockRecord, create_rule_simple
from autofr.rl.action_space import EDGE_TYPE, TYPE, ActionSpace
from autofr.rl.bandits import AutoFRMultiArmedBandit
from autofr.rl.browser_env.reward import SiteFeedback, SiteFeedbackCache
from autofr.rl.browser_env.runner.adgraph_env_runner import AdgraphBrowserEnvRunner, \
    AdgraphBrowserFromDirEnvRunner
from autofr.rl.browser_env.runner.docker_env_runner import AdgraphDockerEnvRunner
from autofr.rl.controlled.site_snapshot import ADGRAPH_NETWORKX, NODE_TYPE, INFO, REQUESTED_URL, FLG_IMAGE, \
    FLG_TEXTNODE, FLG_AD, has_non_dom_predecessor_edges, SNAPSHOT_EDGE__DOM, SiteSnapshot, is_flg_ad_node, \
    is_flg_image_node, is_flg_textnode, \
    is_node_data_annotated

logger = logging.getLogger(__name__)


class AutoFRMultiArmedBanditGetSnapshots(AutoFRMultiArmedBandit):

    def __init__(self, ad_highlighter_ext_path: str,
                 *args,
                 browser_path: str = None,
                 chrome_driver_path: str = None,
                 adblock_proxy_path: str = None,
                 adgraph_files: list = None,
                 site_snapshot_dir_name: str = ADGRAPH_NETWORKX,
                 site_snapshot_klass: typing.Callable = SiteSnapshot,
                 **kwargs):
        super(AutoFRMultiArmedBanditGetSnapshots, self).__init__(*args, **kwargs)
        self.ad_highlighter_ext_path = ad_highlighter_ext_path
        self.browser_path = browser_path
        self.chrome_driver_path = chrome_driver_path
        self.adblock_proxy_path = adblock_proxy_path
        self.adgraph_files = adgraph_files or []
        self.site_snapshots: typing.List[typing.Tuple[SiteSnapshot, str]] = []
        self.site_snapshot_klass = site_snapshot_klass

        # dir name only that holds the processed snapshots already
        self.site_snapshot_dir_name = site_snapshot_dir_name

        if not os.path.isdir(self.get_base_site_snapshots_dir()):
            os.makedirs(self.get_base_site_snapshots_dir())

    def reset(self):
        super(AutoFRMultiArmedBanditGetSnapshots, self).reset()

    def get_base_site_snapshots_dir(self) -> str:
        """
        The snapshot directory for this particular experiment
        """
        return self.get_base_data_dir() + os.sep + self.site_snapshot_dir_name

    def _read_site_snapshots(self, url: str):
        """
        Read in site snapshots that have already been processed from JSON into graphml files
        """
        processed_nx_dir = self.get_base_site_snapshots_dir()
        if os.path.isdir(processed_nx_dir):
            networkx_files = glob.glob(processed_nx_dir + os.sep + "*.graphml")
            for f in networkx_files:
                site_snapshot: SiteSnapshot = self.site_snapshot_klass(url,
                                                base_name=self.base_name,
                                                snapshot_nx_file_path=f)
                if site_snapshot.has_ads() and site_snapshot.has_page_content():
                    self.site_snapshots.append((site_snapshot, site_snapshot.snapshot_name))

    def prepare_site_snapshots(self, url: str) -> bool:
        """
        Run raw adgraphs through the adgraphapi process
        Returns: true for success
        """
        # try to read site snapshots first
        self._read_site_snapshots(url)

        # if none available, we will need to process from raw adgraph to site snapshots
        if self.adgraph_files and len(self.site_snapshots) == 0:
            self._read_raw_snapshot_files(url)

        # sort site snapshots
        if len(self.site_snapshots) > 0:
            # sort by name
            self.site_snapshots.sort(key=lambda x: x[1])
            return True

        return False

    def _read_raw_snapshot_files(self, url: str):
        """
        Site Snapshots have not been processed, so only pass in the raw adgraphs files
        """
        if self.adgraph_files and len(self.site_snapshots) == 0:
            # copy files to data dir ready to be processed
            for f in self.adgraph_files:
                site_snapshot: SiteSnapshot = self.site_snapshot_klass(url,
                                             base_name=self.base_name,
                                             adgraph_raw_file_path=f)
                if site_snapshot.has_ads() and site_snapshot.has_page_content():
                    self.site_snapshots.append((site_snapshot, site_snapshot.snapshot_name))

    def find_initial_state(self, *args, **kwargs) -> InitSiteFeedbackDockerResponse:

        # if we have not done the init work yet, then do them now
        return super(AutoFRMultiArmedBanditGetSnapshots, self).find_initial_state(*args, **kwargs)

    def create_init_runner(self, url: str,
                           INIT_STATE_ITERATIONS: int = 1,
                           filter_list_path: str = None,
                           use_docker: bool = False):

        if use_docker:
            return AdgraphDockerEnvRunner(
                url, docker_name_suffix=self.docker_name_suffix,
                base_name=self.base_name,
                DO_INITIAL_STATE_ONLY=True,
                INIT_STATE_ITERATIONS=INIT_STATE_ITERATIONS,
                filter_list_path=filter_list_path
            )
        else:
            return AdgraphBrowserEnvRunner(
                self.ad_highlighter_ext_path,
                url,
                browser_path=self.browser_path,
                chrome_driver_path=self.chrome_driver_path,
                adblock_proxy_path=self.adblock_proxy_path,
                docker_name_suffix=self.docker_name_suffix,
                base_name=self.base_name,
                DO_INITIAL_STATE_ONLY=True,
                INIT_STATE_ITERATIONS=INIT_STATE_ITERATIONS,
                OUTPUT_PATH=HOST_MACHINE_OUTPUT_PATH,
                filter_list_path=filter_list_path
            )


class DomainHierarchyMABControlled(AutoFRMultiArmedBanditGetSnapshots):
    """
    This Bandit only uses snapshots. It will not go to the site directly.
    Must pass in the directory where the snapshot is
    """

    def __init__(self,
                 init_dir,
                 *args,
                 seed_random: bool = True,
                 action_space: ActionSpace = None,
                 choose_snapshot_random: bool = True,
                 use_snapshot_cache: bool = False,
                 **kwargs):
        """
        use_snapshot_cache: only controls whether we read from the filesystem for the cache file,
            otherwise we always keep an im memory cache for better performance
        """

        ad_highlighter_path = ""
        super(DomainHierarchyMABControlled, self).__init__(ad_highlighter_path,
                                                           *args, **kwargs)

        # action space needed to do pulling later with site snapshots
        self.action_space = action_space

        # top level directory of where the snapshots are, including the raw files
        self.init_dir = init_dir
        self.seed_random = seed_random
        if self.seed_random:
            # must set seed before calling random.choice
            random.seed(40)

        # keeps track of site feedback given an action and site snapshot
        self.site_feedback_cache = SiteFeedbackCache()
        if self.init_dir and use_snapshot_cache:
            try:
                self.site_feedback_cache = SiteFeedbackCache.read_cache(self.init_dir)
            except AttributeError as e:
                logger.debug(f"Could not read in cache file, starting new one. {e}")
        if self.site_feedback_cache is None:
            self.site_feedback_cache = SiteFeedbackCache()

        self.adblock_parser_cache = dict()
        if not os.path.isdir(self.get_base_site_snapshots_dir()):
            os.makedirs(self.get_base_site_snapshots_dir())

        self.choose_snapshot_random = choose_snapshot_random
        self.use_snapshot_cache = use_snapshot_cache
        self.snapshot_choice_history = []

    def reset(self):
        super(DomainHierarchyMABControlled, self).reset()
        self.adblock_parser_cache.clear()
        self.snapshot_choice_history.clear()
        if self.seed_random:
            # must set seed before calling random.choice
            random.seed(40)

    def save_cache(self):
        if self.use_snapshot_cache:
            self.site_feedback_cache.save(self.get_base_data_dir())

    def _read_site_snapshots(self, url: str):
        """
        Read in site snapshots that have already been processed from JSON into graphml files
        """
        if self.init_dir:
            processed_nx_dir = self.init_dir + os.sep + self.site_snapshot_dir_name
            if os.path.isdir(processed_nx_dir):
                networkx_files = glob.glob(processed_nx_dir + os.sep + "*.graphml")
                for f in networkx_files:
                    site_snapshot = self.site_snapshot_klass(url,
                                                    base_name=self.base_name,
                                                    snapshot_nx_file_path=f)
                    if site_snapshot.has_ads() and site_snapshot.has_page_content():
                        self.site_snapshots.append((site_snapshot, site_snapshot.snapshot_name))

    def find_initial_state(self,
                           url,
                           init_state_iterations: int = 10,
                           rounds_per_driver: int = 1,
                           ignore_states_with_zero_ads: bool = True,
                           filter_list_path: str = None,
                           ) -> InitSiteFeedbackDockerResponse:

        # else read in the directories
        execute_done_count = 0
        docker_response_main = InitSiteFeedbackDockerResponse()
        dirs_found = []
        for root, dirs, files in os.walk(self.init_dir):
            for d in dirs:
                if d.startswith("init_"):
                    dirs_found.append(root + os.sep + d)

        # sort this to make things deterministic later when controlled experiment
        dirs_found.sort()

        # read in the data from each init_directory
        for init_adgraph_dir in dirs_found:
            browser_env = self.create_init_runner(url,
                                                  INIT_STATE_ITERATIONS=rounds_per_driver,
                                                  init_adgraph_dir=init_adgraph_dir,
                                                  filter_list_path=filter_list_path
                                                  )
            docker_response = browser_env.get()
            docker_response_main.update_with_docker_response(docker_response)
            execute_done_count += 1

        # keep the state that has larger than 0 ad counter
        if ignore_states_with_zero_ads:
            docker_response_main.init_site_feedback_range.site_feedbacks = [x for x in
                                                                            docker_response_main.init_site_feedback_range.site_feedbacks
                                                                            if x.ad_counter > 0]

        docker_response_main.sort()

        return docker_response_main

    def create_init_runner(self, url: str,
                           INIT_STATE_ITERATIONS: int = 1,
                           filter_list_path: str = None,
                           init_adgraph_dir: str = None) -> AdgraphBrowserFromDirEnvRunner:

        # read in the adgraph dir
        browser_env = AdgraphBrowserFromDirEnvRunner(init_adgraph_dir,
                                                     self.ad_highlighter_ext_path,
                                                     url,
                                                     browser_path=self.browser_path,
                                                     chrome_driver_path=self.chrome_driver_path,
                                                     adblock_proxy_path=self.adblock_proxy_path,
                                                     docker_name_suffix=self.docker_name_suffix,
                                                     base_name=self.base_name,
                                                     DO_INITIAL_STATE_ONLY=True,
                                                     INIT_STATE_ITERATIONS=INIT_STATE_ITERATIONS,
                                                     OUTPUT_PATH=HOST_MACHINE_OUTPUT_PATH
                                                     )
        return browser_env

    def pull_each_arm_parallel(self, url: str, actions: list, **kwargs):
        """
        Here we don't need to pull them in parallel
        """
        results = []
        actions.sort()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_info = {}
            for action in actions:
                future = executor.submit(self.pull, url, action, **kwargs)
                future_to_info[future] = action
            for future in concurrent.futures.as_completed(future_to_info):
                unique_action = future_to_info[future]
                try:
                    result_tmp = future.result()
                except (OSError, AutoFRException) as e:
                    logger.warning(f"{unique_action} pull_each_arm_parallel: generated an exception: {repr(e)} {e}")
                else:
                    results.append(result_tmp)
        return results

    @staticmethod
    def _increment_counter(node_data: dict, ad_counter: int, image_counter: int, textnode_counter: int) \
            -> Tuple[int, int, int, bool, bool, bool]:
        incremented_ad = False
        incremented_img = False
        incremented_text = False
        if is_node_data_annotated(node_data, FLG_AD):
            ad_counter += 1
            incremented_ad = True
        if is_node_data_annotated(node_data, FLG_IMAGE):
            image_counter += 1
            incremented_img = True
        if is_node_data_annotated(node_data, FLG_TEXTNODE):
            textnode_counter += 1
            incremented_text = True
        return ad_counter, image_counter, textnode_counter, \
               incremented_ad, incremented_img, incremented_text

    def _choose_site_snapshot(self, actions: list) -> typing.Tuple[SiteSnapshot, str]:
        """
        Choose site snapshot
        """
        if self.choose_snapshot_random:
            #logger.debug(f"Choosing site snapshot randomly")
            return random.choice(self.site_snapshots)

        possible_site_snapshots = []
        for arm in actions:
            node_type = self.action_space.get(arm)[TYPE]
            for key in self.site_snapshots:
                if key not in possible_site_snapshots:
                    ss, ss_name = key
                    if ss.has_url_variation_in_graph(arm, node_type):
                        possible_site_snapshots.append((ss, ss_name))

        #logger.debug(f"Choosing site snapshot from possible {len(possible_site_snapshots)} for {actions}")
        if possible_site_snapshots:
            possible_site_snapshots.sort(key=lambda x: x[1])
            return random.choice(possible_site_snapshots)

        #logger.warning(f"Found no possible site snapshot for {actions}, falling back to choosing randomly")
        return random.choice(self.site_snapshots)

    def _is_ancestor_blocked(self, node_tmp: str, block_nodes_tmp: dict, site_snapshot: SiteSnapshot) -> typing.Optional[str]:
        found_blocked_ancestor = None
        for ancestor in nx.ancestors(site_snapshot.get_graph(), node_tmp):
            if ancestor in block_nodes_tmp:
                found_blocked_ancestor = ancestor
                break
        return found_blocked_ancestor

    def pull(self, url: str, actions: list,
             is_test: bool = False,
             **kwargs) \
            -> SiteFeedbackFilterRulesDockerResponse:
        """
        Do the following:
        (1) Select a Site Snapshot randomly
        (2) Create a AdblockRules (parser) with the rules version of the actions
        (3) Do a breadth first search to get the site feedback
        (4) Return the response
        """

        # create rules and a parser
        filter_rules = [create_rule_simple(x) for x in actions]

        logger.info(f"{self.__class__.__name__} pulling filter rule(s): {filter_rules}")

        # reset counters and keep track of blocked actions
        ad_counter = 0
        image_counter = 0
        textnode_counter = 0

        # for the control, this is different since the blocking is based on the whole filter_rules
        # we do not know which rule was matched here, so we treat the entire filter_rules as one
        block_items_and_match = dict()
        filter_rules_str = ",".join(filter_rules)

        site_snapshot, site_snapshot_name = self._choose_site_snapshot(actions)

        logger.info(f"Chose {site_snapshot_name} as simulated site from possible {len(self.site_snapshots)} snapshots")
        self.snapshot_choice_history.append(site_snapshot_name)

        # is it in our cache?
        ss_cache_key = site_snapshot_name + filter_rules_str
        if not is_test and self.site_feedback_cache.get(ss_cache_key):
            if self.use_snapshot_cache:
                logger.info(f"Cache hit: {ss_cache_key} for {filter_rules}")
            else:
                logger.info(f"In memory cache hit: {ss_cache_key} for {filter_rules}")
            response: SiteFeedbackFilterRulesDockerResponse = self.site_feedback_cache.get(ss_cache_key)
            response.reward = self.get_reward(response.site_feedback)
            response.is_optimal = self.is_optimal(actions)
            response.action = actions
            logger.info(f"Pull results from cache: {response}")
            return response

        before = time.time()
        if not is_test:
            if filter_rules_str in self.adblock_parser_cache:
                parser = self.adblock_parser_cache[filter_rules_str]
            else:
                parser = AutoFRAdblockRules(filter_rules)
                self.adblock_parser_cache[filter_rules_str] = parser
        else:
            parser = AutoFRAdblockRules(filter_rules)

        # prepare for BFS from randomly chosen site
        node_queue = collections.deque()
        # else continue to figure out the site feedback
        root_key = site_snapshot.get_graph().graph[ROOT_NODE_ID]
        node_queue.append(root_key)

        visited_nodes = dict()
        iframe_nodes = []
        img_nodes_not_blocked = []
        text_nodes_not_blocked = []
        blocked_nodes = dict()
        while node_queue:
            tmp_node = node_queue.popleft()
            if tmp_node in visited_nodes:
                continue

            node_data = site_snapshot.get_graph().nodes.get(tmp_node)

            is_blocked = False
            url_found = None
            matched_rules: List[AdblockRule] = []
            if tmp_node != root_key:
                if REQUESTED_URL in node_data:
                    url_found = node_data[REQUESTED_URL]
                if INFO in node_data and NODE_TYPE in node_data \
                        and node_data[NODE_TYPE] == "URL":
                    url_found = node_data[INFO]
                if url_found:
                    is_blocked, matched_rules = parser.should_block_2(url_found)

            if is_blocked and url_found:
                for adblock_rule in matched_rules:
                    if adblock_rule.raw_rule_text not in block_items_and_match:
                        block_items_and_match[adblock_rule.raw_rule_text] = []
                    record = FilterRuleBlockRecord(adblock_rule.raw_rule_text, url_found, "", "")
                    if record not in block_items_and_match[adblock_rule.raw_rule_text]:
                        block_items_and_match[adblock_rule.raw_rule_text].append(record)
                blocked_nodes[tmp_node] = 1
                if is_test: print(f"node type {node_data[NODE_TYPE]} blocked during looping {tmp_node}")

            # do not go further if this has been blocked
            if not is_blocked:
                if tmp_node != root_key:
                    if INFO in node_data and node_data[INFO].lower() == "iframe":
                        # for iframe nodes, we need to check later
                        iframe_nodes.append(tmp_node)
                    else:
                        # increment counters if it meets conditions
                        ad_counter, image_counter, textnode_counter,\
                            incremented_ad, incremented_img, incremented_text = self._increment_counter(
                            node_data, ad_counter, image_counter, textnode_counter)
                        if incremented_img:
                            img_nodes_not_blocked.append(tmp_node)
                        if incremented_text:
                            text_nodes_not_blocked.append(tmp_node)

                # add successors to the queue
                for s in site_snapshot.get_graph().successors(tmp_node):
                    if s not in visited_nodes:
                        # If the current edge from tmp_node to s is SNAPSHOT_EDGE__DOM and
                        # there are other types of edges from predecessor to s, then do not add s for now
                        # otherwise, always add s.
                        # We do this because we want to follow non-DOM edges mainly
                        #before_adding_successor = time.time()
                        edge_data = site_snapshot.get_graph().get_edge_data(tmp_node, s)
                        if EDGE_TYPE in edge_data and edge_data[EDGE_TYPE] == SNAPSHOT_EDGE__DOM:
                            if not has_non_dom_predecessor_edges(site_snapshot.get_graph(), s):
                                node_queue.append(s)
                            #print(f"Time took to decide to add successor {s}: {time.time() - before_adding_successor}")
                            # logger.debug(f"ignoring node {s} for now due to having other edge types")
                        else:
                            node_queue.append(s)

            visited_nodes[tmp_node] = 1

        not_visited = dict()
        for n in site_snapshot.get_graph().nodes():
            if n not in visited_nodes and n not in not_visited:
                not_visited[n] = 1

        # check iframe nodes
        # this is a special case since multiple nodes can block an iframe
        # we do a set below since there can be dups in iframe_nodes (multiple paths to iframes)
        # logger.debug(f"Found iframe nodes {len(iframe_nodes)}")
        if len(iframe_nodes) > 0:
            # for iframes, we increment, since we did not do so before
            for node in set(iframe_nodes):
                found_blocked_ancestor = self._is_ancestor_blocked(node, blocked_nodes, site_snapshot)
                if found_blocked_ancestor:
                    blocked_nodes[node] = 1
                    if is_test: print(f"Node iframe {node} blocked because ancestor {found_blocked_ancestor}")
                else:
                    ad_counter, image_counter, textnode_counter, _, _, _ = self._increment_counter(
                        site_snapshot.get_graph().nodes.get(node), ad_counter, image_counter, textnode_counter)

        if len(blocked_nodes) > 0:
            # for img and text, we need to decrement since we counted it before
            for node in set(img_nodes_not_blocked):
                found_blocked_ancestor = self._is_ancestor_blocked(node, blocked_nodes, site_snapshot)
                if found_blocked_ancestor:
                    blocked_nodes[node] = 1
                    image_counter -= 1
                    if is_test:
                        path_tmp = nx.shortest_path(site_snapshot.get_graph(), source=found_blocked_ancestor, target=node)
                        print(f"Node image {node} blocked because ancestor {found_blocked_ancestor}: path {path_tmp}")

            for node in set(text_nodes_not_blocked):
                found_blocked_ancestor = self._is_ancestor_blocked(node, blocked_nodes, site_snapshot)
                if found_blocked_ancestor:
                    blocked_nodes[node] = 1
                    textnode_counter -= 1
                    if is_test:
                        path_tmp = nx.shortest_path(site_snapshot.get_graph(), source=found_blocked_ancestor, target=node)
                        print(f"Node textnode {node} blocked because ancestor {found_blocked_ancestor}: path {path_tmp}")


        # create site feedback
        site_feedback = SiteFeedback(ad_counter=ad_counter,
                                     image_counter=image_counter,
                                     textnode_counter=textnode_counter)


        # Categorize blocked nodes.
        # Note that nodes that are explicitly blocked or are not visited are considered "blocked"
        blocked_nodes_all = list(blocked_nodes.keys()) + list(not_visited.keys())
        flg_ads_blocked = []
        flg_images_blocked = []
        flg_textnodes_blocked = []
        others_blocked = []
        for node in blocked_nodes_all:
            if is_flg_ad_node(site_snapshot.get_graph(), node):
                flg_ads_blocked.append(node)
            elif is_flg_image_node(site_snapshot.get_graph(), node):
                flg_images_blocked.append(node)
            elif is_flg_textnode(site_snapshot.get_graph(), node):
                flg_textnodes_blocked.append(node)
            else:
                others_blocked.append(node)

        #print(f"FLG_AD blocked during test: {flg_ads_blocked}")
        #print(f"FLG_IMAGE blocked during test: {flg_images_blocked}")
        #print(f"FLG_TEXTNODE blocked during test: {flg_textnodes_blocked}")
        # if there were no blocking of ads, images, or textnodes, then set it back to the init_site_feedback
        # Note: this is only possible in the controlled environment
        if not is_test:
            if len(flg_ads_blocked) == 0:
                site_feedback.ad_counter = self.init_site_feedback.ad_counter
            if len(flg_images_blocked) == 0:
                site_feedback.image_counter = self.init_site_feedback.image_counter
            if len(flg_textnodes_blocked) == 0:
                site_feedback.textnode_counter = self.init_site_feedback.textnode_counter

        if is_test:
            print(f"Others type of nodes blocked: {others_blocked}")
            print(f"Explicit Blocked nodes: {blocked_nodes}, \n Not visited nodes: {not_visited}")

        logger.info(f"Site feedback found: {site_feedback} for filter rule(s) {filter_rules_str}")
        logger.info(f"Pull {filter_rules} took {time.time() - before}")

        main_path = ""
        outgoing_requests = []
        logger.info(f"Rules triggered: {list(block_items_and_match.keys())}")
        response = SiteFeedbackFilterRulesDockerResponse(site_feedback,
                                                         main_path,
                                                         outgoing_requests,
                                                         filter_rules=filter_rules,
                                                         action=actions,
                                                         block_items_and_match=block_items_and_match,
                                                         reward=self.get_reward(site_feedback),
                                                         is_optimal=self.is_optimal(actions)
                                                         )
        if not is_test:
            # add to cache
            self.site_feedback_cache[ss_cache_key] = response

        logger.info(f"Pull results: {response}")

        return response
