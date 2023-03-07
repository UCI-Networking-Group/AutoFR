import concurrent.futures
import logging
import os.path
import shutil
import typing

from selenium.common.exceptions import WebDriverException

from autofr.common.docker_utils import HOST_MACHINE_OUTPUT_PATH, InitSiteFeedbackDockerResponse, \
    SiteFeedbackFilterRulesDockerResponse
from autofr.common.exceptions import InvalidSiteFeedbackException, AutoFRException
from autofr.common.filter_rules_utils import create_tmp_filter_list
from autofr.common.utils import chunk_list
from autofr.rl.action_space import CHUNK_LIST_THRESHOLD
from autofr.rl.base import MultiArmedBandit
from autofr.rl.browser_env.reward import SiteFeedback, SiteFeedbackRange, \
    get_reward_klass, RewardByCasesVer1, RewardTerms
from autofr.rl.browser_env.runner.docker_env_runner import InitSiteFeedbackDockerEnvRunner, \
    FilterRulesDockerEnvRunner

logger = logging.getLogger(__name__)


class AutoFRMultiArmedBandit(MultiArmedBandit):
    """
    This bandit does not know any action values.
    It merely executes the action and returns the reward.
    """

    def __init__(self,
                 docker_name_suffix: str,
                 w_threshold: float,
                 init_site_feedback: SiteFeedback = None,
                 init_site_feedback_range: SiteFeedbackRange = None,
                 base_name: str = None,
                 chunk_threshold: int = CHUNK_LIST_THRESHOLD,
                 reward_func_name: str = RewardByCasesVer1.get_classname()):
        super().__init__(1)
        self.optimal_ad_counter = 0
        self.docker_name_suffix = docker_name_suffix
        self.w_threshold = w_threshold
        self.init_site_feedback = init_site_feedback
        self.init_site_feedback_range = init_site_feedback_range
        self.optimal_actions = []
        self.base_name = base_name
        self.chunk_threshold = chunk_threshold
        self.reward_func_name = reward_func_name

    @classmethod
    def get_classname(cls):
        return cls.__name__

    def __str__(self):
        return f"w={self.w_threshold}"

    def reset(self):
        self.optimal_actions.clear()

    def get_base_data_dir(self) -> str:
        return HOST_MACHINE_OUTPUT_PATH + os.sep + self.base_name

    def destroy(self):
        data_dir = self.get_base_data_dir()
        if os.path.isdir(data_dir):
            #logger.debug(f"{self.__class__.__name__}: Deleting {data_dir}")
            shutil.rmtree(data_dir)

    def set_init_site_feedback(self, site_feedback: SiteFeedback):
        self.init_site_feedback = site_feedback

    def set_optimal_actions(self, actions: list):
        # make optimal condition
        self.optimal_actions = actions

    def set_init_state_range(self, state_range: SiteFeedbackRange):
        self.init_site_feedback_range = state_range

    def is_optimal(self, action: typing.Any) -> bool:
        if isinstance(action, list):
            return action == self.optimal_actions

        return action in self.optimal_actions

    def get_reward(self, site_feedback: SiteFeedback) -> RewardTerms:
        reward_base = get_reward_klass(self.reward_func_name)
        return reward_base(self.init_site_feedback, site_feedback, self.w_threshold).calculate()

    def create_init_runner(self, url: str,
                           INIT_STATE_ITERATIONS: int = 1,
                           filter_list_path: str = None,
                           use_docker: bool = True) -> InitSiteFeedbackDockerEnvRunner:
        return InitSiteFeedbackDockerEnvRunner(url, docker_name_suffix=self.docker_name_suffix,
                                               base_name=self.base_name,
                                               DO_INITIAL_STATE_ONLY=True,
                                               INIT_STATE_ITERATIONS=INIT_STATE_ITERATIONS,
                                               filter_list_path=filter_list_path
                                               )

    def create_runner(self,
                      filter_list_path: str,
                      url: str
                      ):
        return FilterRulesDockerEnvRunner(url,
                                          filter_list_path=filter_list_path,
                                          docker_name_suffix=self.docker_name_suffix,
                                          base_name=self.base_name,
                                          DO_INITIAL_STATE_ONLY=False
                                          )

    def find_initial_state_no_executor(self,
                                       url,
                                       init_state_iterations: int = 10,
                                       rounds_per_driver: int = 1,
                                       ignore_states_with_zero_ads: bool = True,
                                       filter_list_path: str = None,
                                       ) -> InitSiteFeedbackDockerResponse:

        execute_done_count = 0
        execute_done_count_no_ads = 0
        docker_response_main = InitSiteFeedbackDockerResponse()
        max_try_threshold = 2 * init_state_iterations

        # try multiple times to get states that have ads in them
        while (execute_done_count < init_state_iterations and
               execute_done_count + execute_done_count_no_ads < max_try_threshold):

            if execute_done_count > 0:
                logger.warning("Trying again to find more init states with ads")

            for chunk_actions in chunk_list(list(range(init_state_iterations - execute_done_count)), self.chunk_threshold):
                #logger.debug("Processing %s", str(chunk_actions))
                for action in chunk_actions:
                    browser_env = self.create_init_runner(url,
                                                          INIT_STATE_ITERATIONS=rounds_per_driver,
                                                          filter_list_path=filter_list_path,
                                                          use_docker=True)

                    #logger.debug(f"getting init state url: {url}, {browser_env.full_agent_name}")
                    should_skip = False

                    try:
                        docker_response = browser_env.get()
                    except (AutoFRException, WebDriverException) as e:
                        logger.warning(f"Could not get init site feedback {repr(e)} {e}")
                        should_skip = True
                        execute_done_count_no_ads += 1
                    else:
                        # should we skip zero ads states?
                        if ignore_states_with_zero_ads and docker_response:
                            ag = docker_response.init_site_feedback_range.get_average()
                            if not ag or (ag and ag.ad_counter == 0):
                                should_skip = True
                                execute_done_count_no_ads += 1
                                logger.warning("Skipping the init state since no ads were found")
                                shutil.rmtree(docker_response.main_path)

                        # every time we get a viable snapshot, we increment the max_tries
                        if not should_skip:
                            execute_done_count += 1
                            max_try_threshold += 4
                            if execute_done_count <= init_state_iterations:
                                docker_response_main.update_with_docker_response(docker_response)
                            else:
                                browser_env.destroy()
                    finally:
                        if should_skip:
                            # if we do not need it, destroy it
                            browser_env.destroy()


                #logger.debug("Done with one chunk, current results count: %d" % execute_done_count)

                # if we want states with ads > 0, then see if we have enough already, then break
                if ignore_states_with_zero_ads and execute_done_count >= init_state_iterations:
                    break

            # if we are ok with zero ads, then stop
            if not ignore_states_with_zero_ads and \
                    execute_done_count + execute_done_count_no_ads >= init_state_iterations:
                break

        #logger.info("Care about ad init states only %s, results with ads %d, results with no ads %d",
        #            str(ignore_states_with_zero_ads), execute_done_count, execute_done_count_no_ads)

        if execute_done_count == 0:
            raise InvalidSiteFeedbackException("Could not find init site snapshot")

        if execute_done_count < init_state_iterations:
            logger.warning(f"Expected {init_state_iterations} init states but got {execute_done_count}")

        # keep the state that has larger than 0 ad counter
        if ignore_states_with_zero_ads:
            docker_response_main.init_site_feedback_range.site_feedbacks = [x for x in
                                                                            docker_response_main.init_site_feedback_range.site_feedbacks
                                                                            if x.ad_counter > 0]

        docker_response_main.sort()
        return docker_response_main

    def find_initial_state(self,
                           url,
                           init_state_iterations: int = 10,
                           rounds_per_driver: int = 1,
                           ignore_states_with_zero_ads: bool = True,
                           filter_list_path: str = None,
                           ) -> InitSiteFeedbackDockerResponse:

        execute_done_count = 0
        execute_done_count_no_ads = 0
        docker_response_main = InitSiteFeedbackDockerResponse()
        max_try_threshold = 2 * init_state_iterations
        consecutive_no_ads = 0
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_info = {}

            # try multiple times to get states that have ads in them
            while (execute_done_count < init_state_iterations and
                   execute_done_count + execute_done_count_no_ads < max_try_threshold):

                if execute_done_count > 0:
                    logger.warning("Trying again to find more init states with ads")

                for chunk_actions in chunk_list(list(range(init_state_iterations - execute_done_count)), self.chunk_threshold):
                    future_to_info.clear()
                    #logger.debug("Processing %s", str(chunk_actions))
                    action_to_env = dict()
                    for action in chunk_actions:
                        browser_env = self.create_init_runner(url,
                                                              INIT_STATE_ITERATIONS=rounds_per_driver,
                                                              filter_list_path=filter_list_path,
                                                              use_docker=True)

                        #logger.debug(f"getting init state url: {url}, {browser_env.full_agent_name}")

                        future = executor.submit(browser_env.get)

                        future_to_info[future] = action
                        action_to_env[str(action)] = browser_env

                    for future in concurrent.futures.as_completed(future_to_info):
                        unique_action = future_to_info[future]
                        docker_response: InitSiteFeedbackDockerResponse = None
                        try:
                            docker_response = future.result()
                            #logger.info(str(docker_response))
                        except (OSError, WebDriverException, AutoFRException) as e:
                            logger.warning(f"{unique_action} get_init_state: generated an exception: {repr(e)} {e}")
                            should_skip = True
                            execute_done_count_no_ads += 1
                        else:
                            should_skip = False
                            # should we skip zero ads states?
                            if ignore_states_with_zero_ads and docker_response is not None:
                                ag = docker_response.init_site_feedback_range.get_average()
                                if not ag or (ag and ag.ad_counter == 0):
                                    should_skip = True
                                    execute_done_count_no_ads += 1
                                    logger.warning("Skipping the init state since no ads were found")
                                    consecutive_no_ads += 1
                            if not should_skip:
                                execute_done_count += 1
                                consecutive_no_ads = 0
                                max_try_threshold += 4
                                if execute_done_count <= init_state_iterations:
                                    docker_response_main.update_with_docker_response(docker_response)
                                elif action_to_env.get(str(unique_action)):
                                    env_tmp = action_to_env.get(str(unique_action))
                                    env_tmp.destroy()
                        finally:
                            if should_skip and action_to_env.get(str(unique_action)):
                                env_tmp = action_to_env.get(str(unique_action))
                                env_tmp.destroy()

                    #logger.debug("Done with one chunk, current results count: %d" % execute_done_count)

                    # if we want states with ads > 0, then see if we have enough already, then break
                    if ignore_states_with_zero_ads and execute_done_count >= init_state_iterations:
                        break

                # if we want states with ads > 0, give up if three times there are no ads
                if ignore_states_with_zero_ads and consecutive_no_ads == 6:
                    break

                # if we are ok with zero ads, then stop
                if not ignore_states_with_zero_ads:
                    break

            #logger.info("Care about ad init states only %s, results with ads %d, results with no ads %d",
            #            str(ignore_states_with_zero_ads), execute_done_count, execute_done_count_no_ads)

        if execute_done_count < init_state_iterations:
            raise InvalidSiteFeedbackException(
                f"Expected {init_state_iterations} init states but got {execute_done_count}")

        # keep the state that has larger than 0 ad counter
        if ignore_states_with_zero_ads:
            docker_response_main.init_site_feedback_range.site_feedbacks = [x for x in
                                                                            docker_response_main.init_site_feedback_range.site_feedbacks
                                                                            if x.ad_counter > 0]

        docker_response_main.sort()
        return docker_response_main

    def pull_each_arm_parallel(self, url: str, actions: list,
                               **kwargs) -> list:
        """
        Pull each arm. Note that actions can be a list of list
        Returns list of DockerResponseBase
        """
        results = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_info = {}

            for chunk_actions in chunk_list(actions, self.chunk_threshold):
                future_to_info.clear()
                #logger.debug("Processing %s", str(chunk_actions))

                for action in chunk_actions:
                    future = executor.submit(self.pull,
                                             url,
                                             action,
                                             **kwargs)

                    future_to_info[future] = action

                for future in concurrent.futures.as_completed(future_to_info):
                    action_tmp = future_to_info[future]
                    try:
                        response: SiteFeedbackFilterRulesDockerResponse = future.result()
                    except (OSError, WebDriverException, AutoFRException) as e:
                        logger.warning(f"{action_tmp} get_site_feedback_by_blocking: generated an exception: {repr(e)} {e}")
                    else:
                        results.append(response)

                #logger.debug("Done with one chunk, current results count: %d" % len(results))

        return results

    def pull(self, url: str,
             actions: list,
             **kwargs) -> SiteFeedbackFilterRulesDockerResponse:
        """
            Do the action by starting a docker instance
        """
        filter_list_path = create_tmp_filter_list(action_domains=actions)

        env_runner = self.create_runner(filter_list_path, url, **kwargs)
        response: SiteFeedbackFilterRulesDockerResponse = env_runner.get()

        # clean up
        if os.path.isfile(filter_list_path):
            os.remove(filter_list_path)

        response.reward = self.get_reward(response.site_feedback)
        response.is_optimal = self.is_optimal(actions)
        response.action = actions

        return response

