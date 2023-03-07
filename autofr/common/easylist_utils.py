import logging
import os
import typing

import requests

from autofr.common.filter_rules_utils import find_rule_structure
from autofr.common.utils import extract_tld


def get_easylist_url_based_on_site(site_url: str = None) -> typing.Tuple[str, str]:
    key = "default"
    default_list = "https://easylist.to/easylist/easylist.txt"
    if site_url:
        tld = extract_tld(site_url)
        if tld.suffix:
            key = tld.suffix
            split_key = key.split(".")
            key = split_key[-1]

    return {
               "ru": "https://easylist-downloads.adblockplus.org/ruadlist+easylist.txt",
               "ua": "https://easylist-downloads.adblockplus.org/ruadlist+easylist.txt",
               "ro": "https://easylist-downloads.adblockplus.org/rolist+easylist.txt",
               "fr": "https://easylist-downloads.adblockplus.org/liste_fr+easylist.txt",
               "lv": "https://easylist-downloads.adblockplus.org/latvianlist+easylist.txt",
               "kr": "https://easylist-downloads.adblockplus.org/koreanlist+easylist.txt",
               "in": "https://easylist-downloads.adblockplus.org/indianlist+easylist.txt",
               "es": "https://easylist-downloads.adblockplus.org/easylistspanish+easylist.txt",
               "br": "https://easylist-downloads.adblockplus.org/easylistportuguese+easylist.txt",
               "pl": "https://easylist-downloads.adblockplus.org/easylistpolish+easylist.txt",
               "lt": "https://easylist-downloads.adblockplus.org/easylistlithuania+easylist.txt",
               "it": "https://easylist-downloads.adblockplus.org/easylistitaly+easylist.txt",
               "il": "https://easylist-downloads.adblockplus.org/israellist+easylist.txt",
               "de": "https://easylist-downloads.adblockplus.org/easylistgermany+easylist.txt",
               "nl": "https://easylist-downloads.adblockplus.org/easylistdutch+easylist.txt",
               "cn": "https://easylist-downloads.adblockplus.org/easylistchina+easylist.txt",
               "cc": "https://easylist-downloads.adblockplus.org/easylistchina+easylist.txt",
               "cz": "https://easylist-downloads.adblockplus.org/easylistczechslovak+easylist.txt",
               "sk": "https://easylist-downloads.adblockplus.org/easylistczechslovak+easylist.txt",
               "dk": "https://easylist-downloads.adblockplus.org/dandelion_sprouts_nordic_filters+easylist.txt",
               "no": "https://easylist-downloads.adblockplus.org/dandelion_sprouts_nordic_filters+easylist.txt",
               "nu": "https://easylist-downloads.adblockplus.org/dandelion_sprouts_nordic_filters+easylist.txt",
               "is": "https://easylist-downloads.adblockplus.org/dandelion_sprouts_nordic_filters+easylist.txt",
               "bg": "https://easylist-downloads.adblockplus.org/bulgarian_list+easylist.txt",
               "vn": "https://easylist-downloads.adblockplus.org/abpvn+easylist.txt",
               "id": "https://easylist-downloads.adblockplus.org/abpindo+easylist.txt",
               "default": default_list
           }.get(key, default_list), key


def get_easylist_rules_with_comments(logger: logging.Logger, site_url: str = None) -> typing.Tuple[list, str]:
    easylist_url, list_type = get_easylist_url_based_on_site(site_url)
    r = requests.get(easylist_url)
    rules = []
    if r.ok:
        rules = r.text.split("\n")
        rules = [x for x in rules if len(x) > 0]
    #logger.debug("Found %d rules from EasyList" % len(rules))
    return rules, list_type


def get_easyprivacy_rules_with_comments(logger: logging.Logger):
    r = requests.get("https://easylist.to/easylist/easyprivacy.txt")
    rules = []
    if r.ok:
        rules = r.text.split("\n")
        rules = [x for x in rules if len(x) > 0]
    #logger.debug("Found %d rules from EasyPrivacy" % len(rules))
    return rules, "default"


def output_transformed_filterlist_rule_types(rules_list: list,
                                             main_title: str,
                                             list_type: str,
                                             output_directory: str,
                                             suffix: str,
                                             logger: logging.Logger) -> str:
    file_name = output_directory + os.sep + main_title + "_filter_rule_transformed_" + list_type + "_" + suffix + ".txt"
    logger.info(f"trying to write out {file_name}")

    with open(file_name, "w") as f:
        for rule in rules_list:
            if rule.startswith("!"):
                f.write(rule + "\n")
            else:
                structure_dict = find_rule_structure(rule)
                for key in structure_dict:
                    if ("eSLD" in key or "FQDN" in key) and structure_dict.get(key) > 0:
                        f.write(rule + "\n")

    return file_name


def get_easylist_filterlist_rule_types(output_directory: str,
                                       suffix: str,
                                       logger: logging.Logger,
                                       site_url: str = None) -> str:
    # NOTE: we rely on default EL only for now (do not pass in the site_url for get_easylist_rules_with_comments
    easylist_rules, list_type = get_easylist_rules_with_comments(logger)
    return output_transformed_filterlist_rule_types(easylist_rules,
                                                    "EasyList",
                                                    list_type,
                                                    output_directory,
                                                    suffix,
                                                    logger)


def get_easyprivacy_filterlist_rule_types(output_directory: str,
                                       suffix: str,
                                       logger: logging.Logger) -> str:
    rules, list_type = get_easyprivacy_rules_with_comments(logger)
    return output_transformed_filterlist_rule_types(rules,
                                                    "EasyPrivacy",
                                                    list_type,
                                                    output_directory,
                                                    suffix,
                                                    logger)
