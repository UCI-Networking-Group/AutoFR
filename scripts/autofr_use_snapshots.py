#!/usr/bin/python
import argparse
import logging
import os

import autofr.rl.action_space as action_space
import autofr.rl.controlled.bandits as bandits
from autofr.common.utils import clean_url_for_file, get_unique_str
from autofr.rl.action_space import DEFAULT_Q_VALUE, ActionSpace
from autofr.rl.browser_env.reward import RewardByCasesVer1, \
    RewardBase
from autofr.rl.controlled.bandits import DomainHierarchyMABControlled
from scripts.common.eval_utils import run_autofr_controlled_given_snapshots


def add_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    # REQUIRED
    parser.add_argument('--site_url',
                        required=True,
                        help='Site to test')
    parser.add_argument('--output_directory',
                        required=False,
                        default="temp_graphs",
                        help='output directory for saving agent')
    parser.add_argument('--snapshot_dir', required=True,
                        help='Path to already init files')
    # OPTIONAL
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
                        help='Threshold w: should be between 0 and 1')
    parser.add_argument('--iteration_threshold',
                        required=False,
                        type=int,
                        default=100,
                        help='Multiplier to how many iterations per round')
    parser.add_argument('--init_state_iterations',
                        required=False,
                        type=int,
                        default=10,
                        help='Number of times during init stage')
    parser.add_argument('--default_q_value', default=DEFAULT_Q_VALUE, type=float, required=False,
                        help='whether we do initializing only. New filter rules will be outputted')
    parser.add_argument('--reward_func_name', default=RewardByCasesVer1.get_classname(),
                        choices=[x.get_classname() for x in RewardBase.__subclasses__()],
                        type=str,
                        required=False,
                        help='Name of reward function')
    parser.add_argument('--bandit_klass_name', default=DomainHierarchyMABControlled.get_classname(),
                        choices=[x.get_classname() for x in DomainHierarchyMABControlled.__subclasses__()] + [DomainHierarchyMABControlled.get_classname()],
                        type=str,
                        required=False,
                        help='Name of bandit control class')
    parser.add_argument('--action_space_klass_name', default=ActionSpace.get_classname(),
                        choices=[x.get_classname() for x in ActionSpace.__subclasses__()] + [ActionSpace.get_classname()],
                        type=str,
                        required=False,
                        help='Name of action space class')
    parser.add_argument('--log_level', default="INFO", help='Log level')

    return parser


def main():
    parser = argparse.ArgumentParser(
        description='We run AutoFR-C using the site snapshots given.')

    parser = add_arguments(parser)

    args = parser.parse_args()
    print(args)

    do_init_only = False

    # create output directory
    dir_name = f"AutoFRGControlled_{clean_url_for_file(args.site_url)}_w{args.w_threshold}_c{args.confidence_ucb}_iter{args.iteration_threshold}_lr{args.gamma}_q{args.default_q_value}_{args.reward_func_name}"
    dir_name += "_" + get_unique_str()

    output_directory = args.output_directory + os.sep + dir_name
    if not os.path.isdir(output_directory):
        os.makedirs(output_directory, exist_ok=True)

    # set up logger
    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log_level)
    logging.root.handlers = []
    logging.basicConfig(
        handlers=[logging.FileHandler(output_directory + os.sep + "log.log", mode="w"), logging.StreamHandler()],
        format='%(asctime)s %(module)s - %(message)s', level=numeric_level)

    logger = logging.getLogger(__name__)

    # use gamma = None as 1/n
    gamma = None
    try:
        if args.gamma:
            gamma = float(args.gamma)
    except ValueError:
        pass

    bandit_klass = getattr(bandits, args.bandit_klass_name)
    action_space_klass = getattr(action_space, args.action_space_klass_name)

    env, results = run_autofr_controlled_given_snapshots(args.site_url,
                                          args.snapshot_dir,
                                          args.w_threshold,
                                          gamma,
                                          args.confidence_ucb,
                                          output_directory,
                                          logger,
                                          iteration_threshold=args.iteration_threshold,
                                          init_state_iterations=args.init_state_iterations,
                                          do_init_only=do_init_only,
                                          default_q_value=args.default_q_value,
                                          reward_func_name=args.reward_func_name,
                                          bandit_klass=bandit_klass,
                                          action_space_klass=action_space_klass)


    logger.info(
        f"Output dir: \n\t Filter rules saved at {env.output_directory}")

if __name__ == "__main__":
    main()
