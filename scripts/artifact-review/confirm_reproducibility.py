#!/usr/bin/python
import argparse
import glob
import logging
import os
import shutil
import pandas as pd

from autofr.common.filter_rules_utils import get_rules_from_filter_list, RULES_DELIMITER
from autofr.common.utils import clean_url_for_file, get_unique_str
from autofr.rl.action_space import DEFAULT_Q_VALUE, ActionSpace
from autofr.rl.controlled.bandits import DomainHierarchyMABControlled
from autofr.rl.controlled.site_snapshot import SiteSnapshot
from scripts.common.eval_utils import run_autofr_controlled_given_snapshots, W_VALUE, UCB_CONFIDENCE, GAMMA, \
    ITERATION_MULTIPLIER, REWARD_FUNC, INIT_ITERATIONS


def add_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    # REQUIRED
    parser.add_argument('--csv_file_path',
                        required=True,
                        help='Path to CSV file that holds paper results')
    parser.add_argument('--snapshots_dir',
                        required=True,
                        help='Path to a directory that holds the original zips from the AutoFR dataset')
    parser.add_argument('--output_directory',
                        required=False,
                        default="temp_graphs",
                        help='output directory for saving agent')

    parser.add_argument('--log_level', default="INFO", help='Log level')

    return parser


def main():
    """
    1. Download zips from AutoFR dataset into one directory
    2. Download the Top5K_rules.csv
    3. Run this script to automatically check reproducibility of paper using site snapshots
    """
    parser = argparse.ArgumentParser(
        description='Automatically compares filter rules from given CSV '
                    'to filter rules that we generate using site snapshots.')

    parser = add_arguments(parser)

    args = parser.parse_args()
    print(args)

    logger = logging.getLogger(__name__)

    df = pd.read_csv(args.csv_file_path)

    zips_found = glob.glob(args.snapshots_dir + os.sep + "AutoFRGEval*.zip")
    print(f"Found {len(zips_found)} snapshot zips")

    output_rows = []
    for z in zips_found:
        zip_file_name = os.path.basename(z)
        match_row = df[df["zip_file_name"] == zip_file_name]
        match_row_dict = None
        if len(match_row) > 0:
            match_row_dict = match_row.to_dict(orient="records")[0]

        if not match_row_dict:
            logger.warning(f"Could not find matching row with zip name {zip_file_name}")
            continue

        unpacked_zip_path = z.rstrip(".zip")
        snapshot_directory = None
        # unzip if we have not and find the snapshot directory
        if not os.path.isdir(unpacked_zip_path):
            shutil.unpack_archive(z, args.snapshots_dir)
        # note that the snapshot_directory is expected to be a subdirectory of the unpacked zip
        for d in os.listdir(unpacked_zip_path):
            if os.path.isdir(unpacked_zip_path + os.sep + d):
                if SiteSnapshot.SNAPSHOT_DIRECTORY_PARTIAL in d:
                    snapshot_directory = unpacked_zip_path + os.sep + d
                    break

        if not snapshot_directory:
            logger.warning(f"Could not find snapshot directory for {zip_file_name}")
            continue

        # now re-run using default parameters utilized in the paper
        site_url = match_row_dict["URL"]

        # create output directory
        dir_name = f"AutoFRGControlled_{clean_url_for_file(site_url)}_w{W_VALUE}_c{UCB_CONFIDENCE}_iter{ITERATION_MULTIPLIER}_lr{GAMMA}_q{DEFAULT_Q_VALUE}_{REWARD_FUNC}"
        dir_name += "_" + get_unique_str()

        new_output_directory = args.output_directory + os.sep + dir_name
        if not os.path.isdir(new_output_directory):
            os.makedirs(new_output_directory, exist_ok=True)

        # set up logger
        numeric_level = getattr(logging, args.log_level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % args.log_level)
        logging.root.handlers = []
        logging.basicConfig(
            handlers=[logging.FileHandler(new_output_directory + os.sep + "log.log", mode="w"), logging.StreamHandler()],
            format='%(asctime)s %(module)s - %(message)s', level=numeric_level)
        logger = logging.getLogger(__name__)

        print(f"Re-running {site_url} using {zip_file_name}...")

        env, results = run_autofr_controlled_given_snapshots(site_url,
                                              snapshot_directory,
                                              W_VALUE,
                                              GAMMA,
                                              UCB_CONFIDENCE,
                                              new_output_directory,
                                              logger,
                                              iteration_threshold=ITERATION_MULTIPLIER,
                                              init_state_iterations=INIT_ITERATIONS,
                                              do_init_only=False,
                                              default_q_value=DEFAULT_Q_VALUE,
                                              reward_func_name=REWARD_FUNC,
                                              bandit_klass=DomainHierarchyMABControlled,
                                              action_space_klass=ActionSpace)

        #logger.info(
        #    f"Output dir: \n\t Filter rules saved at {env.output_directory}")

        # read in the filter rules from env
        env_filter_rules, _ = get_rules_from_filter_list(env.main_agent.get_filter_rules_file_path())
        env_filter_rules = set([x for x in env_filter_rules if x.strip()])

        # compare with what is in the given CSV
        paper_filter_rules = set()
        if pd.notna(match_row_dict["filter_rules_created"]):
            paper_filter_rules_str = match_row_dict["filter_rules_created"]
            paper_filter_rules = set(paper_filter_rules_str.split(RULES_DELIMITER))

        match = paper_filter_rules == env_filter_rules

        # create row data to output
        row = dict()
        row["URL"] = site_url
        row["Rank"] = match_row_dict["Rank"]
        row["zip_file_name"] = match_row_dict["zip_file_name"]
        row["reproduced"] = match
        row["paper_filter_rules_created"] = match_row_dict["filter_rules_created"]
        row["rerun_filter_rules_created"] = RULES_DELIMITER.join(env_filter_rules)
        row["paper_filter_rules_created_count"] = len(paper_filter_rules)
        row["rerun_filter_rules_created_count"] = len(env_filter_rules)
        output_rows.append(row)

    # output results as CSV
    reproduce_file_path = args.output_directory + os.sep + f"confirm_reproducible_{get_unique_str()}.csv"
    df_output = pd.DataFrame(columns=list(output_rows[0].keys()))
    df_output = df_output.from_dict(output_rows)
    df_output.to_csv(reproduce_file_path, index=False)

    reproduced = df_output.loc[df_output.reproduced]
    print(f"\n\nSUMMARY:\n\t- Reproduced {len(reproduced)}/{len(df_output)}\n\t- Final results in {reproduce_file_path}")


if __name__ == "__main__":
    main()
