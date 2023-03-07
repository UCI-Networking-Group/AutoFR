import concurrent.futures
import glob
import json
import os
import shutil
from subprocess import CompletedProcess

import pandas as pd

from autofr.common.adgraph_version import get_adgraph_version
from autofr.common.docker_utils import DEFAULT_DOCKER_NAME, DOCKER_OUTPUT_PATH, HOST_MACHINE_OUTPUT_PATH, \
    InitSiteFeedbackDockerResponse, logger, run_browser_docker_process, ONE_ITERATION_DOCKER_NAME, \
    DockerResponseBase, SiteFeedbackFilterRulesDockerResponse
from autofr.common.exceptions import InvalidSiteFeedbackException, DockerException, AutoFRException
from autofr.common.filter_rules_utils import get_rules_from_filter_list, get_filter_records_by_rule
from autofr.common.selenium_utils import get_webrequests_from_perf_json
from autofr.common.utils import clean_url_for_file, get_file_from_path_by_key, get_unique_str
from autofr.rl.browser_env.browser_adgraph_env import ADGRAPH_DIR
from autofr.rl.browser_env.browser_env import STATS_INIT_FILE_NAME, FILTER_LISTS_DIR_NAME, JSON_DIR_NAME, \
    STATS_FILE_NAME, ABP_HITRECORDS_SUFFIX, VISIBLE_IMAGES_FILE_NAME, VISIBLE_TEXTNODES_FILE_NAME, \
    DISSIMILAR_HASH_NAME
from autofr.rl.browser_env.reward import get_site_feedback_range_from_file, get_site_feedback_from_file
from autofr.rl.controlled.site_snapshot import ADGRAPH_NETWORKX, get_main_raw_adgraph_file_path


class DockerEnvRunner:
    """
    Runs browser env with no blocking
    """

    def __init__(self,
                 url: str,
                 docker_name: str = None,
                 full_agent_name: str = "",
                 docker_name_suffix: str = "",
                 base_name: str = "",
                 cleanup_upon_error: bool = True,
                 FLG_AGENT: str = None,
                 DO_INITIAL_STATE_ONLY: bool = True,
                 INIT_STATE_ITERATIONS: int = 4,
                 OUTPUT_PATH: str = DOCKER_OUTPUT_PATH,
                 unique_str: str = None,
                 filter_list_path: str = None,
                 save_dissimilar_hashes: bool = False):

        self.full_agent_name = full_agent_name
        self.url = url
        self.docker_name = docker_name
        self.docker_name_suffix = docker_name_suffix
        self.base_name = base_name
        self.FLG_AGENT = FLG_AGENT
        self.DO_INITIAL_STATE_ONLY = DO_INITIAL_STATE_ONLY
        self.INIT_STATE_ITERATIONS = INIT_STATE_ITERATIONS
        self.OUTPUT_PATH = OUTPUT_PATH
        self.cleanup_upon_error = cleanup_upon_error
        self.unique_str = unique_str or get_unique_str()
        self.filter_list_path = filter_list_path
        self.save_dissimilar_hashes = save_dissimilar_hashes
        if not full_agent_name:
            self.full_agent_name = self.create_full_agent_name()

        # for cleanup
        self.files_to_remove = []

        # used to pass to docker later
        self.docker_blocks_items_path = None

    def destroy(self):
        """
        Remove entire directory
        """
        env_output = self.get_env_output_path()
        if self.full_agent_name:
            env_output += os.sep + self.full_agent_name
        if os.path.isdir(env_output):
            shutil.rmtree(env_output, ignore_errors=True)

    def create_full_agent_name(self) -> str:
        """
        Provides the name of the directory that will hold the output
        """
        raise NotImplementedError("Missing Full Agent Name")

    def execute(self, executor: concurrent.futures.ThreadPoolExecutor) -> DockerResponseBase:

        future = executor.submit(self.get)
        docker_response = future.result()

        return docker_response

    def _prep_run(self):
        """
        Do any prep work for inputs to the docker
        """
        pass

    def _post_run(self, completed_proc: CompletedProcess) -> DockerResponseBase:
        """
        Do post processing after the run
        """
        return DockerResponseBase()

    def _post_run_cleanup(self):
        """
        Do cleanup after the run
        """
        # clean up files too
        for file_path in self.files_to_remove:
            if file_path and os.path.isfile(file_path):
                os.remove(file_path)

    def get(self) -> DockerResponseBase:
        """
            Runs the docker process and read from the necessary file to get the SiteFeedback
            Returns SiteFeedbackRange, whitelist_domains, set of outgoing requests, perf_log_files
        """
        self._prep_run()
        process = self._run()
        response = self._post_run(process)
        self._post_run_cleanup()
        return response

    def get_docker_output_path(self) -> str:
        """
        This includes the output path and basename, which may be absolute for Docker: /data/output
        """
        output_path = self.OUTPUT_PATH
        if self.base_name:
            output_path = self.OUTPUT_PATH + os.sep + self.base_name
        return output_path

    def get_env_output_path(self) -> str:
        """
        Builds the top level path of output for this env runner.
        We assume that the data directory is always in the cwd, HOST_MACHINE_OUTPUT_PATH.
        """

        host_machine_output = HOST_MACHINE_OUTPUT_PATH
        if self.base_name:
            # not docker relative
            host_machine_output += os.sep + self.base_name

        if not os.path.isdir(host_machine_output):
            os.makedirs(host_machine_output, exist_ok=True)

        return host_machine_output

    def _run(self) -> CompletedProcess:
        raise NotImplementedError()


class InitSiteFeedbackDockerEnvRunner(DockerEnvRunner):
    """
    Runs docker to get the init site feedback only
    """

    def __init__(self,
                 *args, **kwargs):
        super(InitSiteFeedbackDockerEnvRunner, self).__init__(*args, **kwargs)
        self.FLG_AGENT = "agent_new.py"
        self.docker_name = DEFAULT_DOCKER_NAME

    def create_full_agent_name(self) -> str:
        return "init_state_" + clean_url_for_file(self.url) + self.unique_str

    def _run(self) -> CompletedProcess:
        docker_name = self.docker_name + self.docker_name_suffix
        docker_output_path = self.get_docker_output_path()
        docker_blocks_items_path = None
        if self.filter_list_path:
            docker_blocks_items_path = docker_output_path + os.sep + os.path.basename(self.filter_list_path)

        return run_browser_docker_process(docker_name,
                                          FLG_AGENT=self.FLG_AGENT,
                                          FULL_AGENT_NAME=self.full_agent_name,
                                          URL=self.url,
                                          BLOCK_ITEMS_FILE_PATH=docker_blocks_items_path,
                                          DO_INITIAL_STATE_ONLY=str(self.DO_INITIAL_STATE_ONLY),
                                          INIT_STATE_ITERATIONS=self.INIT_STATE_ITERATIONS,
                                          OUTPUT_PATH=docker_output_path,
                                          SAVE_DISSIMILAR_HASHES=self.save_dissimilar_hashes
                                          )

    def _prep_run(self):
        super(InitSiteFeedbackDockerEnvRunner, self)._prep_run()

        env_dir = self.get_env_output_path()
        # No matter where the filter list is,
        # copy it to right place to be read in later (so that docker can access it)
        if self.filter_list_path:
            new_filter_list_path = env_dir + os.sep + os.path.basename(self.filter_list_path)
            shutil.copyfile(self.filter_list_path, new_filter_list_path)
            self.files_to_remove.append(new_filter_list_path)

    def _post_run(self, completed_proc: CompletedProcess) -> InitSiteFeedbackDockerResponse:
        env_dir = self.get_env_output_path()
        main_path = env_dir + os.sep + self.full_agent_name
        stats_init_file_path = main_path + os.sep + STATS_INIT_FILE_NAME
        filter_lists_path = main_path + os.sep + FILTER_LISTS_DIR_NAME
        json_lists_path = main_path + os.sep + JSON_DIR_NAME
        dissimilar_hash_file_path = json_lists_path + os.sep + DISSIMILAR_HASH_NAME

        if completed_proc.returncode == 0:
            # read in the init file
            #logger.debug("Getting init site_feedback file from: %s", stats_init_file_path)
            init_site_feedback_range = get_site_feedback_range_from_file(stats_init_file_path)
            if init_site_feedback_range is None:
                raise InvalidSiteFeedbackException(f"Feedback range cannot be None {self.url}")

            # get hash files if they exist
            dissimilar_hashes_files = glob.glob(dissimilar_hash_file_path + "*.csv")

            # get all requests that we find
            perf_log_files = glob.glob(json_lists_path + os.sep + "*--cvwebrequests.json")
            outgoing_requests = []
            for f_path in perf_log_files:
                out_tmp = get_webrequests_from_perf_json(f_path)
                outgoing_requests += out_tmp

            return InitSiteFeedbackDockerResponse(main_path=main_path,
                                                  init_site_feedback_range=init_site_feedback_range,
                                                  outgoing_requests=list(set(outgoing_requests)),
                                                  perf_log_files=perf_log_files,
                                                  dissimilar_hash_files=dissimilar_hashes_files)
        else:
            logger.error("Could not read the init site feedback file, url: %s, file_path: %s", self.url,
                         stats_init_file_path)
            if self.cleanup_upon_error:
                shutil.rmtree(env_dir + os.sep + self.full_agent_name, ignore_errors=True)
            raise AutoFRException("Could not read the init site feedback file")


class FilterRulesDockerEnvRunner(DockerEnvRunner):
    """
    Given filter rules, use it along with visiting a Site
    """

    def __init__(self,
                 *args,
                 **kwargs):
        kwargs["DO_INITIAL_STATE_ONLY"] = False
        super(FilterRulesDockerEnvRunner, self).__init__(*args, **kwargs)
        self.FLG_AGENT = "agent_simple.py"
        self.docker_name = ONE_ITERATION_DOCKER_NAME

    def create_full_agent_name(self) -> str:
        return "with_blocking_" + clean_url_for_file(self.url) + self.unique_str

    def _prep_run(self):
        """
        For given block items and whitelist items, make them into filter lists.
        For web replay archive, make a copy.
        Pass all of them to docker env.
        """
        super(FilterRulesDockerEnvRunner, self)._prep_run()

        env_dir = self.get_env_output_path()

        # No matter where the filter list is,
        # copy it to right place to be read in later (so that docker can access it)
        if self.filter_list_path:
            new_filter_list_path = env_dir + os.sep + os.path.basename(self.filter_list_path)
            shutil.copyfile(self.filter_list_path, new_filter_list_path)
            self.files_to_remove.append(new_filter_list_path)

    def _run(self) -> CompletedProcess:
        docker_name = self.docker_name + self.docker_name_suffix
        docker_output_path = self.get_docker_output_path()
        # docker relative
        docker_blocks_items_path = None
        if self.filter_list_path:
            docker_blocks_items_path = docker_output_path + os.sep + os.path.basename(self.filter_list_path)

        return run_browser_docker_process(docker_name,
                                          FLG_AGENT=self.FLG_AGENT,
                                          FULL_AGENT_NAME=self.full_agent_name,
                                          URL=self.url,
                                          BLOCK_ITEMS_FILE_PATH=docker_blocks_items_path,
                                          OUTPUT_PATH=docker_output_path
                                          )

    def _post_run(self, completed_proc: CompletedProcess) -> DockerResponseBase:
        env_dir = self.get_env_output_path()
        main_path = env_dir + os.sep + self.full_agent_name
        stats_file_path = main_path + os.sep + STATS_FILE_NAME
        filter_lists_path = main_path + os.sep + FILTER_LISTS_DIR_NAME
        webrequests_lists_path = main_path + os.sep + JSON_DIR_NAME
        images_file_path = main_path + os.sep + VISIBLE_IMAGES_FILE_NAME
        textnodes_file_path = main_path + os.sep + VISIBLE_TEXTNODES_FILE_NAME

        images_records = None
        if os.path.isfile(images_file_path):
            df = pd.read_csv(images_file_path, index_col=False)
            images_records = df.to_dict('records')

        textnodes_records = None
        if os.path.isfile(textnodes_file_path):
            df_text = pd.read_csv(textnodes_file_path, index_col=False)
            textnodes_records = df_text.to_dict('records')

        if completed_proc.returncode == 0:
            # read in the stats file
            site_feedback = get_site_feedback_from_file(stats_file_path)
            filter_rules = []
            try:
                latest_file_path = get_file_from_path_by_key(filter_lists_path, "abp*.txt")
                filter_rules, _ = get_rules_from_filter_list(latest_file_path)
            except OSError as e:
                logger.warning("Could not find whitelist domains file from %s, %s", filter_lists_path, str(e))

            try:
                abp_hit_records_file_path = get_file_from_path_by_key(webrequests_lists_path,
                                                                      "*" + ABP_HITRECORDS_SUFFIX + ".json")
                with open(abp_hit_records_file_path, "r") as abp_file:
                    abp_hit_records_json = json.load(abp_file)
                    block_items_and_match = get_filter_records_by_rule(abp_hit_records_json)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("Could not find block_items_and_match file from %s, %s", webrequests_lists_path, str(e))
                block_items_and_match = dict()

            return SiteFeedbackFilterRulesDockerResponse(
                    site_feedback,
                    main_path=main_path,
                    filter_rules=filter_rules,
                    block_items_and_match=block_items_and_match,
                    images_records=images_records,
                    textnode_records=textnodes_records)
        else:
            err_msg = f"Could not get output {self.url}"
            logger.error(err_msg)

            if self.cleanup_upon_error:
                shutil.rmtree(env_dir + os.sep + self.full_agent_name, ignore_errors=True)
            raise DockerException(err_msg)


class AdgraphDockerEnvRunner (InitSiteFeedbackDockerEnvRunner):
    """
    Run AdGraph with Docker
    """
    def __init__(self,
                 *args, **kwargs):
        super(AdgraphDockerEnvRunner, self).__init__(*args, **kwargs)
        self.FLG_AGENT = "agent_adgraph.py"
        self.docker_name = get_adgraph_version().version

    def create_full_agent_name(self) -> str:
        return "init_adgraph_site_feedback_" + clean_url_for_file(self.url) + self.unique_str

    def _run(self) -> CompletedProcess:
        docker_name = self.docker_name + self.docker_name_suffix
        docker_output_path = self.get_docker_output_path()
        docker_blocks_items_path = None
        if self.filter_list_path:
            docker_blocks_items_path = docker_output_path + os.sep + os.path.basename(self.filter_list_path)

        return run_browser_docker_process(docker_name,
                                          FLG_AGENT=self.FLG_AGENT,
                                          FULL_AGENT_NAME=self.full_agent_name,
                                          URL=self.url,
                                          BLOCK_ITEMS_FILE_PATH=docker_blocks_items_path,
                                          DO_INITIAL_STATE_ONLY=str(self.DO_INITIAL_STATE_ONLY),
                                          INIT_STATE_ITERATIONS=self.INIT_STATE_ITERATIONS,
                                          OUTPUT_PATH=docker_output_path,
                                          SAVE_DISSIMILAR_HASHES=self.save_dissimilar_hashes,
                                          IS_NEW_ADGRAPH=get_adgraph_version().is_new_adgraph()
                                          )

    def _post_run(self, completed_proc: CompletedProcess) -> DockerResponseBase:
        """
        This should mirror AdgraphBrowserEnvRunner somewhat
        """
        docker_response = super(AdgraphDockerEnvRunner, self)._post_run(completed_proc)
        # read in the adgraph files
        adgraph_files = []
        input_dir = docker_response.main_path + os.sep + ADGRAPH_DIR
        # there should only be one large main file
        main_file_path = get_main_raw_adgraph_file_path(input_dir, self.url)
        if main_file_path:
            adgraph_files.append(main_file_path)

        docker_response.adgraph_files = adgraph_files
        docker_response.adgraph_files.sort()

        # read in the site snapshots
        snapshot_files = []
        input_dir = docker_response.main_path + os.sep + ADGRAPH_NETWORKX
        snapshot_files = glob.glob(input_dir + os.sep + "*.graphml")
        #logger.debug(f"found snapshotfiles in {input_dir}: {len(snapshot_files)}")
        docker_response.snapshot_files = snapshot_files
        docker_response.snapshot_files.sort()

        return docker_response

