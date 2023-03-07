import json
import logging
import os
import re
import tempfile
import typing
from urllib.parse import urlparse

from autofr.common.utils import get_variations_of_domains, get_second_level_domain_by_url, get_unique_str, \
    extract_tld

logger = logging.getLogger(__name__)

ABP_START_OF_FILE = ["[Adblock Plus 3.1]",
                     "! Checksum: e21fn3Ldug+2L2niY/LTRQ",
                     "! Version: 202012162200",
                     "! Title: ABP filters",
                     "! Last modified: 16 Dec 2020 22:00 UTC",
                     "! Expires: 1 hours (update frequency)",
                     "! Homepage: https://github.com/abp-filters/abp-filters-anti-cv",
                     "!", "! Filter list designed by RL for Adblock Plus",
                     "!", "! Please report any issues",
                     "! on GitHub https://github.com/abp-filters/abp-filters-anti-cv/issues",
                     "! or via filters+cv@adblockplus.org"]

# filter rule delimiters
RULES_DELIMITER = ";;"
FILTER_RULE_DOMAIN_DELIMITER = "^"
FILTER_RULE_OPTION_DELIMITER = "$"
FILTER_RULE_DOMAIN_START = "||"


class FilterRule:
    """
    Simple structure for filter rule.
    The higher the priority, the more important it is
    """

    def __init__(self, rule: str,
                 comment: str = None,
                 priority: int = 1):
        self.rule = rule
        self.comment = comment
        self.priority = priority

    def __eq__(self, other: "FilterRule"):
        if not isinstance(other, type(self)):
            return NotImplemented

        return self.rule == other.rule \
               and self.comment == other.comment \
               and self.priority == other.priority

    def __hash__(self):
        return hash((self.rule, self.comment, self.priority))

class FilterRuleBlockRecord:
    """
    Structure to keep track of when a filter rule is hit during application.
    Hit = rule blocked a web request
    """

    def __init__(self, filter_rule: str, url_blocked: str, url_type: str, docDomain: str):
        self.filter_rule = filter_rule
        self.url_blocked = url_blocked
        self.url_type = url_type
        # which scope/frame is it in
        self.docDomain = docDomain

    def get_variations_of_domain_of_blocked(self) -> typing.Tuple[str, str, str, str]:
        """
        Returns sld, fqdn, fqdn_and_path, path
        """
        return get_variations_of_domains(self.url_blocked)

    def get_variations_from_filter_rule(self) -> typing.Tuple[str, str, str]:
        """
        Tries to clean up the rule and get the FQDN version of the rule
        """
        return get_variations_from_filter_rule(self.filter_rule)

    def __str__(self):
        return "filter_rule: " + str(self.filter_rule) \
               + ", url_blocked: " + str(self.url_blocked) \
               + ", url_type: " + str(self.url_type) \
               + ", docDomain: " + str(self.docDomain)

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.filter_rule == other.filter_rule and self.url_blocked == other.url_blocked \
                and self.url_type == other.url_type and self.docDomain == other.docDomain
        return False


def create_rule_simple(domain: str) -> str:
    if "/" not in domain:
        return f"{FILTER_RULE_DOMAIN_START}{domain}{FILTER_RULE_DOMAIN_DELIMITER}"

    # if it has paths or more, then we do not use the ending caret
    return f"{FILTER_RULE_DOMAIN_START}{domain}"


def create_rule_simple_with_subdocumnt(domain: str) -> str:
    rule = create_rule_simple(domain)
    return f"{rule}$subdocument"


def create_whitelist_rule_simple(whitelist_domain: str) -> typing.Optional[str]:
    if not whitelist_domain.strip():
        return None

    if whitelist_domain.startswith("data:"):
        # TODO: maybe do whitelist rule for data:?
        pass
    else:
        if "http" not in whitelist_domain:
            parsed_url = urlparse("http://" + whitelist_domain)
        else:
            parsed_url = urlparse(whitelist_domain)

        if parsed_url.hostname:
            parsed_url = parsed_url.hostname.replace("www.", "") + parsed_url.path
            return f"@@{FILTER_RULE_DOMAIN_START}{parsed_url}"
        else:
            logger.warning("whitelist domain has no hostname: %s", whitelist_domain)
    return None


def output_filter_list_with_value(domains_and_values: dict,
                                  whitelist_domains: list = None,
                                  file_path: str = "../adblockpluschrome-anticv-rl-adblocking/proxy/abp-filters-anti-cv.txt"):
    with open(file_path, "w") as output_file:
        # write beginning lines of filter list
        for start_line in ABP_START_OF_FILE:
            output_file.write(start_line + "\n")

        domains_and_values_flat = [(x, y) for x, y in domains_and_values.items()]

        domains_and_values_flat.sort(key=lambda v: (v[1]["q_value"], v[0]), reverse=True)

        # write out rules
        for domain, value in domains_and_values_flat:
            output_file.write(f"! {json.dumps(value)}\n")
            split_domain = domain.split(RULES_DELIMITER)
            for d in split_domain:
                output_file.write(create_rule_simple(d) + "\n")

        # add in white listing
        if whitelist_domains:
            for whitelist_domain in whitelist_domains:
                split_domain = whitelist_domain.split(RULES_DELIMITER)
                for d in split_domain:
                    rule = create_whitelist_rule_simple(d)
                    if rule:
                        output_file.write(rule + "\n")


def output_existing_filter_list(existing_filter_list_path: str,
                                whitelist_domains: list = None,
                                file_path: str = "../adblockpluschrome-anticv-rl-adblocking/proxy/abp-filters-anti-cv.txt"):
    """
    Given an existing_filter_list_path, open the rules and transfer it to another file (file_path)
    """
    with open(file_path, "w") as output_file:
        # write beginning lines of filter list
        for start_line in ABP_START_OF_FILE:
            output_file.write(start_line + "\n")

        with open(existing_filter_list_path) as existing_file:
            for line in existing_file:
                if not line.startswith("!"):
                    output_file.write(line)

            # add in white listing
            if whitelist_domains:
                for whitelist_domain in whitelist_domains:
                    rule = create_whitelist_rule_simple(whitelist_domain)
                    if rule:
                        output_file.write(rule + "\n")


def output_filter_list(
        rules: set = None,
        domains: set = None,
        whitelist_domains: set = None,
        file_path: str = "../adblockpluschrome-anticv-rl-adblocking/proxy/abp-filters-anti-cv.txt",
):
    """
    Output a filter list at file_path with a beginning of ABP_START_OF_FILE
    File can be empty (with just the beginning part)
    """
    with open(file_path, "w") as output_file:
        # write beginning lines of filter list
        for start_line in ABP_START_OF_FILE:
            output_file.write(start_line + "\n")

        # write all raw rules as well (already in correct syntax)
        if rules:
            for rule in rules:
                output_file.write(rule + "\n")

        # If we pass in any domains, then convert them into a rule

        # write out rules (convert from domain to rule)
        if domains:
            for domain in domains:
                output_file.write(create_rule_simple(domain) + "\n")

        # add in white listing (convert from domain to rule)
        if whitelist_domains:
            for whitelist_domain in whitelist_domains:
                rule = create_whitelist_rule_simple(whitelist_domain)
                if rule:
                    output_file.write(rule + "\n")


def output_filter_list_with_comments(
        rules: typing.List[FilterRule] = None,
        domains: set = None,
        whitelist_domains: set = None,
        file_path: str = "../adblockpluschrome-anticv-rl-adblocking/proxy/abp-filters-anti-cv.txt",
):
    """
    Output a filter list at file_path with a beginning of ABP_START_OF_FILE
    File can be empty (with just the beginning part)
    """
    with open(file_path, "w") as output_file:
        # write beginning lines of filter list
        for start_line in ABP_START_OF_FILE:
            output_file.write(start_line + "\n")

        # write all raw rules as well (already in correct syntax)
        if rules:
            for rule in rules:
                if rule.comment:
                    output_file.write("! " + rule.comment + "\n")
                output_file.write(rule.rule + "\n")

        # If we pass in any domains, then convert them into a rule

        # write out rules (convert from domain to rule)
        if domains:
            for domain in domains:
                output_file.write(create_rule_simple(domain) + "\n")

        # add in white listing (convert from domain to rule)
        if whitelist_domains:
            for whitelist_domain in whitelist_domains:
                rule = create_whitelist_rule_simple(whitelist_domain)
                if rule:
                    output_file.write(rule + "\n")


def get_variations_from_filter_rule(filter_rule: str) -> typing.Tuple[typing.Optional[str], str, str]:
    """
    Converts rule into eSLD, FQDN version, domain versions
    """
    rule_tmp = filter_rule
    for delimiter, keep_index in [(FILTER_RULE_OPTION_DELIMITER, 0), ("?", 0), (FILTER_RULE_DOMAIN_DELIMITER, 0),
                                  (FILTER_RULE_DOMAIN_START, 1)]:
        if delimiter in rule_tmp:
            rule_tmp_split = rule_tmp.split(delimiter)
            if keep_index > 0:
                if len(rule_tmp_split) > keep_index:
                    rule_tmp = rule_tmp_split[keep_index]
            else:
                rule_tmp = rule_tmp_split[keep_index]

    #logger.debug("filter rule %s, after getting rid of delimiters %s", filter_rule, rule_tmp)
    sld, fqdn, fqdn_and_path, path = get_variations_of_domains(rule_tmp)
    return sld, fqdn, rule_tmp


def convert_filter_rule_to_action(filter_rule: str) -> str:
    """
    Converts network-based filter rules to an action
    """
    filter_rule_split = filter_rule.split(FILTER_RULE_OPTION_DELIMITER)[0]
    return filter_rule_split.replace(FILTER_RULE_DOMAIN_START, "").replace(FILTER_RULE_DOMAIN_DELIMITER, "")


def convert_to_filter_records(abp_hitrecords: dict) -> typing.List[FilterRuleBlockRecord]:
    """
    Convert JSON abp_hitrecords to list of FilterRuleBlockRecord
    """

    # Example of filter records JSON:
    # {"filter_records": [{"filter": {"_text": "||piquenewsmagazine.com^",
    # "pattern": "||piquenewsmagazine.com^"}, "request": {"docDomain": "www.piquenewsmagazine.com", "sitekey": null,
    # "specificOnly": false, "type": "STYLESHEET", "url":
    # "https://www.piquenewsmagazine.com/cssb/template_via?v=w-RkTQIdRp4EMX3v-OAgcOs-3defLas1Ck9lvPyxYMI1"},
    # "tabId": 2, "type": "WEBREQUEST"},

    filter_records = []
    for abp_hitrecord in abp_hitrecords["filter_records"]:
        filter_rule = abp_hitrecord["filter"]["_text"]
        request_info = abp_hitrecord["request"]
        url_blocked = request_info["url"]
        url_type = request_info["type"]
        docDomain = request_info["docDomain"]
        filter_record = FilterRuleBlockRecord(filter_rule, url_blocked, url_type, docDomain)
        filter_records.append(filter_record)
    return filter_records


def get_block_items_from_path(block_items_path: str) -> list:
    block_items = []
    if os.path.isfile(block_items_path):
        with open(block_items_path) as f:
            for block_item in f:
                block_items.append(block_item.strip())
    return block_items


def get_whitelist_domains_from_file(filter_list_file: str) -> list:
    whitelist_domains = []
    if os.path.isfile(filter_list_file):
        with open(filter_list_file) as f:
            for line in f:
                if line.startswith("@@"):
                    domain = line.strip().replace("@@", "").replace(FILTER_RULE_DOMAIN_START, "").replace(
                        FILTER_RULE_DOMAIN_DELIMITER, "")
                    whitelist_domains.append(domain)
    return whitelist_domains


def get_sld_from_filter_rules(filter_rule: str) -> typing.Optional[str]:
    rule_tmp = filter_rule.split(FILTER_RULE_OPTION_DELIMITER)[0]
    rule_tmp = rule_tmp.split(FILTER_RULE_DOMAIN_DELIMITER)[0]
    rule_tmp = rule_tmp.replace(FILTER_RULE_DOMAIN_START, "")
    return get_second_level_domain_by_url(rule_tmp)


def get_rules_from_filter_list(filter_list_file: str) -> typing.Tuple[list, list]:
    """
    Get the raw filter rules
    """
    rules = []
    whitelist_rules = []
    if os.path.isfile(filter_list_file):
        with open(filter_list_file) as f:
            for line in f:
                if line and not line.startswith("!") and not line.startswith("["):
                    rule = line.rstrip("\n")
                    if line.startswith("@@"):
                        whitelist_rules.append(rule)
                    else:
                        rules.append(rule)
    return rules, whitelist_rules


def create_tmp_filter_list(
        raw_rules: list = None,
        action_domains: list = None,
        whitelist_domains: list = None,
        output_directory: str = None) -> str:
    """
    Creates a filter list in /tmp/ folder given domains
    Returns the path to the create filter list
    """
    rules = []
    if action_domains:
        for d in action_domains:
            rules.append(create_rule_simple(d))
    if whitelist_domains:
        for d in whitelist_domains:
            rules.append(create_whitelist_rule_simple(d))

    if raw_rules:
        rules += raw_rules

    output_dir = output_directory
    if not output_dir:
        output_dir = tempfile.gettempdir()

    filter_list_path = output_dir + os.sep + "filter_rules_tmp_" + get_unique_str() + ".txt"
    output_filter_list(rules=set(rules),
                       file_path=filter_list_path)
    return filter_list_path


def get_default_rule_structure_dict() -> dict:
    return {"Web Request Blocking": 0, "Element Hiding": 0, "Whitelisting": 0,
            "Advance Element Hiding": 0, "Advance JS aborting": 0, "Advance Misc.": 0}


def find_rule_structure(line: str) -> dict:
    def _get_number_of_path_segments(url: str) -> int:
        path_split = url.split("/")
        path_segments = 0
        # check if first item is part of domain
        tld = extract_tld(path_split[0])
        if len(tld.domain) > 0 and len(tld.suffix) > 0:
            # logger.debug("remove domain from path_split %s", tld)
            path_split.remove(path_split[0])

        for path_item in path_split:
            if path_item != "/" and len(path_item.strip()) > 0:
                if path_item.startswith("&") or path_item.startswith("?"):
                    continue

                path_segments += 1

        return path_segments

    def _increment(key: str, stats: dict) -> dict:
        if key not in stats:
            stats[key] = 0
        stats[key] += 1
        return stats

    def _process_domain_with_path(subrule: str, type_str: str, file_stats: dict):
        path_split = subrule.split("$")
        path_segment_count = _get_number_of_path_segments(path_split[0])
        if path_segment_count > 0:
            if "*" in subrule:
                file_stats = _increment(type_str + " + Path + Regex", file_stats)
            else:
                file_stats = _increment(type_str + " + Path", file_stats)

            file_stats = _increment("Path_Segment_" + str(path_segment_count), file_stats)
        return file_stats

    line_processed_success = False
    file_stats = get_default_rule_structure_dict()

    # ignore comment lines
    if line.startswith("!") or len(line.strip()) == 0:
        return file_stats

    if line.startswith("@@"):
        file_stats["Whitelisting"] += 1
        return file_stats

    # whitelisting element hiding
    if "#@#" in line:
        file_stats["Whitelisting"] += 1
        return file_stats

    if "#$#" in line:
        if "abort" in line:
            file_stats = _increment("Advance JS aborting", file_stats)
        elif "hide-if-contains-visible-text" in line or "hide-if-contains-and-matches-style" in line or \
                "hide-if-has-and-matches-style" in line or "hide-if-contains-image" in line or \
                "hide-if-contains-image-hash" in line or "hide-if-shadow-contains" in line or \
                "hide-if-contains" in line:
            file_stats = _increment("Advance Element Hiding", file_stats)
        else:
            file_stats = _increment("Advance Misc.", file_stats)

        return file_stats

    if "#?#" in line:
        file_stats = _increment("Element Hiding", file_stats)
        return file_stats

    if "##" in line:
        file_stats = _increment("Element Hiding", file_stats)
        return file_stats

    if line.startswith(f"/{FILTER_RULE_DOMAIN_DELIMITER}") or line.startswith("/\\"):
        file_stats = _increment("Regex Only", file_stats)
    elif line.startswith("&"):
        file_stats = _increment("Query Parameters", file_stats)
    elif line.startswith("/") or line.startswith("-") or line.startswith("+"):
        path_segment_count = _get_number_of_path_segments(line)
        file_stats = _increment("Path_Segment_" + str(path_segment_count), file_stats)
        if "*" in line:
            file_stats = _increment("Path Only with Regex", file_stats)
        else:
            file_stats = _increment("Path Only", file_stats)
    elif line.startswith("."):
        if "/" in line:
            path_segment_count = _get_number_of_path_segments(line)
            file_stats = _increment("Path_Segment_" + str(path_segment_count), file_stats)
            if "?" in line or "&" in line:
                file_stats = _increment("Any Part of Domain + Path + Query", file_stats)
            else:
                file_stats = _increment("Any Part of Domain + Path", file_stats)
        elif "?" in line or "&" in line:
            file_stats = _increment("Any Part of Domain + Query", file_stats)
        else:
            file_stats = _increment("Any Part of Domain", file_stats)
    elif line.startswith(FILTER_RULE_DOMAIN_START):
        line = line.replace(FILTER_RULE_DOMAIN_START, "")
        line_split = line.split(FILTER_RULE_DOMAIN_DELIMITER)
        type_str = "eSLD"

        if len(line_split) > 1 and len(line_split[1]) > 0:
            # logger.debug("inside if: %s" % str(line_split))

            tld = extract_tld(line_split[0])
            if len(tld.subdomain) > 0:
                type_str = "FQDN"

            if "/" in line[1]:
                file_stats = _process_domain_with_path(line[1], type_str, file_stats)
            elif "*" in line[0] or "*" in line[1]:
                file_stats = _increment(type_str + " + Regex", file_stats)
            else:
                file_stats = _increment(type_str, file_stats)

        else:
            split_tmp = line_split[0].split("$")
            tld = extract_tld(split_tmp[0])
            if len(tld.subdomain) > 0:
                type_str = "FQDN"

            # logger.debug("inside else: %s" % str(split_tmp))
            if "/" in split_tmp[0]:
                file_stats = _process_domain_with_path(split_tmp[0], type_str, file_stats)
            elif "*" in split_tmp[0]:
                file_stats = _increment(type_str + " + Regex", file_stats)
            else:
                file_stats = _increment(type_str, file_stats)

    if re.search("\$.*domain", line):
        file_stats = _increment("Domain Specific", file_stats)
    if re.search("\$.*image", line):
        file_stats = _increment("Image Resource", file_stats)
    if re.search("\$.*third-party", line):
        file_stats = _increment("Third Party", file_stats)
    if re.search("\$.*subdocument", line):
        file_stats = _increment("SubDocument", file_stats)
    if re.search("\$.*popup", line):
        file_stats = _increment("Popup", file_stats)

    file_stats = _increment("Web Request Blocking", file_stats)

    return file_stats


# hit records is a dictionary with keys:
# "filters", "whitelist"
def get_filter_records_by_rule(abp_hitrecords: dict) -> dict:
    """
    Convert to FilterRuleBlockRecord then create a dict of record.filter_rule -> list[FilterRuleBlockRecord]
    """

    filter_records = convert_to_filter_records(abp_hitrecords)
    filter_records_by_rule = dict()
    for record in filter_records:
        if record.filter_rule not in filter_records_by_rule:
            filter_records_by_rule[record.filter_rule] = []
        filter_records_by_rule[record.filter_rule].append(record)
    """
    for abp_hitrecord in abp_hitrecords["filter_records"]:
        fitler = abp_hitrecord["filter"]["_text"]
        filter_domain = fitler.replace("||", "").replace("^", "")
        url_blocked = abp_hitrecord["request"]["url"]
        if filter_domain not in filters_by_domain:
            filters_by_domain[filter_domain] = []
        filters_by_domain[filter_domain].append(url_blocked)
    """
    return filter_records_by_rule
