import argparse
import logging
import os
import subprocess
from autofr.common.docker_utils import IS_INSIDE_DOCKER

from autofr.common.filter_rules_utils import get_rules_from_filter_list
from autofr.rl.browser_env.browser_env import BrowserWithAdHighlighter, GOOGLE_TMP_URL

logger = logging.getLogger(__name__)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Main agent + selenium')
    parser.add_argument('--profile_path', required=False,
                        help='Path to browser profile')
    parser.add_argument('--downloads_path', required=True,
                        help='Path for downloads')
    parser.add_argument('--url', default="https://www.insomnia.gr",
                        help='Path to log file of percival')
    parser.add_argument('--adblock_ext_path', required=True,
                        help='Path to adblock plus extension')
    parser.add_argument('--adblock_proxy_path', required=True,
                        help='Path to adblock plus proxy')
    parser.add_argument('--ad_highlighter_ext_path', required=True,
                        help='Path to ad-highlighter extension')
    parser.add_argument('--browser_path', required=False,
                        help='Path to browser binary')
    parser.add_argument('--chrome_driver_path', default="chromedriver",
                        help='Path to chrome driver')
    parser.add_argument('--tmp_url', default=GOOGLE_TMP_URL,
                        help='URL used to refresh filter list')
    parser.add_argument('--wait_time', default=45, type=int,
                        help='time to wait between URLs')
    parser.add_argument('--agent_name', default="", required=False,
                        help='Suffix name of agent')
    parser.add_argument('--block_items_path',
                        help='The path to a list of new line separated items to block')
    parser.add_argument('--do_initial_state_only', default="false", required=False,
                        help='Suffix name of agent')
    parser.add_argument('--init_state_iterations', default=1, type=int, required=False,
                        help='Number of times to run init state')
    parser.add_argument('--save_dissimilar_hashes', default="false", required=False,
                        help='Whether to output file of dissimilar hashes')
    parser.add_argument('--log_level', default="INFO", help='Log level')

    args = parser.parse_args()

    format_str = '%(asctime)s %(module)s - %(message)s'
    if IS_INSIDE_DOCKER:
        output = subprocess.check_output(['cat', '/etc/hostname'], text=True).replace("\n", "").strip()
        format_str = 'Docker ' + output  + ": " + format_str

    logging.basicConfig(format=format_str, level=args.log_level.upper())
    logger.debug(args)
    assert "http" in args.url, "URL must specify some http protocol"

    if not os.path.isdir(args.downloads_path):
        os.makedirs(args.downloads_path, exist_ok=True)

    do_initial_state_only = args.do_initial_state_only.lower() == "true"
    save_dissimilar_hashes = args.save_dissimilar_hashes.lower() == "true"

    agent_name = args.agent_name

    filter_rules = None
    whitelist_filter_rules = None
    if args.block_items_path:
        filter_rules, whitelist_filter_rules = get_rules_from_filter_list(args.block_items_path)

    #logger.debug(f"Number of rules being tested: {len(filter_rules or [])}")

    with BrowserWithAdHighlighter(args.url, args.adblock_proxy_path,
                                  args.ad_highlighter_ext_path, args.downloads_path,
                                  current_filter_rules=filter_rules,
                                  whitelist_rules=whitelist_filter_rules,
                                  adblock_ext_path=args.adblock_ext_path if filter_rules or whitelist_filter_rules else None,
                                  agent_name=agent_name, wait_time=args.wait_time,
                                  do_initial_state_only=do_initial_state_only,
                                  init_state_iterations=args.init_state_iterations,
                                  save_dissimilar_hashes=save_dissimilar_hashes
                                  ) as agent:
        logging.root.handlers = []
        logging.basicConfig(handlers=[logging.FileHandler(agent.output_path + os.sep + "log.log", mode="w"), logging.StreamHandler()], format=format_str, level=args.log_level.upper())
        agent.get_init_site_feedback()

