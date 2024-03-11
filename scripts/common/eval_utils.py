import logging
import os
import typing

from autofr.common.utils import clean_url_for_file, get_unique_str
from autofr.rl.action_space import DEFAULT_Q_VALUE, ActionSpace
from autofr.rl.autofr_env import AutoFRResults
from autofr.rl.browser_env.reward import RewardByCasesVer1
from autofr.rl.controlled.agent import DomainHierarchyAgentControlled
from autofr.rl.controlled.autofr_env import AutoFRControlledEnvironment
from autofr.rl.controlled.bandits import DomainHierarchyMABControlled
from autofr.rl.policy import DomainHierarchyUCBPolicy

logger = logging.getLogger(__name__)

# Default values for running eval scripts
W_VALUE = 0.9
GAMMA = None
UCB_CONFIDENCE = 1.4
DOCKER_SUFFIX = ""
INIT_ITERATIONS = 10
AD_HIGHLIGHTER_EXT_PATH = os.path.expanduser("~") + os.sep + "github/rl_adblocking/ad_highlighter/perceptual-adblocker/"
BROWSER_BINARY_PATH = os.path.expanduser("~") + os.sep + "AdGraph-Ubuntu-16.04/chrome"
CHROME_DRIVER_PATH = os.path.expanduser("~") + os.sep + "adgraph_chrome_driver/chromedriver"
ITERATION_MULTIPLIER = 100
REWARD_FUNC = RewardByCasesVer1.get_classname()


def run_autofr_with_snapshots(site_url: str,
                              snapshot_directory: str,
                              output_directory: str,
                              log_level: str = str(logging.INFO),
                              do_init_only: bool = False,
                              w: float = W_VALUE,
                              bandit_klass: typing.Callable = DomainHierarchyMABControlled,
                              iteration_threshold: int = ITERATION_MULTIPLIER,
                              init_state_iterations: int = INIT_ITERATIONS,
                              default_q_value: float = DEFAULT_Q_VALUE,
                              reward_func_name: str = REWARD_FUNC,
                              gamma: typing.Optional[float] = GAMMA,
                              confidence_ucb: float = UCB_CONFIDENCE,
                              **kwargs) \
        -> typing.Tuple[AutoFRControlledEnvironment, AutoFRResults, str]:
    """
    Runs AutoFR Algorithm using snapshots
    """
    gamma_label = "1overN"
    if GAMMA:
        gamma_label = str(GAMMA)

    # create output directory
    dir_name = f"AutoFRGControlled_{clean_url_for_file(site_url)}_w{w}_" \
               f"c{UCB_CONFIDENCE}_iter{ITERATION_MULTIPLIER}_lr{gamma_label}_" \
               f"q{DEFAULT_Q_VALUE}_{REWARD_FUNC}_{get_unique_str()}"

    autofr_output_directory = output_directory + os.sep + dir_name
    if not os.path.isdir(autofr_output_directory):
        os.makedirs(autofr_output_directory, exist_ok=True)

    # set up logger
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % log_level)
    logging.root.handlers = []
    logging.basicConfig(
        handlers=[logging.FileHandler(autofr_output_directory + os.sep + "log.log", mode="w"),
                  logging.StreamHandler()],
        format='%(asctime)s %(processName)s %(threadName)s %(module)s - %(message)s', level=numeric_level)
    logger = logging.getLogger(__name__)

    autofr_env, results = run_autofr_controlled_given_snapshots(site_url,
                                                                snapshot_directory,
                                                                w,
                                                                gamma,
                                                                confidence_ucb,
                                                                autofr_output_directory,
                                                                logger,
                                                                iteration_threshold=iteration_threshold,
                                                                init_state_iterations=init_state_iterations,
                                                                do_init_only=do_init_only,
                                                                default_q_value=default_q_value,
                                                                reward_func_name=reward_func_name,
                                                                destroy=False,
                                                                bandit_klass=bandit_klass,
                                                                **kwargs)

    return autofr_env, results, autofr_output_directory


def run_autofr_controlled_given_snapshots(site_url: str,
                                          init_dir: str,
                                          w_threshold: float,
                                          gamma: float,
                                          confidence_ucb: float,
                                          output_directory: str,
                                          logger: logging.Logger,
                                          docker_name_suffix: str = "",
                                          iteration_threshold: int = 10,
                                          init_state_iterations: int = 10,
                                          do_init_only: bool = False,
                                          default_q_value: float = DEFAULT_Q_VALUE,
                                          reward_func_name: str = RewardByCasesVer1.get_classname(),
                                          destroy: bool = True,
                                          choose_snapshot_random: bool = True,
                                          use_snapshot_cache: bool = False,
                                          agent_klass: typing.Callable = DomainHierarchyAgentControlled,
                                          autofrg_env_klass: typing.Callable = AutoFRControlledEnvironment,
                                          bandit_klass: typing.Callable = DomainHierarchyMABControlled,
                                          action_space_klass: typing.Callable = ActionSpace,
                                          ) \
        -> typing.Tuple[AutoFRControlledEnvironment, AutoFRResults]:
    base_name = os.path.basename(output_directory)

    bandit = bandit_klass(init_dir, docker_name_suffix,
                          w_threshold,
                          base_name=base_name,
                          reward_func_name=reward_func_name,
                          choose_snapshot_random=choose_snapshot_random,
                          use_snapshot_cache=use_snapshot_cache)

    policy = DomainHierarchyUCBPolicy(confidence_level=confidence_ucb)
    agent = agent_klass(bandit,
                        policy=policy,
                        gamma=gamma,
                        output_directory=output_directory,
                        default_q_value=default_q_value,
                        action_space_class=action_space_klass)

    env = autofrg_env_klass(site_url, bandit, agent,
                            iteration_threshold=iteration_threshold,
                            output_directory=output_directory,
                            do_init_only=do_init_only)

    # logger.debug(f"Running experiment for {site_url}")
    results = env.run(init_state_iterations=init_state_iterations)

    if destroy:
        env.destroy(data=True, rules=False)

    return env, results
