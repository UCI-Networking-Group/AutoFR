import logging
import os
import shutil
import typing

from autofr.common.docker_utils import InitSiteFeedbackDockerResponse
from autofr.rl.action_space import SLEEPING_ARM, UNKNOWN_ARM, TYPE
from autofr.rl.autofr_env import AutoFREnvironment, AutoFRResults
from autofr.rl.browser_env.reward import SiteFeedbackRange
from autofr.rl.controlled.agent import DomainHierarchyAgentControlled

logger = logging.getLogger(__name__)


class AutoFRControlledEnvironment(AutoFREnvironment):

    def __init__(self, *args, **kwargs):
        super(AutoFRControlledEnvironment, self).__init__(*args, **kwargs)
        self.save_time = 1000
        # let the bandit have access to the action space
        self.bandit.action_space = self.main_agent.action_space

    def end_experiment(self):
        super(AutoFRControlledEnvironment, self).end_experiment()
        self.bandit.save_cache()
        #if isinstance(self.main_agent, DomainHierarchyAgentControlled):
        #    self.main_agent.save_iframe_rules()

    def _remove_unknown_arms(self, response: InitSiteFeedbackDockerResponse):
        """
        For controlled env, we only look at the snapshots for unknown arms.
        Arms must appear in all site snapshots, else they are unknown
        """
        unknown_arms = []
        for arm in self.main_agent.current_arms:
            node_type = self.main_agent.action_space.get(arm)[TYPE]
            for ss, ss_name in self.bandit.site_snapshots:
                if not ss.has_url_variation_in_graph(arm, node_type):
                    unknown_arms.append(arm)
                    break

        for arm in unknown_arms:
            self.main_agent.action_space.get(arm)[SLEEPING_ARM] = True
            self.main_agent.action_space.get(arm)[UNKNOWN_ARM] = True
            self.main_agent.current_arms.remove(arm)

    def _remove_unknown_arms_ver2(self, response: InitSiteFeedbackDockerResponse):
        """
        For controlled env, we only look at the snapshots for unknown arms.
        Arms must appear in at least one site snapshots, else they are unknown
        """
        unknown_arms = []
        for arm in self.main_agent.current_arms:
            node_type = self.main_agent.action_space.get(arm)[TYPE]
            found = False
            for ss, ss_name in self.bandit.site_snapshots:
                if ss.has_url_variation_in_graph(arm, node_type):
                    found = True
                    break
            if not found:
                unknown_arms.append(arm)
                #logger.info(f"_remove_unknown_arms_ver2: removing arm because it does not appear in any site snapshot {arm}")

        for arm in unknown_arms:
            self.main_agent.action_space.get(arm)[SLEEPING_ARM] = True
            self.main_agent.action_space.get(arm)[UNKNOWN_ARM] = True
            self.main_agent.current_arms.remove(arm)

    def run_init_state_only(self,
                            init_state_iterations: int = 1,
                            ignore_states_with_zero_ads: bool = True,
                            check_valid_state_range: bool = True,
                            save_raw_initiator_chain: bool = True,
                            filter_list_path: str = None
                            ) -> InitSiteFeedbackDockerResponse:
        docker_response = super(AutoFRControlledEnvironment, self).run_init_state_only(
            init_state_iterations=init_state_iterations,
            ignore_states_with_zero_ads=ignore_states_with_zero_ads,
            check_valid_state_range=check_valid_state_range,
            save_raw_initiator_chain=save_raw_initiator_chain,
            filter_list_path=filter_list_path)
        # make bandit process adgraph files
        self.bandit.adgraph_files = docker_response.adgraph_files
        # if there are processed snapshots, then copy them to the top-level of the bandit's ADGRAPH_NETWORKX folder
        if docker_response.snapshot_files:
            for snapshot_file in docker_response.snapshot_files:
                shutil.copyfile(snapshot_file,
                                self.bandit.get_base_site_snapshots_dir() + os.sep + os.path.basename(snapshot_file))
        self.bandit.prepare_site_snapshots(self.url)
        return docker_response

