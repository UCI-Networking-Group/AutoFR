import logging
import os
import subprocess
from subprocess import CompletedProcess

from autofr.rl.browser_env.runner.docker_env_runner import InitSiteFeedbackDockerEnvRunner

logger = logging.getLogger(__name__)


class InitSiteFeedbackBrowserEnvRunner (InitSiteFeedbackDockerEnvRunner):
    """
    Run the InitSiteFeedbackDockerEnvRunner without Docker
    """
    def __init__(self,
                 ad_highlighter_ext_path: str,
                 *args,
                 browser_path: str = None,
                 chrome_driver_path: str = None,
                 adblock_proxy_path: str = None,
                 adblock_ext_path: str = None,
                 path_to_agents: str = None,
                 filter_list_path: str = None,
                 **kwargs):
        super(InitSiteFeedbackBrowserEnvRunner, self).__init__(*args, **kwargs)
        self.ad_highlighter_ext_path = os.path.abspath(ad_highlighter_ext_path)
        self.browser_path = browser_path
        self.chrome_driver_path = chrome_driver_path
        self.adblock_proxy_path = os.path.abspath(adblock_proxy_path or os.path.abspath("framework-with-ad-highlighter/abp_proxy/"))
        self.path_to_agents = path_to_agents or os.path.abspath("framework-with-ad-highlighter")
        self.adblock_ext_path = adblock_ext_path or os.path.abspath("../adblockpluschrome/devenv.chrome/")
        self.filter_list_path = filter_list_path

    def _run(self) -> CompletedProcess:

        params = ["python", self.path_to_agents + os.sep + self.FLG_AGENT,
                  "--downloads_path", self.get_docker_output_path(),
                  "--url", self.url,
                  "--adblock_proxy_path", self.adblock_proxy_path,
                  "--ad_highlighter_ext_path", self.ad_highlighter_ext_path,
                  "--browser_path", self.browser_path,
                  "--chrome_driver_path", self.chrome_driver_path,
                  "--agent_name", self.full_agent_name,
                  "--adblock_ext_path", self.adblock_ext_path]

        if self.filter_list_path:
            params += ["--block_items_path", self.filter_list_path]

        #logger.debug(f"params: {params}")
        process = subprocess.run(params,
                                 stdout=subprocess.PIPE,
                                 universal_newlines=True)
        return process
