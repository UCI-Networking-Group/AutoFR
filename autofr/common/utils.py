import glob
import json
import logging
import os
import re
import typing
import urllib.request
import uuid
import numpy as np
import tldextract
from json import JSONDecodeError
from typing import Tuple
from urllib.parse import urlparse


opener = urllib.request.build_opener()
opener.addheaders = [('User-agent',
                      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36')]
urllib.request.install_opener(opener)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36'}


logger = logging.getLogger(__name__)

JSON_WEBREQUEST_KEY = "cvwebrequests"
WEBREQUESTS_DATA_FILE_SUFFIX = f"--{JSON_WEBREQUEST_KEY}.json"
TOPFRAME = "topframe_"


# To retrieve all webrequests for HTTP status 200,
# pass in the file path to the json file and the HTTP status 200
# webrequests = get_webrequests_from_raw_json(path_file, 200)
def get_webrequests_from_raw_json(file_path, event_status=200):
    webrequests = []
    with open(file_path) as f:
        try:
            file_data = json.load(f)
            requests = file_data[JSON_WEBREQUEST_KEY]
            # print("requests found %d" % len(requests))
            if requests and len(requests) > 0:
                for req in requests:
                    # print("Looking at request %s " % str(req))
                    event = req["event"]
                    if event and "status" in event and event["status"] == "onCompleted":
                        # print("Found onCompleted URL")
                        req_details_json = json.loads(event["details"])
                        if req_details_json.get("statusCode") == event_status:
                            webrequests.append(event["url"])
        except JSONDecodeError as e:
            # return out of here
            logger.warning(f"Could not load json file {file_path}: {repr(e)} {e}")
            return

    return webrequests


def extract_tld(url: str):
    return tldextract.extract(url)


def get_second_level_domain_from_tld(url_tld) -> str:
    return url_tld.domain + "." + url_tld.suffix


def get_domain_only_from_tld(url_tld, remove_www: bool = True) -> str:
    """
    returns fully qualified domain (FQDN)
    """
    sld = get_second_level_domain_from_tld(url_tld)
    if url_tld.subdomain and len(url_tld.subdomain) > 0:
        sld = url_tld.subdomain + "." + sld

    if remove_www:
        sld = sld.replace("www.", "")

    return sld


# from url such as example.doubleclick.net --> SLD is doubleclick.net
def get_second_level_domain_by_url(url: str) -> str:
    tld = extract_tld(url)
    sld = get_second_level_domain_from_tld(tld)
    return sld


# given a url, return the domain
def get_domain_only_from_url(url: str, **kwargs) -> str:
    tld = extract_tld(url)
    domain = get_domain_only_from_tld(tld, **kwargs)
    return domain


def get_domains_dict_from_urls(urls: list) -> dict:
    domain_dict = dict()

    for url in urls:
        key = get_domain_only_from_url(url)
        if key not in domain_dict:
            domain_dict[key] = []
        domain_dict[key].append(url)

    return domain_dict

def dump_to_json(data: typing.Any, file_name: str, output_directory: str):
    with open(output_directory + os.sep + file_name + ".json", 'w') as outfile:
        json.dump(data, outfile)


def clean_url_for_file(url: str, max_length: int = 50) -> str:
    try:
        url = url.replace("https", "").replace("http", "").replace(":", "").replace("/", "_")[:max_length]
        url = re.sub('[^a-zA-Z0-9 \n\.]', '', url)
    except AttributeError as e:
        logger.error(f"Could not clean {url}")
        raise e
    return url


def get_file_from_path_by_key(path: str, file_name_regex: str,
                              by_key: typing.Callable = os.path.getmtime,
                              ignore: list = None) -> typing.Optional[str]:
    """
    From a list of files from path, get the file that has max based on the by_key criteria
    Default: most recent file by time
    """
    list_of_files = glob.glob(path + os.sep + file_name_regex)
    latest_file = None
    if len(list_of_files) > 0:
        # ignore some files based on names
        if ignore:
            for ignore_str in ignore:
                list_of_files = [x for x in list_of_files if ignore_str not in x]
        # get latest
        latest_file = max(list_of_files, key=by_key)

    return latest_file


def get_largest_file_from_path(path: str, file_name_regex: str, ignore: list = None) -> str:
    """
    From a list of files from path, get the file is largest
    Default: most recent file by time
    """
    return get_file_from_path_by_key(path, file_name_regex,
                                     by_key=os.path.getsize, ignore=ignore)


def chunk_list(some_list: list, n: int = 4) -> list:
    final = [
        some_list[i * n:(i + 1) * n]
        for i in range((len(some_list) + n - 1) // n)
    ]
    return final


def should_skip_perf_url(url: str) -> bool:
    return url.startswith("about:blank") or url.startswith("chrome") or url.startswith("data") or \
           "new-tab" in url or "newtab" in url or "iamawesome" in url or "about." == url or url is None


def is_real_fqdn(fqdn: str, slds: list) -> bool:
    """
    fqdn must not have www or be the same as its esld version
    """
    return fqdn and not fqdn.startswith("www") and fqdn not in slds


def is_real_fqdn_with_path(path: str) -> bool:
    return path is not None


def get_fqdns_from_urls(slds: list, urls: list, set_only=True) -> list:
    fqdns = []
    # find fqdns that have the same sld as the given slds
    for url in urls:
        current_sld = get_second_level_domain_by_url(url)
        if current_sld in slds:
            fqdn = get_domain_only_from_url(url, remove_www=False)
            # skip the ones with www
            if is_real_fqdn(fqdn, slds):
                fqdns.append(fqdn)
    if set_only:
        fqdns = list(set(fqdns))
    return fqdns


def get_variations_of_domains(domain: str) -> Tuple[
    typing.Optional[str], str, typing.Optional[str], typing.Optional[str]]:
    """
        Given a domain, return the eSLD, FQDN, FQDN+Path, Path with no protocol
    """
    sld = get_second_level_domain_by_url(domain)
    fqdn = get_domain_only_from_url(domain, remove_www=False)

    path = urlparse(domain).path
    if path == "/" or path == "":
        # if path is not there, then we don't need to consider it fqdn_and_path
        fqdn_and_path = None
        path = None
    else:
        fqdn_and_path = fqdn + path

    if sld.endswith("."):
        sld = None

    # logger.debug("sld %s, fqdn %s, fqdn_and_path %s, path %s", sld, fqdn, str(fqdn_and_path), str(path))

    return sld, fqdn, fqdn_and_path, path


def is_request_js_extension(req: str) -> Tuple[bool, bool]:
    _, _, _, path = get_variations_of_domains(req)
    is_js_ext = False
    has_ext = False
    if path is not None:
        path_split = path.split(".")
        if len(path_split) > 1:
            resource_ext = path_split[-1].strip()
            if resource_ext:
                has_ext = True
                if resource_ext == "js":
                    is_js_ext = True

    return is_js_ext, has_ext


def get_unique_str() -> str:
    return str(uuid.uuid4())[:8]


def json_convert_helper(o):
    if isinstance(o, np.generic):
        return o.item()
    raise TypeError
