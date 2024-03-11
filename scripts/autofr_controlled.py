#!/usr/bin/python
import argparse
import logging
import os
import subprocess
import time

import numpy as np
from selenium.common.exceptions import WebDriverException

import autofr.rl.action_space as action_space
import autofr.rl.controlled.bandits as bandits
from autofr.common.exceptions import AutoFRException
from autofr.common.utils import clean_url_for_file, get_unique_str
from autofr.rl.action_space import DEFAULT_Q_VALUE, CHUNK_LIST_THRESHOLD, ActionSpace
from autofr.rl.agent import DomainHierarchyAgent
from autofr.rl.browser_env.reward import RewardByCasesVer1, RewardBase
from autofr.rl.controlled.autofr_env import AutoFRControlledEnvironment
from autofr.rl.controlled.bandits import DomainHierarchyMABControlled, AutoFRMultiArmedBanditGetSnapshots
from autofr.rl.policy import DomainHierarchyUCBPolicy
from scripts.common.eval_utils import run_autofr_with_snapshots, \
    AD_HIGHLIGHTER_EXT_PATH, BROWSER_BINARY_PATH, CHROME_DRIVER_PATH, INIT_ITERATIONS

logger = logging.getLogger(__name__)


def setup_and_run_env(site_url: str,
                      output_directory: str,
                      logger: logging.Logger,
                      ad_highlighter_ext_path: str,
                      browser_path: str,
                      chrome_driver_path: str,
                      init_state_iterations: int = 10,
                      chunk_threshold: int = CHUNK_LIST_THRESHOLD,
                      do_init_only: bool = True,
                      filter_list_path: str = None,
                      zip_output: bool = True,
                      destroy_output: bool = True) -> AutoFRControlledEnvironment:
    reward_func_name: str = RewardByCasesVer1.get_classname()
    base_name = os.path.basename(output_directory)

    bandit = AutoFRMultiArmedBanditGetSnapshots(
        ad_highlighter_ext_path, "", 0.9,
        browser_path=browser_path,
        chrome_driver_path=chrome_driver_path,
        base_name=base_name,
        reward_func_name=reward_func_name,
        chunk_threshold=chunk_threshold
    )

    policy = DomainHierarchyUCBPolicy()
    agent = DomainHierarchyAgent(bandit,
                                 policy=policy,
                                 output_directory=output_directory)

    env = AutoFRControlledEnvironment(site_url, bandit, agent,
                                      output_directory=output_directory,
                                      do_init_only=do_init_only)

    logger.info(f"Finding {init_state_iterations} SiteSnapshots for {site_url} only")
    env.run_init_state_only(init_state_iterations=init_state_iterations,
                            filter_list_path=filter_list_path)
    if zip_output:
        env.zip_output()
    if destroy_output:
        env.destroy()

    return env


def get_snapshots(site_url: str,
                  output_directory: str,
                  filter_list_path: str = None,
                  init_state_iterations: int = INIT_ITERATIONS,
                  chunk_threshold: int = CHUNK_LIST_THRESHOLD,
                  log_level: str = str(logging.INFO)) \
        -> AutoFRControlledEnvironment:
    """
    Gets the snapshots
    Returns the Environment and the snapshot output directory
    """
    # create output directory
    dir_name = f"AutoFRGControlled_{clean_url_for_file(site_url)}_AdGraph_Snapshots_{get_unique_str()}"

    snapshot_output_directory = output_directory + os.sep + dir_name
    if not os.path.isdir(snapshot_output_directory):
        os.makedirs(snapshot_output_directory, exist_ok=True)

    # set up logger
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % log_level)
    logging.root.handlers = []
    logging.basicConfig(
        handlers=[logging.FileHandler(snapshot_output_directory + os.sep + "log.log", mode="w"),
                  logging.StreamHandler()],
        format='%(asctime)s %(processName)s %(threadName)s %(module)s - %(message)s', level=numeric_level)

    env = setup_and_run_env(site_url,
                            snapshot_output_directory,
                            logger,
                            AD_HIGHLIGHTER_EXT_PATH,
                            BROWSER_BINARY_PATH,
                            CHROME_DRIVER_PATH,
                            init_state_iterations=init_state_iterations,
                            do_init_only=True,
                            filter_list_path=filter_list_path,
                            zip_output=False,
                            destroy_output=False,
                            chunk_threshold=chunk_threshold)
    return env


def main():
    parser = argparse.ArgumentParser(
        description='We run AutoFR-C.')

    # REQUIRED
    parser.add_argument('--site_url',
                        required=True,
                        help='Site to test')
    parser.add_argument('--output_directory',
                        required=False,
                        default="temp_graphs",
                        help='output directory for saving agent')
    # OPTIONAL
    parser.add_argument('--chunk_threshold',
                        type=int,
                        default=CHUNK_LIST_THRESHOLD,
                        required=False,
                        help='How many times at once we will spawn a browser instance (reduce this number if your machine cannot handle many parallel processes)')
    parser.add_argument('--gamma',
                        type=str,
                        required=False,
                        help='How much do we care about future rewards. '
                             'Default is 1/n. If passed in, it will be treated as a float value')
    parser.add_argument('--confidence_ucb',
                        type=float,
                        default=1.4,
                        required=False,
                        help='Confidence level for UCB calculation')
    parser.add_argument('--w_threshold',
                        type=float,
                        default=0.9,
                        required=False,
                        help='Preference to avoid visual breakage. Between 0 and 1, use number closer to 1 if you really care about avoiding breakage.')
    parser.add_argument('--iteration_threshold',
                        required=False,
                        type=int,
                        default=100,
                        help='Multiplier to how many iterations per round')
    parser.add_argument('--init_state_iterations',
                        required=False,
                        type=int,
                        default=10,
                        help='Number of site snapshots required for AutoFR to run (reduce this number if the process cannot detect ads easily for the website)')
    parser.add_argument('--default_q_value', default=DEFAULT_Q_VALUE, type=float, required=False,
                        help='whether we do initializing only. New filter rules will be outputted')
    parser.add_argument('--reward_func_name', default=RewardByCasesVer1.get_classname(),
                        choices=[x.get_classname() for x in RewardBase.__subclasses__()],
                        type=str,
                        required=False,
                        help='Name of reward function')
    parser.add_argument('--bandit_klass_name', default=DomainHierarchyMABControlled.get_classname(),
                        choices=[x.get_classname() for x in DomainHierarchyMABControlled.__subclasses__()] + [
                            DomainHierarchyMABControlled.get_classname()],
                        type=str,
                        required=False,
                        help='Name of bandit control class')
    parser.add_argument('--action_space_klass_name', default=ActionSpace.get_classname(),
                        choices=[x.get_classname() for x in ActionSpace.__subclasses__()] + [
                            ActionSpace.get_classname()],
                        type=str,
                        required=False,
                        help='Name of action space class')
    parser.add_argument('--log_level', default="INFO", help='Log level')
    args = parser.parse_args()
    print(args)

    bandit_klass = getattr(bandits, args.bandit_klass_name)
    action_space_klass = getattr(action_space, args.action_space_klass_name)

    # use gamma = None as 1/n
    gamma = None
    try:
        if args.gamma:
            gamma = float(args.gamma)
    except ValueError:
        pass

    site_url = args.site_url

    try:
        # Get snapshots
        before_snapshot = time.time()
        snapshot_env = get_snapshots(site_url,
                                     args.output_directory,
                                     init_state_iterations=args.init_state_iterations,
                                     log_level=args.log_level,
                                     chunk_threshold=args.chunk_threshold)
        snapshot_directory = snapshot_env.bandit.get_base_data_dir()
        snapshot_time_sec = int(time.time() - before_snapshot)

        # Run AutoFR with snapshots
        autofr_env, results, autofr_dir = run_autofr_with_snapshots(site_url,
                                                                    snapshot_directory,
                                                                    args.output_directory,
                                                                    iteration_threshold=args.iteration_threshold,
                                                                    init_state_iterations=args.init_state_iterations,
                                                                    w=args.w_threshold,
                                                                    default_q_value=args.default_q_value,
                                                                    confidence_ucb=args.confidence_ucb,
                                                                    log_level=args.log_level,
                                                                    bandit_klass=bandit_klass,
                                                                    action_space_klass=action_space_klass,
                                                                    reward_func_name=args.reward_func_name,
                                                                    gamma=gamma)
        autofr_env.destroy(rules=False)
        autofr_time_sec = int(np.average(results.time_per_experiment) + results.time_init_experiment)

        init_site_feedback = autofr_env.bandit.init_site_feedback
        site_snapshots_count = len(autofr_env.bandit.site_snapshots)
        # logger.debug(f"Baseline site feedback of {site_url} is {init_site_feedback}")
        logger.info(
            f"Collecting {site_snapshots_count} snapshots took {snapshot_time_sec} sec, AutoFR experiment took {autofr_time_sec} sec")
        logger.info(
            f"\nOutput dir:\n\tSnapshots saved at {snapshot_directory}\n\tFilter rules saved at {autofr_env.output_directory}")
    except (WebDriverException, AutoFRException, OSError, subprocess.CalledProcessError) as e:
        logger.warning(f"Could not process {site_url}", exc_info=True)
    except Exception as e:
        logger.warning(f"Unexpected exception", exc_info=True)


if __name__ == "__main__":
    main()
