import io
import json
import logging
import os
import random
import re
import string
import time
import traceback
import typing

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
from selenium.common.exceptions import TimeoutException, NoSuchElementException, NoSuchFrameException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from autofr.common.exceptions import AutoFRException
from autofr.common.utils import should_skip_perf_url

logger = logging.getLogger(__name__)

BLANK_CHROME_PAGE = "about:blank"
INITIATOR_KEY = "initiator"

# constants for chrome dev tool protocol (CDP)
CDP_NODEID = "nodeId"
CDP_BACKENDNODEID = "backendNodeId"
CDP_ATTRIBUTES = "attributes"
CDP_OBJECTID = "objectId"
CDP_SCRIPTID = "scriptId"
CDP_CALLFRAMES = "callFrames"


def _get_common_driver_options(chrome_default_download_directory=None,
                               allow_running_insecure_content=True,
                               include_window_size=True,
                               include_browser_logging=True,
                               window_width=2560, window_height=1080 * 3):
    # build options
    chrome_opt = webdriver.ChromeOptions()
    chrome_opt.add_argument('--no-sandbox')
    if include_window_size:
        chrome_opt.add_argument("--window-size=%d,%d" % (window_width, window_height))
    else:
        chrome_opt.add_argument("--start-maximized")
    chrome_opt.add_argument('--disable-application-cache')
    chrome_opt.add_argument('--disable-infobars')
    if include_browser_logging:
        chrome_opt.add_argument('--enable-logging')
        chrome_opt.add_argument('--v=1')

    chrome_opt.add_argument("--start-fullscreen")
    chrome_opt.add_argument("--no-first-run")
    chrome_opt.add_argument("--hide-scrollbars")
    chrome_opt.add_argument("--disable-notifications")

    # For older ChromeDriver under version 79.0.3945.16
    chrome_opt.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_opt.add_experimental_option('useAutomationExtension', False)
    # For ChromeDriver version 79.0.3945.16 or over
    chrome_opt.add_argument('--disable-blink-features=AutomationControlled')

    # Allow loading of unsafe script content
    if allow_running_insecure_content:
        chrome_opt.add_argument("--allow-running-insecure-content")
        chrome_opt.add_argument("--ignore-certificate-errors")

    if chrome_default_download_directory:
        chrome_opt.add_experimental_option('prefs', {
            'download.default_directory': chrome_default_download_directory,
            'download.prompt_for_download': False,
        })

    return chrome_opt

def create_driver_with_adhighlilghter(
        chrome_driver_path='',
        chrome_ext_path='',
        browser_binary_path=None,
        chrome_default_download_directory=None,
        profile_path=None,
        allow_running_insecure_content=True,
        include_custom_extensions=True,
        include_window_size=False,
        include_browser_logging=False,
        use_perf_logs=True,
        disable_isolation: bool = True,
        window_width=2560,
        window_height=1080 * 3) -> webdriver.Chrome:
    chrome_opt = _get_common_driver_options(
        chrome_default_download_directory=chrome_default_download_directory,
        allow_running_insecure_content=allow_running_insecure_content,
        include_window_size=include_window_size,
        include_browser_logging=include_browser_logging,
        window_width=window_width,
        window_height=window_height)

    # set path for the browser binary
    if browser_binary_path:
        chrome_opt.binary_location = browser_binary_path
        chrome_opt.add_argument('--chrome-binary=' + browser_binary_path)

    # load custom extension ABP + Web requests
    if include_custom_extensions:
        custom_exts = chrome_ext_path
        #logger.info(f"Using custom exts {custom_exts}")
        chrome_opt.add_argument("--load-extension=" + custom_exts)

    # Load profile
    if profile_path:
        #logger.debug("Loading driver with profile: " + profile_path)
        chrome_opt.add_argument("--user-data-dir=" + profile_path)
    #else:
    #    logger.debug("Loading driver with NO profile")

    if chrome_driver_path == "":
        chrome_driver_path = "chromedriver"
        #logger.debug("Using default chromedriver without path")

    capabilities = DesiredCapabilities.CHROME.copy()
    capabilities["applicationCacheEnabled"] = False

    # disabling isolation allows us to get all requests from all frames using perf logs
    if disable_isolation:
        # https://stackoverflow.com/questions/53280678/why-arent-network-requests-for-iframes-showing-in-the-chrome-developer-tools-un
        # to get network requests from iframes too
        chrome_opt.add_argument("--disable-features=IsolateOrigins,site-per-process")

        # need this for later versions after 68+
        # https://www.chromium.org/Home/chromium-security/site-isolation/
        chrome_opt.add_argument("--disable-site-isolation-trials")

    if use_perf_logs:
        perf_all = {"performance": "ALL"}
        capabilities["goog:loggingPrefs"] = perf_all
        # for older browsers below 75.0.3770.8
        capabilities['loggingPrefs'] = perf_all

    # finally create the driver
    driver = webdriver.Chrome(executable_path=chrome_driver_path,
                              options=chrome_opt,
                              desired_capabilities=capabilities)

    return driver


def get_scroll_width_and_height(driver):
    required_width = driver.execute_script('return document.body.parentNode.scrollWidth')
    required_height = driver.execute_script('return document.body.parentNode.scrollHeight')

    required_width_body = driver.execute_script('return document.body.scrollWidth')
    required_height_body = driver.execute_script('return document.body.scrollHeight')

    if required_width_body > required_width:
        required_width = required_width_body
    if required_height_body > required_height:
        required_height = required_height_body

    if required_height == 0:
        child_count = driver.execute_script('return document.body.childNodes.length')
        if child_count and child_count > 0:
            required_height = driver.execute_script('return document.body.childNodes[0].scrollHeight')

    return required_width, required_height


def scroll_page(scrollto_height, driver):
    js_down = f"scrollTo(0, {scrollto_height})"
    driver.execute_script(js_down)
    time.sleep(1.5)


def scroll_to_bottom(driver, default_height: int = 1000) -> int:
    js_down = 'scrollTo(0,document.body.scrollHeight)'
    js_down = """
        let scrollHeight = document.body.scrollHeight || document.documentElement.scrollHeight;
        if (scrollHeight == 0) {
            scrollHeight = %s;
        }
        scrollTo(0,scrollHeight);
        return scrollHeight;
    """ % default_height
    scroll_height_found = driver.execute_script(js_down)
    time.sleep(1.5)
    return int(scroll_height_found)


# we fake an event so that the extensions know which names to save it as
def trigger_js_event_for_filename(driver, file_name):
    js_str = "var evt = new CustomEvent('AnticvFileNameEvent', {detail:{filename: '" + file_name + "'}}); window.dispatchEvent(evt);"
    driver.execute_script(js_str)


# we fake an event so that the extensions know to refresh the filterlist (for adblock plus)
def trigger_js_event_for_refresh_filterlist(driver):
    js_str = "var evt = new CustomEvent('update_rl_filter_list'); document.dispatchEvent(evt);"
    driver.execute_script(js_str)


# we fake an event so that the extensions know to reset the adchoice counter (for ad-highlighter)
def trigger_js_event_for_reset_adchoice_counter(driver):
    js_str = "var evt = new CustomEvent('reset_adchoice_counter'); document.dispatchEvent(evt);"
    driver.execute_script(js_str)


# we fake an event so that the extensions know to get the adchoice counter (for ad-highlighter)
def trigger_js_event_for_get_adchoice_counter(driver) -> typing.Tuple[int, list]:
    #logger.info("Injecting JS to retrieve adchoice total counter")

    js_str = "var evt = new CustomEvent('set_adchoice_total_in_DOM'); document.dispatchEvent(evt);"
    driver.execute_script(js_str)
    # time.sleep(1)
    wait = WebDriverWait(driver, 2)
    wait.until(EC.presence_of_element_located((By.ID, "ad-highlighter-counter")))

    # get the element
    js_str = """
        var element = document.getElementById('ad-highlighter-counter');
        return element.getAttribute('total');
    """
    adchoice_counter = driver.execute_script(js_str)
    if not isinstance(adchoice_counter, int):
        adchoice_counter = int(adchoice_counter)

    #logger.debug("adchoice total counter %d" % adchoice_counter)

    # get the urls of the logos
    js_str = """
        var element = document.getElementById('ad-highlighter-counter');
        return element.innerText;
    """
    adchoice_logo_urls = driver.execute_script(js_str) or ""
    adchoice_logo_urls = adchoice_logo_urls.split(";;")
    #logger.debug("adchoice logo urls %d", len(adchoice_logo_urls))

    return adchoice_counter, adchoice_logo_urls


# we fake an event so that the extensions know to reset the hit records being kept (for adblock plus)
def trigger_js_event_for_reset_abp_hitrecords(driver):
    js_str = "var evt = new CustomEvent('resetHitRecords'); document.dispatchEvent(evt);"
    driver.execute_script(js_str)


# we fake an event so that the extensions know to get the hitrecords from abp (for adblock plus)
def trigger_js_event_for_get_abp_hitrecords(driver):
    logger.info("Injecting JS to retrieve adblock plus hit records")

    js_str = "var evt = new CustomEvent('setHitRecordinDOM'); document.dispatchEvent(evt);"
    driver.execute_script(js_str)
    time.sleep(1)
    # get the element
    js_str = """
        var element = document.getElementById('abp-hitrecords');
        return JSON.parse(element.textContent);
    """
    abp_hitrecords = driver.execute_script(js_str)
    # logger.debug("abp hitrecords %s" % str(abp_hitrecords))

    abp_hitrecords_len = 0
    if abp_hitrecords:
        try:
            abp_hitrecords_len = len(abp_hitrecords["filter_records"])
        except (KeyError, TypeError) as e:
            logger.warning(f"Could not turn string to json: {repr(e)} {e}")

    return abp_hitrecords, abp_hitrecords_len


# we fake an event so that the extensions know to get the dissimilar hashes (for ad-highlighter)
def trigger_js_event_for_get_dissimilar_hashes(driver) -> list:
    #logger.info("Injecting JS to retrieve dissimilar hashes")

    js_str = "var evt = new CustomEvent('set_dissimilar_hashes_in_DOM'); document.dispatchEvent(evt);"
    driver.execute_script(js_str)

    hashes = []
    try:
        element_class = "ad-highlighter-hashes"
        # time.sleep(1)
        wait = WebDriverWait(driver, 3)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, element_class)))

        # get the element
        js_str = """
            var elements = document.getElementsByClassName('%s');
            return elements;
        """ % element_class
        elements = driver.execute_script(js_str)
        if elements is not None:
            for el in elements:
                hashes.append({"src_url": el.get_attribute("src_url"),
                               "hex": el.get_attribute("hex"),
                               "sim": el.get_attribute("sim")})
    except WebDriverException:
        logger.warning(f"Could not get dissimilar hashes")

    return hashes


def get_js_helper_methods_str() -> str:
    return """
        window.is_visible_sure = function(element, computedStyles) {
            var not_visible = !element.offsetParent && element.offsetWidth === 0 && element.offsetHeight === 0;
            if (!not_visible) {
                var styles = computedStyles || window.getComputedStyle(element);
                if (styles.opacity <= 0.1 || styles.display == 'none') {
                    not_visible = true;
                }
            }
            return !not_visible;
        };


        window.is_visible_dimensions = function(element, computedStyles) {
            var styles = computedStyles || window.getComputedStyle(element);
            //var not_visible = styles.visibility == 'hidden' && element.offsetWidth <= 2 && element.offsetHeight <= 2;
            var not_visible = element.offsetWidth <= 2 && element.offsetHeight <= 2;

            return !not_visible;
        };

        window.normalizeUrl = function(urlString) {
            try {
                const url = new URL(urlString, document.location);

                if (url.protocol == "http:" || url.protocol == "https:") {
                    return url.href;
                } else if (url.protocol == "data:") {
                    return urlString;
                }
            } catch (_) {
                // pass
            }

            return null;
        }
    """


# we grab the count of all images (imgs, background, svgs)
# adapted by unified-gatherer + anti-circumventio with changes
# we skip iframes since they are mostly ads and we don't want to traverse them
# TODO: add <svg>, search into open shadowDOM and use of slots
def trigger_js_event_get_all_image_elements(driver, highlight: bool = False) -> int:

    element_set_border = "elem.style.border = '5px solid blue';"

    js_str = """
        //const elementList = [];
        var image_count = 0;
        %s

        window.walk_element = function(elem) {

            if (elem.tagName == "IFRAME") {
                return;
            }

            const re = /^url\((['"]?)([^'"]+)\1\)/;
            const re2 = /url\(["']?([^"']*)["']?\)/;
            var elemId = "";
            var computedStyles = null;
            var imageFlag = false;
            const rect = elem.getBoundingClientRect();
            var obj = {
                //elem: elem,
                id: (typeof elem.id === "string" ? elem.id : null) || null,
                height: rect.bottom - rect.top,
                width: rect.right - rect.left
            };

            if (elem.tagName == "IMG") {
                obj.src = elem.src ? window.normalizeUrl(elem.src) : null;
                imageFlag = true;
            } else {
                computedStyles = window.getComputedStyle(elem);
                const background = computedStyles.backgroundImage;
                var matched = "";
                if (background) {
                    try {
                        let matched_temp = re.exec(background);
                        if (matched_temp && matched_temp[2]) {
                            matched = matched_temp[2];
                            console.log("got with re1: " + matched);
                        } else {
                            matched_temp = re2.exec(background);
                            if (matched_temp && matched_temp[1]) {
                                matched = matched_temp[1];
                                console.log("got with re2: " + matched);
                            }
                        }
                    } catch(error) {
                        console.log("error: " + background);
                        console.log(error);
                    }
                }
                console.log(matched);
                if (matched) {
                    obj.src = window.normalizeUrl(matched);
                    imageFlag = true;
                    console.log("found background image: " + obj.src);
                }
            }

            // also skip invisible elements that we are sure are invisible, no need to check children
            if (imageFlag && !window.is_visible_sure(elem, computedStyles)) {
                return;
            }

            // add element to list if only the dimension test work out
            if (imageFlag && window.is_visible_dimensions(elem)) {
                elem.setAttribute("flg-image", "true");
                %s
                //elementList.push(obj);
                image_count += 1;
            }

            
            for (const child of elem.childNodes) {
                if (child instanceof HTMLElement) {
                    window.walk_element(child);
                }
            }
        }

        window.walk_element(document.body);
        return image_count;

    """ % (get_js_helper_methods_str(), element_set_border if highlight else "")

    elements_found = 0
    try:
        elements_found = driver.execute_script(js_str)
    except WebDriverException as e:
        logger.warning(f"Could not get the image count: {repr(e)} {e}")

    #logger.debug(f"Elements found {elements_found}")
    return elements_found


def trigger_js_event_get_all_text_nodes(driver, highlight: bool = False) -> int:

    elem_add_autofr = "elem.textContent += '(AutoFR)';"

    js_str = """
        //const elementList = [];
        const TEXTNODE_TYPE = 3;
        const ELEMENTNODE_TYPE = 1;
        var text_count = 0;

        %s
        
        window.get_truncated_text = function(text_value) {
            if (text_value.length > 100) {
                var first_half = text_value.substring(0, 50);
                var second_half = text_value.substring(text_value.length-50, text_value.length);
                return first_half + second_half;
            } else {
                return text_value;
            }
        }

        window.walk_element = function(elem, parent_elem) {
            var elemId = "";
            var computedStyles = null;

            // we don't care about text from scripts
            if (elem.tagName == "SCRIPT" || elem.tagName == "IFRAME") {
                //console.log("ignore script/iframes tags");
                return;
            }

            if (elem.nodeType != ELEMENTNODE_TYPE && elem.nodeType != TEXTNODE_TYPE) {
                //console.log("ignoring type: " + elem.nodeType);
                return;
            }

            // also skip invisible elements that we are sure are invisible, no need to check children
            
            if (elem.nodeType == ELEMENTNODE_TYPE && (!window.is_visible_sure(elem, computedStyles) || !window.is_visible_dimensions(elem)) ) {
                //console.log("ignoring due to being invisible");
                //console.log(elem);
                return;
            }
            
            let coord = {};
            try {
                let range = document.createRange();
                range.selectNode(elem);
                cord = range.getBoundingClientRect();
            } catch (err) {}
            
            var obj = {
                //elem: elem,
                id: (typeof elem.id === "string" ? elem.id : null) || null,
                coordinates: JSON.stringify(cord)
            };

            if (elem.nodeType == TEXTNODE_TYPE && elem.textContent != null) {
                //console.log("found textnode");
                if (elem.textContent.trim().length > 0) {
                    //console.log("found valid textnode #text");
                    obj.text = window.get_truncated_text(elem.textContent);
                    obj.textlength = elem.textContent.length
                    //elementList.push(obj);
                    text_count += 1;

                    // for textnodes, we need a temporary element to hold the labeling of textnodes 
                    // since we cannot add the attribute to the textnode itself.
                    
                    if (parent_elem != null && parent_elem.nodeType == ELEMENTNODE_TYPE) {
                        let tmp_el = document.createElement("flg-textnode");
                        tmp_el.style.display = "none";
                        //tmp_el.setAttribute("flg-textnode", "true");
                        elem.parentNode.insertBefore(tmp_el, elem.nextSibling);
                        %s
                        //parent_elem.appendChild(tmp_el);
                    }
                }
            } 

            for (const child of elem.childNodes) {
                //console.log("Walking children nodes");
                window.walk_element(child, elem);
            }
        }

        window.walk_element(document.body, null);

        return text_count;

    """ % (get_js_helper_methods_str(), elem_add_autofr if highlight else "")

    elements_found = 0
    try:
        elements_found = driver.execute_script(js_str)
    except WebDriverException as e:
        logger.warning(f"Could not get the text nodes: {repr(e)} {e}")

    #logger.debug(f"TextNodes found {elements_found}")

    return elements_found


def trigger_js_event_label_iframes_with_ids(driver, iframe_id_prefix: str) -> int:
    """
    We label each iframe with iframe_id_prefix + some counter
    We mark the HTML of the frame as the window.name
    """

    js_str = """
        %s
        
        let iframes = document.getElementsByTagName("iframe");
        let iframe_counter = 0;
        let iframe_id_prefix = '%s';
        for (let iframe of iframes) {
            if (window.is_visible_sure(iframe) && window.is_visible_dimensions(iframe)) {
                iframe.setAttribute('flg-iframe-id', iframe_id_prefix + iframe_counter);
                iframe_counter += 1;
            }
        }
        document.querySelector("html").setAttribute('flg-window-name', window.name);
        return iframe_counter;
    """ % (get_js_helper_methods_str(), iframe_id_prefix)

    elements = 0
    try:
        elements = driver.execute_script(js_str)
    except WebDriverException as e:
        pass
        #logger.debug(f"Could not label iframes with ids {repr(e)} {e}")

    #logger.debug("Iframes labeled %d" % elements)

    return elements


def trigger_js_event_label_iframes_with_ids_selenium(driver, iframe_id_prefix: str) -> int:
    """
    We label each iframe with iframe_id_prefix + some counter
    We mark the HTML of the frame as the window.name
    """

    js_str_individual = """
        let iframe_id_prefix = '%s';
        arguments[0].setAttribute('flg-iframe-id', iframe_id_prefix + arguments[1]);
    """ % iframe_id_prefix

    iframe_counter = 0
    elements_labeled = 0

    iframes = []
    try:
        if hasattr(driver, "find_elements_by_tag_name"):
            iframes = driver.find_elements_by_tag_name("iframe")
        else:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
    except (TimeoutException, WebDriverException) as e:
        logger.warning(f"Could not get all iframes {repr(e)} {e}")

    for iframe in iframes:
        try:
            wait = WebDriverWait(driver, 0.2)
            visible_iframe = wait.until(EC.visibility_of(iframe))
            driver.execute_script(js_str_individual, visible_iframe, iframe_counter)
            iframe_counter += 1
            elements_labeled += 1
        except (TimeoutException, WebDriverException) as e:
            pass
            #logger.debug(f"Could not label iframe {iframe} not visible {repr(e)} {e}")

    #logger.debug("Iframes labeled %d" % elements_labeled)

    return elements_labeled


def trigger_js_event_annotate_iframe_as_ad(driver, flg_iframe_id: int) -> bool:
    js_str = """
        let iframe = document.querySelector("iframe[flg-iframe-id='%s'");
        if (iframe !== null) {
            iframe.setAttribute('flg-ad', 'true');
            return 'true';
        }
        return 'false';
    """ % flg_iframe_id

    success = False
    try:
        success = driver.execute_script(js_str) == 'true'
    except WebDriverException as e:
        logger.warning(f"Could not annotate iframe as ad {flg_iframe_id}: {repr(e)} {e}")

    return success


def quit_drivers(drivers):
    if drivers:
        for driver in drivers:
            driver.close()
            time.sleep(1)
            driver.quit()


# taken from https://stackoverflow.com/a/61448618
def get_id_of_unpacked_chrome_extension(ext_abs_path):
    import hashlib

    m = hashlib.sha256()
    m.update(bytes(ext_abs_path.encode('utf-8')))
    EXTID = ''.join([chr(int(i, base=16) + ord('a')) for i in m.hexdigest()][:32])
    return EXTID


def setup_adblock_plus(drv, ext_abs_path=None, toggle_filter_list_off=False):
    # unique ID of extension taken from the chrome extension store
    # https://chrome.google.com/webstore/detail/adblock-plus-free-ad-bloc/cfhdojbkjhnklbpkdaibdccddilifddb
    if ext_abs_path is None:
        drv.get("chrome-extension://cfhdojbkjhnklbpkdaibdccddilifddb/options.html")
    else:
        # for unpacked extensions, extid are generated based on the absolute path of the extension
        ext_id = get_id_of_unpacked_chrome_extension(ext_abs_path)
        drv.get("chrome-extension://" + ext_id + "/options.html")
        #logger.debug("extension is unpacked %s" % ext_id)

    before = time.time()
    while drv.title == "":
        time.sleep(1)
        if int(time.time() - before) > 10:
            break

    if "Adblock Plus" not in drv.title:
        #logger.debug("driver title: %s" % str(drv.title))
        raise AutoFRException("Failed to install AdBlock Plus!")

    drv.switch_to.frame(0)

    # disallow
    if hasattr(drv, "find_element_by_id"):
        drv.find_element_by_id("acceptable-ads-allow").click()
    else:
        drv.find_element(By.ID, "acceptable-ads-allow").click()

    try:
        if hasattr(drv, "find_elements_by_css_selector"):
            rec_buttons_found = drv.find_elements_by_css_selector("#recommend-protection-list-table > button")
        else:
            rec_buttons_found = drv.find_elements(By.CSS_SELECTOR, "#recommend-protection-list-table > button")

        for btn in rec_buttons_found:
            if btn.get_attribute("aria-checked") == "true":
                btn.click()
                #logger.info("toggled button off: %s", btn.get_attribute("data-action"))
    except WebDriverException as e:
        logger.warning(f"Could not toggle off recommend buttons, {repr(e)} {e}")

    # go to advanced tab
    if hasattr(drv, "find_element_by_link_text"):
        drv.find_element_by_link_text("Advanced").click()
    else:
        drv.find_element(By.LINK_TEXT, "Advanced").click()

    if toggle_filter_list_off:
        time.sleep(3)

        if hasattr(drv, "find_elements_by_css_selector"):
            filter_lists_found = drv.find_elements_by_css_selector("#all-filter-lists-table > li")
        else:
            filter_lists_found = drv.find_elements(By.CSS_SELECTOR, "#all-filter-lists-table > li")

        for elem in filter_lists_found:
            filter_list_name = elem.get_attribute("aria-label")
            filter_list_url = elem.get_attribute("aria-label")
            # turn off everything that is not "ABP filters"
            if filter_list_name != "ABP filters":
                if hasattr(elem, "find_element_by_css_selector"):
                    toggle_button = elem.find_element_by_css_selector("io-toggle > button")
                else:
                    toggle_button = elem.find_element(By.CSS_SELECTOR, "io-toggle > button")

                if toggle_button.get_attribute("aria-checked") == "true":
                    drv.execute_script("arguments[0].click();", toggle_button)
                    #logger.debug("toggled filter list %s OFF" % filter_list_name)
            else:
                # turn on ABP filters
                if hasattr(elem, "find_element_by_css_selector"):
                    toggle_button = elem.find_element_by_css_selector("io-toggle > button")
                else:
                    toggle_button = elem.find_element(By.CSS_SELECTOR, "io-toggle > button")

                if toggle_button.get_attribute("aria-checked") == "false":
                    drv.execute_script("arguments[0].click();", toggle_button)
                    #logger.debug("toggled filter list %s ON" % filter_list_name)
    else:
        if hasattr(drv, "find_elements_by_css_selector"):
            filter_lists_found = drv.find_elements_by_css_selector("#all-filter-lists-table > li")
        else:
            filter_lists_found = drv.find_elements(By.CSS_SELECTOR, "#all-filter-lists-table > li")

        for elem in filter_lists_found:
            filter_list_name = elem.get_attribute("aria-label")
            if hasattr(elem, "find_element_by_css_selector"):
                toggle_button = elem.find_element_by_css_selector("io-toggle > button")
            else:
                toggle_button = elem.find_element(By.CSS_SELECTOR, "io-toggle > button")

            if toggle_button.get_attribute("aria-checked") == "true":
                logger.debug("filter list is on: %s", filter_list_name)

    drv.switch_to.parent_frame()


def take_screenshot(driver, file_name, output_directory):
    try:
        driver.save_screenshot(output_directory + os.sep + file_name + ".png")
    except (TimeoutException, WebDriverException) as e:
        logger.warning(f"Could not take screenshot {repr(e)} {e}")



# IMPORTANT: make sure this is almost the same as output_performance_logs
def wait_for_networkidle(driver,
                         threshold=4,
                         increment_threshold=3,
                         max_wait=60,
                         min_wait=20) -> list:
    """
    Wait for networkidle based on perf logs Network.requestWillBeSent only

    Returns list of outgoing webrequests
    """

    def _should_wait_more(before):
        if (time.time() - before) < min_wait:
            #logger.debug("Stopping too early, giving it more time")
            time.sleep(2)
            return True
        return False

    done = False
    before = time.time()
    webrequests = []
    increment_count = 0
    prev_event_count = 99999999
    while not done:
        perf_logs = driver.get_log("performance")
        count = 0

        for event in perf_logs:
            if "Network.requestWillBeSent" in event["message"]:
                count += 1
                if "requestWillBeSentExtraInfo" not in event["message"]:
                    message_json = json.loads(event["message"])
                    url = get_webrequests_from_perf_event_json(message_json)
                    if url:
                        webrequests.append(url)

        logger.debug("Count of perf logs: %d", count)

        # keep track of the number of times the logs increments from previous
        # if the log keeps increasing, then we assume it is doing something continuously like
        # playing a video. So we don't need to wait longer
        if count > prev_event_count:
            increment_count += 1
        prev_event_count = count

        if count < threshold:
            if not _should_wait_more(before):
                done = True
                #logger.debug("Stopping due to threshold")

        if increment_count > increment_threshold:
            if not _should_wait_more(before):
                done = True
                #ogger.debug("Stopping due to increment threshold")

        # this deals with sites that constantly have network requests like playing a video ad.
        if not done and (time.time() - before > max_wait):
            done = True
            #logger.debug("Stopping due to exceeding max wait")

        if not done:
            time.sleep(1)

    return webrequests


def output_performance_logs(driver,
                            output_network_file_path,
                            output_page_lifecycle_path,
                            threshold=4,
                            increment_threshold=3,
                            max_wait=60,
                            min_wait=20) -> list:
    """
    Wait for networkidle based on perf logs Network.requestWillBeSent and output files

    Returns list of outgoing webrequests
    """

    def _should_wait_more(before):
        if (time.time() - before) < min_wait:
            #logger.debug("Stopping too early, giving it more time")
            time.sleep(2)
            return True
        return False

    done = False
    before = time.time()
    webrequests = []
    increment_count = 0
    prev_event_count = 99999999
    while not done:
        perf_logs = driver.get_log("performance")
        count = 0
        with open(output_network_file_path, "a+") as network_file:
            with open(output_page_lifecycle_path, "a+") as page_file:
                for event in perf_logs:
                    if "Network.requestWillBeSent" in event["message"]:
                        network_file.write(json.dumps(event) + "\n")
                        count += 1
                        if "requestWillBeSentExtraInfo" not in event["message"]:
                            message_json = json.loads(event["message"])
                            url = get_webrequests_from_perf_event_json(message_json)
                            if url:
                                webrequests.append(url)
                    elif "Page." in event["message"]:
                        page_file.write(json.dumps(event) + "\n")

        # logger.debug("Count of perf logs: %d", count)
        # keep track of the number of times the logs increments from previous
        # if the log keeps increasing, then we assume it is doing something continuously like
        # playing a video. So we don't need to wait longer
        if count > prev_event_count:
            increment_count += 1
        prev_event_count = count

        if count < threshold:
            if not _should_wait_more(before):
                done = True
                #logger.debug("Stopping due to threshold")

        if increment_count > increment_threshold:
            if not _should_wait_more(before):
                done = True
                #logger.debug("Stopping due to increment threshold")

        # this deals with sites that constantly have network requests like playing a video ad.
        if not done and (time.time() - before > max_wait):
            done = True
            #logger.debug("Stopping due to exceeding max wait")

        if not done:
            time.sleep(1)

    return webrequests


def get_webrequests_from_perf_json(file_path: str) -> list:
    """
    Read from file_path where each line is a perf log event in JSON format
    """
    webrequests = []
    with open(file_path) as webrequests_file:
        for line in webrequests_file:
            try:
                line_json = json.loads(line.strip())
                message_json = json.loads(line_json["message"])
                url = get_webrequests_from_perf_event_json(message_json)
                if url:
                    webrequests.append(url)
            except json.JSONDecodeError as e:
                logger.warning(f"Could not parse json of perf log {repr(e)} {e}")
    return webrequests


def get_webrequests_from_perf_event_json(event: typing.Any) -> typing.Optional[str]:
    try:
        if "Network.requestWillBeSent" == event["message"]["method"]:
            url = event["message"]["params"]["request"]["url"]
            if not should_skip_perf_url(url):
                return url
    except (TypeError, KeyError) as e:
        logger.warning(f"Could not get url from perf log event: {event}, {repr(e)} {e}")

    return None

def get_node_stack_traces_of_annotated_images(driver) -> dict:
    """
    Retrieves the image node stack traces by leveraging our annotation flg-image=true.
    """
    return get_node_stack_traces_of_elements(driver, "[flg-image]")

def get_node_stack_traces_of_annotated_iframe_ads(driver) -> dict:
    """
    Retrieves the iframe node stack traces by leveraging our annotation flg-ad=true.
    """
    return get_node_stack_traces_of_elements(driver, "[flg-ad]")


def get_node_stack_traces_of_elements(driver, selector: str) -> dict:
    """
    Highly experimental
    Retrieves the elements (not node) based on selector.
    """
    # https://chromedevtools.github.io/devtools-protocol/tot/DOM/#method-getNodeStackTraces
    result = dict()
    try:
        doc_node = driver.execute_cdp_cmd("DOM.getDocument", {})
        node_ids = driver.execute_cdp_cmd("DOM.querySelectorAll",
                                          {"nodeId": doc_node["root"]["nodeId"], "selector": selector})
        for node_id in node_ids.get("nodeIds"):
            # not all nodes will have stacktraces
            node_stack_traces = driver.execute_cdp_cmd("DOM.getNodeStackTraces", {"nodeId": node_id})
            #logger.debug(f"{node_id}: node stack traces: {node_stack_traces}")

            if "creation" in node_stack_traces:
                describe_node = driver.execute_cdp_cmd("DOM.describeNode", {"nodeId": node_id})
                #logger.debug(f"{node_id} described: {describe_node}")
                node_stack_traces[CDP_NODEID] = node_id
                # get backendNodeId, which matches with the adgraph node ids
                if "node" in describe_node and CDP_BACKENDNODEID in describe_node["node"]:
                    backend_node_id = describe_node["node"][CDP_BACKENDNODEID]
                    node_stack_traces[CDP_BACKENDNODEID] = backend_node_id
                    result[backend_node_id] = node_stack_traces
    except:
        logger.warning(f"Could not get the images stack traces from CDP")

    #logger.debug(f"Got node stack traces from CDP: {len(result)} using selector {selector}")
    return result


def get_node_stack_traces_of_annotated_textnodes(driver: webdriver.Chrome) -> dict:
    """
    Highly experimental
    Retrieves the textnodes by first leveraging our <flg-textnode> custom tags. Then get the preceding-sibling, which should be the textnode
    """

    get_textnode_js_str = """
        let results = [];
        let query = document.evaluate('//flg-textnode/preceding-sibling::text()', document,
            null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
        for (let i = 0, length = query.snapshotLength; i < length; ++i) {
            results.push(query.snapshotItem(i));
        }
        results;
    """

    result = dict()
    try:
        # 1. get the textnodes in a list (returns an array object but not the actual list of objectIds that we need)
        eval_result = driver.execute_cdp_cmd("Runtime.evaluate",
                                             {"expression": get_textnode_js_str, "generatePreview": True})

        # 2. get the properties to get the objectId of each textnode
        properties = driver.execute_cdp_cmd("Runtime.getProperties",
                                            {"objectId": eval_result.get("result").get(CDP_OBJECTID)})

        # 3. For each textnode with objectId in the result, we get the node stacktraces and make sure we get the
        # backendNodeId example:  {'configurable': True, 'enumerable': True, 'isOwn': True, 'name': '350',
        # 'value': {'className': 'Text', 'description': '#text', 'objectId': '8005738278229584145.1.358', 'subtype':
        # 'node', 'type': 'object'}, 'writable': True}
        for result_node_prop in properties.get("result"):
            # for each text node
            if result_node_prop.get("enumerable") is True and result_node_prop.get("value").get("className") == "Text":
                request_node = driver.execute_cdp_cmd("DOM.requestNode",
                                                      {"objectId": result_node_prop.get("value").get(CDP_OBJECTID)})
                node_id = request_node.get(CDP_NODEID)
                node_stack_traces = driver.execute_cdp_cmd("DOM.getNodeStackTraces", {"nodeId": node_id})
                if "creation" in node_stack_traces:
                    describe_node = driver.execute_cdp_cmd("DOM.describeNode", {"nodeId": node_id})
                    node_stack_traces[CDP_NODEID] = node_id
                    # get backendNodeId, which matches with the adgraph node ids
                    if "node" in describe_node and CDP_BACKENDNODEID in describe_node["node"]:
                        backend_node_id = describe_node["node"][CDP_BACKENDNODEID]
                        node_stack_traces[CDP_BACKENDNODEID] = backend_node_id
                        result[backend_node_id] = node_stack_traces
    except:
        logger.warning(f"Could not get the textnode stack traces from CDP")

    #logger.debug(f"Got textnode stack traces from CDP: {len(result)}")

    return result


def switch_to_frame(driver, flg_iframe_id: str, max_try: int = 3) -> bool:
    try_count = 0
    success = False
    while try_count < max_try:
        try:
            if hasattr(driver, "find_element_by_css_selector"):
                element = driver.find_element_by_css_selector(f"iframe[flg-iframe-id='{flg_iframe_id}']")
            else:
                element = driver.find_element(By.CSS_SELECTOR, f"iframe[flg-iframe-id='{flg_iframe_id}']")

            if element is not None and element.is_displayed():
                #logger.info(f"element {flg_iframe_id} is displayed, about to switch")
                wait = WebDriverWait(driver, 2)
                wait.until(EC.frame_to_be_available_and_switch_to_it(element))
                success = True
                break
        except (StaleElementReferenceException) as e:
            logger.debug(f"Retrying: Stale iframe element {flg_iframe_id}: {repr(e)} {e}")
            try_count += 1
        except (NoSuchFrameException, NoSuchElementException, TimeoutException) as e:
            # if frame no longer exists, then no need to try again
            logger.debug(f"NoSuchFrameException: iframe of {flg_iframe_id} no longer exists: {repr(e)} {e}")
            break
        except:
            logger.warning(f"Unexpected exception while switching iframes {flg_iframe_id}")
            traceback.print_exc()
            break

    #logger.debug(f"try count {try_count} for parent frame {flg_iframe_id}")
    return success


def switch_to_defaultcontent(driver: webdriver.Chrome):
    try:
        driver.switch_to.default_content()
    except WebDriverException as e:
        logger.debug(f"Could not switch to default frame, trying active_element {e}")
        driver.switch_to.active_element
        driver.switch_to.default_content()



# taken from https://github.com/ultrafunkamsterdam/undetected-chromedriver/blob/master/undetected_chromedriver/patcher.py
def gen_random_cdc():
    cdc = random.choices(string.ascii_lowercase, k=26)
    cdc[-6:-4] = map(str.upper, cdc[-6:-4])
    cdc[2] = cdc[0]
    cdc[3] = "_"
    return "".join(cdc).encode()


def is_binary_patched(executable_path):
    """simple check if executable is patched.
    :return: False if not patched, else True
    """
    with io.open(executable_path, "rb") as fh:
        for line in iter(lambda: fh.readline(), b""):
            if b"cdc_" in line:
                return False
        else:
            return True


def patch_exe(executable_path) -> int:
    """
    Patches the ChromeDriver binary
    :return: False on failure, binary name on success
    """
    logger.debug("patching driver executable %s" % executable_path)

    linect = 0
    replacement = gen_random_cdc()
    with io.open(executable_path, "r+b") as fh:
        for line in iter(lambda: fh.readline(), b""):
            if b"cdc_" in line:
                fh.seek(-len(line), 1)
                newline = re.sub(b"cdc_.{22}", replacement, line)
                fh.write(newline)
                linect += 1
        return linect
