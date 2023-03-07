import logging
import logging
import os
import subprocess
import typing
import pandas as pd
from subprocess import CompletedProcess

from autofr.common.action_space_utils import TYPE_ESLD, TYPE_FQDN, TYPE_FQDN_PATH
from autofr.common.selenium_utils import get_webrequests_from_perf_json
from autofr.common.utils import get_variations_of_domains
from autofr.rl.browser_env.reward import SiteFeedback, SiteFeedbackRange, RewardTerms

logger = logging.getLogger(__name__)

DOCKER_RUN_ARGS_START = [
    "docker", "run",
    "--tmpfs", "/tmp:exec",
    "--shm-size", "2g",
    "--rm"]

# The docker data directories and host machine data dirs are hard-coded.
# Changing any of these will most likely break other parts of the code

DATA_DIR_NAME = "data"
OUTPUT_DIR_NAME = "output"
# host machine
HOST_MACHINE_DATA_PATH = os.getcwd() + os.sep + DATA_DIR_NAME
HOST_MACHINE_OUTPUT_PATH = HOST_MACHINE_DATA_PATH + os.sep + OUTPUT_DIR_NAME
# docker
DOCKER_USER_HOME_PATH = "/home/user"
DOCKER_USER_DATA_PATH = DOCKER_USER_HOME_PATH + os.sep + DATA_DIR_NAME
DOCKER_OUTPUT_PATH = DOCKER_USER_DATA_PATH + os.sep + OUTPUT_DIR_NAME

RELATIVE_OUTPUT_PATH = DATA_DIR_NAME + os.sep + OUTPUT_DIR_NAME

ONE_ITERATION_DOCKER_NAME = "flg-ad-highlighter-simple"
DEFAULT_DOCKER_NAME = "flg-ad-highlighter"

# are we inside a docker? The DockerFile has to specify this ENV
IS_INSIDE_DOCKER = os.environ.get('IS_INSIDE_DOCKER', "False") == "True"


class DockerResponseBase:

    def __init__(self,
                 main_path: str = None,
                 outgoing_requests: list = None,
                 ):
        self.main_path = main_path or ""
        self.outgoing_requests = outgoing_requests or []
        self.merged_docker_responses = []
        # keep track of response to different variations
        self.response_to_url_variations = dict()

    def create_response_to_url_variations(self) -> dict:
        for index, response in enumerate(self.merged_docker_responses):
            if index not in self.response_to_url_variations:
                self.response_to_url_variations[index] = {TYPE_ESLD: dict(),
                                                          TYPE_FQDN: dict(),
                                                          TYPE_FQDN_PATH: dict()}

            for perf_log in response.perf_log_files:
                out_tmp = get_webrequests_from_perf_json(perf_log)
                for url in out_tmp:
                    sld, fqdn, fqdn_path, _ = get_variations_of_domains(url)
                    if sld:
                        self.response_to_url_variations[index][TYPE_ESLD][sld] = 1
                    if fqdn:
                        self.response_to_url_variations[index][TYPE_FQDN][fqdn] = 1
                    if fqdn_path:
                        self.response_to_url_variations[index][TYPE_FQDN][fqdn_path] = 1

        return self.response_to_url_variations

    def has_url_variations_in_all_responses(self, url: str, node_type: str) -> bool:
        if len(self.response_to_url_variations) == 0:
            self.create_response_to_url_variations()

        for index in self.response_to_url_variations:
            if self.response_to_url_variations[index][node_type].get(url, 0) != 1:
                return False

        return True

    def update_with_docker_response(self, docker_response: "DockerResponseBase"):
        self.merged_docker_responses.append(docker_response)
        self.outgoing_requests += docker_response.outgoing_requests

    def sort(self):
        """
        Sort all lists
        """
        self.outgoing_requests.sort()

    def __str__(self):
        return f"Got outgoing requests: {len(self.outgoing_requests)}\n"


class InitSiteFeedbackDockerResponse(DockerResponseBase):
    def __init__(self, *args,
                 init_site_feedback_range: SiteFeedbackRange = None,
                 perf_log_files: list = None,
                 adgraph_files: list = None,
                 snapshot_files: list = None,
                 dissimilar_hash_files: list = None,
                 **kwargs):
        super(InitSiteFeedbackDockerResponse, self).__init__(*args, **kwargs)
        self.init_site_feedback_range = init_site_feedback_range or SiteFeedbackRange()
        self.perf_log_files = perf_log_files or []
        self.adgraph_files = adgraph_files or []
        self.snapshot_files = snapshot_files or []
        self.dissimilar_hash_files = dissimilar_hash_files or []

    def update_with_docker_response(self, docker_response: "InitSiteFeedbackDockerResponse"):
        super(InitSiteFeedbackDockerResponse, self).update_with_docker_response(docker_response)
        self.init_site_feedback_range.site_feedbacks += docker_response.init_site_feedback_range.site_feedbacks
        self.perf_log_files += docker_response.perf_log_files
        self.adgraph_files += docker_response.adgraph_files
        self.snapshot_files += docker_response.snapshot_files
        self.dissimilar_hash_files += docker_response.dissimilar_hash_files

    def get_dissimilar_hashes(self) -> typing.Optional[pd.DataFrame]:
        dissimilar_hashes_dfs = []
        dissimilar_hashes_df_merged = None
        try:
            for f in self.dissimilar_hash_files:
                dissimilar_hashes_dfs.append(pd.read_csv(f))
            if len(dissimilar_hashes_dfs) > 0:
                dissimilar_hashes_df_merged = pd.concat(dissimilar_hashes_dfs)
        except ValueError:
            logger.warning(f"Could not retrieve and merge dissimilar hash files", exc_info=True)

        return dissimilar_hashes_df_merged

    def sort(self):
        """
        Sort all lists
        """
        super(InitSiteFeedbackDockerResponse, self).sort()
        self.perf_log_files.sort()
        self.adgraph_files.sort()
        self.snapshot_files.sort()
        self.dissimilar_hash_files.sort()

    def __str__(self):
        result = super(InitSiteFeedbackDockerResponse, self).__str__()
        result += f"Got init site feedback range: {self.init_site_feedback_range}\n"
        result += f"Got performance logs: {len(self.perf_log_files)}\n"
        result += f"Found Raw Adgraph files: {len(self.adgraph_files)}\n"
        result += f"Found Site Snapshots files: {len(self.snapshot_files)}\n"
        result += f"Found Dissimilar hash files: {len(self.dissimilar_hash_files)}\n"

        return result


class SiteFeedbackFilterRulesDockerResponse(DockerResponseBase):
    def __init__(self,
                 site_feedback: SiteFeedback,
                 *args,
                 filter_rules: list = None,
                 block_items_and_match: dict = None,
                 images_records: list = None,
                 textnode_records: list = None,
                 reward: RewardTerms = None,
                 is_optimal: bool = False,
                 action: typing.Any = None,
                 **kwargs):
        super(SiteFeedbackFilterRulesDockerResponse, self).__init__(*args, **kwargs)
        self.site_feedback = site_feedback
        self.filter_rules = filter_rules or []
        self.block_items_and_match = block_items_and_match or dict()
        self.images_records = images_records or []
        self.textnode_records = textnode_records or []

        # set later
        self.reward = reward
        self.is_optimal = is_optimal

        # equivalent to filter_rules but in the non-filter-rule form
        self.action = action

    def __str__(self):
        result = super(SiteFeedbackFilterRulesDockerResponse, self).__str__()
        result += f"filter rules tried: {len(self.filter_rules or [])}\n"
        result += f"site feedback: {self.site_feedback}\n"

        rules_that_match = 0
        for rule in self.block_items_and_match:
            if len(self.block_items_and_match[rule]) > 0:
                rules_that_match += 1

        result += f"number of rules that match: {rules_that_match}\n"
        result += f"rules triggered: {list(self.block_items_and_match.keys())}\n"
        return result


def get_docker_run_params(docker_name: str, **env_vars) -> list:
    env_list = []
    for key, value in env_vars.items():
        env_list += ["-e", key + "=" + str(value)]

    docker_params = DOCKER_RUN_ARGS_START \
                    + env_list \
                    + ["-v", f"{HOST_MACHINE_DATA_PATH}:{DOCKER_USER_DATA_PATH}", docker_name]

    return docker_params


def run_browser_docker_process(docker_name: str, **env_vars) -> CompletedProcess:
    process = subprocess.run(get_docker_run_params(docker_name, **env_vars),
                             stdout=subprocess.PIPE, universal_newlines=True)
    return process


def create_items_to_block(block_items: list, file_path: str):
    with open(file_path, "w") as f:
        if len(block_items) > 0:
            f.writelines(l + '\n' for l in block_items)




