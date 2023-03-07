import argparse
import logging
import shutil

from autofr.common.selenium_utils import is_binary_patched, patch_exe

logger = logging.getLogger(__name__)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Patch chrome driver')

    parser.add_argument('--chrome_driver_path', default="chromedriver",
                        help='Path to chrome driver')

    args = parser.parse_args()

    logger.info(args)

    # check binary
    logger.debug(f"PATCHING: chrome driver path as input {args.chrome_driver_path}")
    is_patched = False
    patch_response = ""
    location_of_binary = args.chrome_driver_path
    if args.chrome_driver_path == "chromedriver":
        location_of_binary = shutil.which(args.chrome_driver_path)

    logger.debug(f"PATCHING: location of binary {location_of_binary}")
    is_patched = is_binary_patched(location_of_binary)
    if not is_patched:
        patch_response = patch_exe(location_of_binary)
    logger.debug(f"PATCHING: is chrome driver binary patched: {is_patched}, patch response: {patch_response}")
