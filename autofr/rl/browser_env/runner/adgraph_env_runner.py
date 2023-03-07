import glob
import os
from subprocess import CompletedProcess

from selenium.common.exceptions import WebDriverException

from autofr.common.docker_utils import DockerResponseBase
from autofr.common.filter_rules_utils import get_rules_from_filter_list
from autofr.common.utils import clean_url_for_file
from autofr.rl.browser_env.browser_adgraph_env import ADGRAPH_DIR, AdgraphBrowserWithAdHighlighter
from autofr.rl.browser_env.runner.browser_env_runner import InitSiteFeedbackBrowserEnvRunner, logger
from autofr.rl.controlled.site_snapshot import ADGRAPH_NETWORKX, get_main_raw_adgraph_file_path


class AdgraphBrowserEnvRunner(InitSiteFeedbackBrowserEnvRunner):
    """
    Run the BrowserEnv without Docker with Adgraph (but still goes to the site)
    """

    def __init__(self,
                 *args, **kwargs):
        super(AdgraphBrowserEnvRunner, self).__init__(*args, **kwargs)
        self.FLG_AGENT = "agent_adgraph.py"

    def create_full_agent_name(self) -> str:
        return "init_adgraph_site_feedback_" + clean_url_for_file(self.url) + self.unique_str

    def _post_run(self, completed_proc: CompletedProcess) -> DockerResponseBase:
        docker_response = super(AdgraphBrowserEnvRunner, self)._post_run(completed_proc)
        # read in the raw adgraph files
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

    def _run(self) -> CompletedProcess:
        process = CompletedProcess([], returncode=0)
        env = None
        try:
            filter_rules = None
            whitelist_filter_rules = None
            if self.filter_list_path:
                filter_rules, whitelist_filter_rules = get_rules_from_filter_list(self.filter_list_path)

            logger.debug(f"Number of rules being tested: {len(filter_rules or [])} from {self.filter_list_path}")

            env = AdgraphBrowserWithAdHighlighter(self.url,
                                                  self.adblock_proxy_path,
                                                  self.ad_highlighter_ext_path, self.get_docker_output_path(),
                                                  agent_name=self.full_agent_name, wait_time=30,
                                                  do_initial_state_only=self.DO_INITIAL_STATE_ONLY,
                                                  init_state_iterations=self.INIT_STATE_ITERATIONS,
                                                  chrome_driver_path=self.chrome_driver_path,
                                                  browser_path=self.browser_path,
                                                  adblock_ext_path=self.adblock_ext_path if filter_rules or whitelist_filter_rules else None,
                                                  current_filter_rules=filter_rules,
                                                  whitelist_rules=whitelist_filter_rules
                                                  )

            env.init_drivers_and_dirs()
            env.get_init_site_feedback()
        except WebDriverException:
            logger.warning(f"Could not get init snapshot for {self.url}", exc_info=True)
            process.return_code = -1
        finally:
            if env:
                env.clean_up()

        return process


class AdgraphBrowserFromDirEnvRunner(AdgraphBrowserEnvRunner):
    """
    Run the BrowserEnv without Docker with Adgraph, read from directory
    This does not visit the site
    """

    def __init__(self,
                 init_adgraph_dir,
                 *args, **kwargs):
        super(AdgraphBrowserFromDirEnvRunner, self).__init__(*args, **kwargs)
        self.init_adgraph_dir = init_adgraph_dir
        # don't clean up, since we do not want to alter the init_graph_dir
        self.cleanup_upon_error = False
        # build dirs based off the init_adgraph_dir
        self.full_agent_name = os.path.basename(self.init_adgraph_dir)
        tmp_dir = self.init_adgraph_dir.replace(self.full_agent_name, "").rstrip(os.sep)
        self.base_name = os.path.basename(tmp_dir)
        tmp_dir = tmp_dir.replace(self.base_name, "").rstrip(os.sep)
        self.OUTPUT_PATH = os.path.basename(tmp_dir)

    def get_env_output_path(self) -> str:
        """
        Builds the top level path of the env runner (without the full agent name)
        """

        return self.init_adgraph_dir.replace(self.full_agent_name, "").rstrip(os.sep)

    def get_docker_output_path(self) -> str:
        return self.OUTPUT_PATH + os.sep + self.base_name

    def _run(self) -> CompletedProcess:
        """
        Fake the run, since it has already been done
        """
        process = CompletedProcess([], returncode=0)
        return process
