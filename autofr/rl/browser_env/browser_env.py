import glob
import logging
import os
import random
import shutil
import time
from typing import Any, Tuple

import pandas as pd
from pyvirtualdisplay import Display
from selenium.common.exceptions import WebDriverException, TimeoutException, ElementNotInteractableException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By

from autofr.common.adgraph_version import get_adgraph_version
from autofr.common.filter_rules_utils import create_whitelist_rule_simple, output_filter_list, \
    get_filter_records_by_rule
from autofr.common.selenium_utils import create_driver_with_adhighlilghter, BLANK_CHROME_PAGE, \
    trigger_js_event_for_refresh_filterlist, \
    trigger_js_event_get_all_image_elements, trigger_js_event_for_get_adchoice_counter, setup_adblock_plus, \
    trigger_js_event_for_reset_adchoice_counter, take_screenshot, \
    trigger_js_event_for_get_abp_hitrecords, trigger_js_event_for_reset_abp_hitrecords, \
    trigger_js_event_get_all_text_nodes, output_performance_logs, \
    trigger_js_event_for_get_dissimilar_hashes, scroll_page, scroll_to_bottom
from autofr.common.utils import get_domain_only_from_url, \
    dump_to_json, WEBREQUESTS_DATA_FILE_SUFFIX
from autofr.rl.browser_env.reward import SiteFeedback

logger = logging.getLogger(__name__)

BLOCK_DECISION = "block_decision"
STATS_INIT_FILE_NAME = "stats_init.csv"
STATS_FILE_NAME = "stats.csv"
ABP_HITRECORDS_SUFFIX = "_abp_hitrecords"
DISSIMILAR_HASH_NAME = "dissimilar_hashes"
FILTER_LISTS_DIR_NAME = "filter_lists"
JSON_DIR_NAME = "json"
GOOGLE_TMP_URL = "https://www.google.com/"
VISIBLE_IMAGES_FILE_NAME = "visible_images.csv"
VISIBLE_TEXTNODES_FILE_NAME = "visible_textnodes.csv"
FILTER_LIST_NAME = "abp-filters-anti-cv"


class BrowserWithAdHighlighterBase:

    def __init__(self,
                 url: str,
                 adblock_proxy_path: str,
                 ad_highlighter_ext_path: str,
                 downloads_path: str,
                 adblock_ext_path: str = None,
                 agent_name: str = "",
                 chrome_driver_path: str = "chromedriver",
                 tmp_url: str = GOOGLE_TMP_URL,
                 wait_time: int = 45,
                 display_width: int = 2560,
                 display_height: int = 1080 * 3,
                 default_profile_path: str = None,
                 profile_path: str = None,
                 clean_up_profile_path: bool = True,
                 browser_path: str = None,
                 init_state_iterations: int = 4,
                 w_threshold: float = 0.90,
                 min_ad_threshold: int = 2,
                 take_screenshot_action: bool = False,
                 do_initial_state_only: bool = False,
                 whitelist_rules: list = None,
                 current_filter_rules: list = None,
                 save_dissimilar_hashes: bool = False,
                 disable_isolation: bool = True,
                 ):

        self.url = url
        self.adblock_ext_path = adblock_ext_path
        self.adblock_proxy_path = adblock_proxy_path
        self.ad_highlighter_ext_path = ad_highlighter_ext_path
        self.downloads_path = downloads_path
        self.chrome_driver_path = chrome_driver_path
        self.tmp_url = tmp_url
        self.wait_time = wait_time
        self.default_profile_path = default_profile_path
        self.profile_path = profile_path
        self.clean_up_profile_path = clean_up_profile_path
        self.browser_path = browser_path
        self.agent_name = agent_name
        self.init_state_iterations = init_state_iterations
        self.w_threshold = w_threshold
        self.main_domain = get_domain_only_from_url(self.url)
        self.tmp_domain = None
        if self.tmp_url:
            self.tmp_domain = get_domain_only_from_url(self.tmp_url)
        self.display_width = display_width
        self.display_height = display_height
        self.min_ad_threshold = min_ad_threshold
        self.take_screenshot_action = take_screenshot_action
        self.do_initial_state_only = do_initial_state_only
        self.whitelist_rules = whitelist_rules or []
        self.current_filter_rules = current_filter_rules or []
        self.driver = None
        self.abp_hitrecords = {}
        self.should_setup_abp = True
        self.current_images = []
        self.current_textnodes = []
        self.save_dissimilar_hashes = save_dissimilar_hashes
        self.disable_isolation = disable_isolation

    def _get_empty_data_object(self) -> dict:
        raise NotImplementedError("Need to implement the structure of the data object")

    def _create_data_object(self, aggregate_data: list,
                            new_site_feedback: SiteFeedback,
                            webrequests: list, iteration: int) -> Any:
        raise NotImplementedError("Need to implement the updating of data object")

    def init_drivers_and_dirs(self):
        self._create_dirs()
        self._create_displays_and_drivers()

    def __enter__(self):
        self.init_drivers_and_dirs()
        return self

    def __exit__(self, *exc):
        self.clean_up()

    def clean_up(self):

        # clean up once we are done
        if self.driver is not None:
            self.driver.quit()
        if self.display is not None:
            self.display.stop()

        time.sleep(2)
        # clean up profile
        try:
            for file_tmp in glob.glob(self.downloads_path + os.sep + "about_blank*.json"):
                os.remove(file_tmp)
            if self.tmp_domain:
                for file_tmp in glob.glob(self.downloads_path + os.sep + "*" + self.tmp_domain + "*.json"):
                    os.remove(file_tmp)
            if self.clean_up_profile_path:
                # save the logs
                if os.path.isfile(self.profile_path + os.sep + "chrome_debug.log"):
                    shutil.copy(self.profile_path + os.sep + "chrome_debug.log",
                                self.output_path + os.sep + "chrome_debug.log")
                shutil.rmtree(self.profile_path, ignore_errors=True)

            else:
                shutil.copytree(self.profile_path,
                                self.output_path + os.sep + "profile", ignore_dangling_symlinks=True)
        except OSError as e:
            logger.warning(f"Could not delete profile: {repr(e)} {e}")

    def _get_custom_exts(self) -> list:
        exts = []
        if self.adblock_ext_path:
            exts.append(self.adblock_ext_path)
        exts.append(self.ad_highlighter_ext_path)
        return exts

    def _create_displays_and_drivers(self):
        before = time.time()
        old_display = os.environ.get("DISPLAY")

        self.display = Display(visible=False, size=(self.display_width, self.display_height))
        self.display.start()

        os.environ["DISPLAY"] = self.display.new_display_var
        #logger.debug("Time it took to create virtual display %d", int(time.time() - before))

        before_driver = time.time()
        # load three extensions:
        # (1) the custom adblockplus that will read from our custom filter rule file,
        # (2) ad-highlighter
        # NOTE: ORDER MATTERS
        chrome_exts_path = ",".join(self._get_custom_exts())
        self.driver = create_driver_with_adhighlilghter(
            browser_binary_path=self.browser_path,
            chrome_driver_path=self.chrome_driver_path,
            chrome_default_download_directory=self.downloads_path,
            profile_path=self.profile_path,
            chrome_ext_path=chrome_exts_path,
            include_window_size=True,
            include_browser_logging=False,
            window_width=self.display_width,
            window_height=self.display_height,
            disable_isolation=self.disable_isolation)

        #logger.debug("Time it took to create driver %d", int(time.time() - before_driver))

        if old_display is not None:
            os.environ["DISPLAY"] = old_display

        if self.should_setup_abp and self.adblock_ext_path:
            before_abp = time.time()
            setup_adblock_plus(self.driver, ext_abs_path=self.adblock_ext_path)
            # logger.debug("Done setting up adblock plus settings")
            #logger.debug("Time it took to setup abp %d", int(time.time() - before_abp))

        # make sure the filter list being used is refreshed
        if self.adblock_ext_path:
            before_abp = time.time()
            if self.tmp_url:
                self.driver.get(self.tmp_url)
            trigger_js_event_for_refresh_filterlist(self.driver)
            self.driver.get(BLANK_CHROME_PAGE)
            if self.tmp_url:
                self.driver.get(self.tmp_url)
            #logger.debug("Time it took to refresh filter list %d", int(time.time() - before_abp))

        logger.debug("Overall _create_displays_and_drivers %d", int(time.time() - before))

    def _create_dirs(self):
        # randomize the download output file + create necessary directories
        self.output_path = self.downloads_path + os.sep + self.agent_name
        os.makedirs(self.output_path, exist_ok=True)
        # logger.info("Output will be in: %s" % self.output_path)

        self.downloads_path = self.output_path + os.sep + JSON_DIR_NAME
        os.makedirs(self.downloads_path, exist_ok=True)
        # logger.info("Downloads will be in: %s" % self.downloads_path)

        if not self.profile_path:
            self.profile_path = os.sep + "dev" + os.sep + "shm" + os.sep + self.agent_name + "_profile"
            #if self.default_profile_path and os.path.isdir(self.default_profile_path):
            #    try:
            #        # this profile should already have everything set up
            #        shutil.copytree(self.default_profile_path, self.profile_path, ignore_dangling_symlinks=True)
            #        self.should_setup_abp = False
            #        logger.info("Copied default profile path to new destination")
            #    except OSError as e:
            #        logger.warning('Directory not copied. Error: %s' % e)
            #        raise e
            #else:
            os.makedirs(self.profile_path, exist_ok=True)

        # logger.info("Browser profile will be in: %s" % self.profile_path)

        self.screenshot_dir = self.output_path + os.sep + "screenshots"
        os.makedirs(self.screenshot_dir, exist_ok=True)
        # logger.info("Screenshots will be in: %s" % self.screenshot_dir)

        self.filter_list_dir = self.output_path + os.sep + FILTER_LISTS_DIR_NAME
        os.makedirs(self.filter_list_dir, exist_ok=True)
        # logger.info("Filter lists will be in: %s" % self.filter_list_dir)

        # keeps track of images
        self.images_dir = self.output_path + os.sep + "images"
        os.makedirs(self.images_dir, exist_ok=True)

    def _hover_over_iframes(self):
        a = ActionChains(self.driver)
        try:
            if hasattr(self.driver, "find_elements_by_tag_name"):
                iframes = self.driver.find_elements_by_tag_name("iframe") or []
            else:
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe") or []

            #logger.debug(f"Number of iframes found: {len(iframes)}")
            for index, i in enumerate(iframes):
                # hover over element
                if i.is_displayed():
                    try:
                        a.move_to_element(i).perform()
                        time.sleep(0.5)
                        #logger.debug(f"Hovering over iframe: {index} {i}")
                    except ElementNotInteractableException as e:
                        pass
        except (TimeoutException, WebDriverException) as e:
            logger.warning(f"Could not hover over iframes {repr(e)} {e}")
        finally:
            scroll_page(0, self.driver)

    def _visit_url(self, iteration: int = 0,
                   suffix: str = "",
                   force_wait_time: int = None,
                   page_load_timeout: int = 120) -> list:
        """
        Visits URL based on perf log

        Returns list of outgoing webrequests
        """

        logger.info(f"Visiting site {self.url}")
        before = time.time()
        self.driver.set_page_load_timeout(page_load_timeout)

        # EXPERIMENTAL
        if get_adgraph_version().is_new_adgraph():
            self.driver.execute_cdp_cmd("DOM.setNodeStackTracesEnabled", {"enable": True})

        self.driver.get(self.url)
        driver_title = self.driver.title
        logger.info(f"Got site title: {driver_title}")
        self._scroll_page(iteration=iteration)
        self._hover_over_iframes()

        if iteration == 0:
            self.driver.execute_cdp_cmd("Page.setLifecycleEventsEnabled", {"enabled": True})
            #logger.debug(f"Enabled Page.setLifecycleEventsEnabled")

        file_name = self.main_domain + str(iteration) + suffix
        latest_webreq_file_path = self.downloads_path + os.sep + file_name + WEBREQUESTS_DATA_FILE_SUFFIX
        latest_page_file_path = self.downloads_path + os.sep + "page_" + file_name + ".json"

        webrequests = output_performance_logs(self.driver,
                                                latest_webreq_file_path,
                                                latest_page_file_path,
                                                max_wait=(force_wait_time or self.wait_time))

        logger.info("Visit took: %d sec", int(time.time() - before))
        return webrequests

    def _update_whitelist_rules_by_domains(self, domains: list):
        if domains:
            for domain in domains:
                domain = domain.strip()
                if domain:
                    rule = create_whitelist_rule_simple(domain)
                    if rule and rule not in self.whitelist_rules:
                        self.whitelist_rules.append(rule)

    def _get_site_feedback(self) -> SiteFeedback:
        #logger.debug("Retrieving site feedback...")
        site_feedback = SiteFeedback()

        #self.current_images = trigger_js_event_get_all_image_elements(self.driver)
        site_feedback.image_counter = trigger_js_event_get_all_image_elements(self.driver)

        #self.current_textnodes = trigger_js_event_get_all_text_nodes(self.driver)
        site_feedback.textnode_counter = trigger_js_event_get_all_text_nodes(self.driver)

        site_feedback.ad_counter, site_feedback.ad_logo_urls = trigger_js_event_for_get_adchoice_counter(self.driver)

        logger.info(site_feedback)
        # TODO: save ad_logo_urls in a different file
        # self._update_whitelist_rules_by_domains(site_feedback.ad_logo_urls)

        return site_feedback

    def _take_screenshot(self, iteration: int, suffix: str = "", force: bool = False):
        if self.take_screenshot_action or force:
            take_screenshot(self.driver, str(iteration) + suffix, self.screenshot_dir)

    def _save_abp_hitrecords(self, iteration: int) -> Tuple[Any, int]:
        iter_abp_hitrecords, abp_hitrecords_len = trigger_js_event_for_get_abp_hitrecords(self.driver)
        self.abp_hitrecords[iteration] = (iter_abp_hitrecords, abp_hitrecords_len)
        dump_to_json(iter_abp_hitrecords, str(iteration) + ABP_HITRECORDS_SUFFIX, self.downloads_path)
        logger.info("Filter matches: %d" % abp_hitrecords_len)
        return iter_abp_hitrecords, abp_hitrecords_len

    def _save_dissimilar_hashes(self, iteration: int) -> list:
        # list of dict
        hashes = trigger_js_event_for_get_dissimilar_hashes(self.driver)
        if len(hashes) > 0:
            # add in the site url
            for x in hashes:
                x["URL"] = self.url
            df = pd.DataFrame(columns=list(hashes[0].keys()))
            df = df.from_dict(hashes)
            df.to_csv(f"{self.downloads_path}{os.sep}{DISSIMILAR_HASH_NAME}_{iteration}.csv",
                      index=False, encoding='utf-8')
        #logger.info(f"Dissimilar hashes found: {len(hashes)}")
        return hashes

    def _update_internal_filter_list_only(self, rules: list = None,
                                          whitelist_rules: list = None,
                                          iteration: int = 0,
                                          is_init_phase: bool = False):
        """
        Makes a copy of the filter list only. This is not applied
        """
        file_path = self.filter_list_dir + os.sep + FILTER_LIST_NAME + "_" + str(iteration)
        if is_init_phase:
            file_path += "_init"
        file_path += ".txt"

        all_rules = (rules or []) + (whitelist_rules or [])

        output_filter_list(
            rules=set(all_rules),
            file_path=file_path)

    def _update_filter_lists(self, rules: list = None,
                             whitelist_rules: list = None,
                             iteration: int = 0,
                             is_init_phase: bool = False):
        """
        Updates the filter list that will be applied when visiting_url, then make a copy of it
        """
        
        if not self.adblock_proxy_path:
            logger.debug("No adblocker proxy path detected")
            return

        try:
            all_rules = (rules or []) + (whitelist_rules or [])
            # pass in a list of strings (domains OR second level domains) to block multiple items
            file_path_proxy = self.adblock_proxy_path + os.sep + FILTER_LIST_NAME + ".txt"

            output_filter_list(
                rules=set(all_rules),
                file_path=file_path_proxy)

            if os.path.isfile(file_path_proxy):
                # keep the copy
                internal_copy_file_path = self.filter_list_dir + os.sep + FILTER_LIST_NAME + "_" + str(iteration)
                if is_init_phase:
                    internal_copy_file_path += "_init"
                internal_copy_file_path += ".txt"
                shutil.copyfile(file_path_proxy, internal_copy_file_path)

            # use selenium to trigger an event for the adblocker to reload
            # its filter rules from the new file above
            #logger.debug("Trigger event for adblock plus to reload filter list")
            trigger_js_event_for_refresh_filterlist(self.driver)
            time.sleep(0.5)
            trigger_js_event_for_refresh_filterlist(self.driver)
            time.sleep(5)
        except OSError as e:
            logger.error(f"Could not write out the filter list")
            raise e
        except WebDriverException as e:
            logger.error(f"Could not refresh filterlist")
            raise e

    def _create_main_dataframe(self) -> pd.DataFrame:
        data_object = self._get_empty_data_object()
        return pd.DataFrame(columns=list(data_object.keys()))

    def _end_iteration(self,
                       reset_counters=True,
                       clear_cookies: bool = True,
                       output_imgs_and_textnodes: bool = False):
        if reset_counters:
            # reset the adchoice counter within the browser
            #logger.debug("Resetting the adchoice counter...")
            trigger_js_event_for_reset_adchoice_counter(self.driver)

            # reset the adchoice counter within the browser
            #logger.debug("Resetting the abp hit records...")
            trigger_js_event_for_reset_abp_hitrecords(self.driver)

        # save the images and textnodes to file
        if output_imgs_and_textnodes:
            before = time.time()
            image_columns = ["id", "height", "width", "src"]
            #logger.debug("Outputting the visible images data into csv")
            df_images = pd.DataFrame(columns=image_columns)
            if len(self.current_images) > 0:
                df_images = df_images.from_dict(self.current_images)
                df_images.to_csv(self.output_path + os.sep + VISIBLE_IMAGES_FILE_NAME,
                                index=False, encoding='utf-8')

            textnode_columns = ["id", "coordinates", "text", "textlength"]
            #logger.debug("Outputting the visible textnodes data into csv")
            df_textnodes = pd.DataFrame(columns=textnode_columns)
            if len(self.current_textnodes) > 0:
                df_textnodes = df_textnodes.from_dict(self.current_textnodes)
                df_textnodes.to_csv(self.output_path + os.sep + VISIBLE_TEXTNODES_FILE_NAME,
                                    index=False, encoding='utf-8')

            #logger.debug(f"Time it took to output {len(self.current_images)} visible images and "
            #            f"{len(self.current_textnodes)} textnodes: {int(time.time() - before)}")

        if clear_cookies:
            self._clear_driver()

    def _clear_driver(self):
        self.driver.get(BLANK_CHROME_PAGE)
        # clear cookies
        self.driver.delete_all_cookies()

    def _sleep_after_visit(self):
        time.sleep(10)

    def _scroll_page(self, iteration: int = 0):
        # scroll to bottom
        scroll_height_found = scroll_to_bottom(self.driver)
        #logger.debug(f"scrolled to {scroll_height_found}")

        if scroll_height_found > 0:
            self._take_screenshot(iteration, suffix="_scroll", force=True)

        # scroll to top
        scroll_divide = 3
        scroll_height_remaining = scroll_height_found
        scroll_partial = int(scroll_height_remaining / scroll_divide)
        scroll_up_count = 0
        while scroll_height_remaining > 0:
            scroll_next_position = scroll_height_remaining - scroll_partial - int(100 * random.random())
            if scroll_next_position < 0:
                scroll_next_position = 0
            scroll_page(scroll_next_position, self.driver)
            #logger.info(f"scrolled to {scroll_next_position}")
            scroll_height_remaining = scroll_next_position
            scroll_up_count += 1
            if scroll_up_count > scroll_divide or scroll_height_remaining == 0:
                break
        if scroll_height_remaining > 0:
            scroll_page(0, self.driver)
        #logger.info(f"scrolled to 0 -- done")

    def _before_leave_site(self, iteration: int = 0):
        """
        Do something before we leave the site
        """
        pass

    def get_init_site_feedback(self) -> Tuple[SiteFeedback, list]:
        initial_site_feedback = SiteFeedback()

        # for the rest of this phase, we do not update the filter rules
        aggregate_data = []
        for iteration in range(self.init_state_iterations):
            logger.info("Starting gathering initial site feedback: iteration %d", iteration)

            # if there are rules to apply, then do so
            if self.current_filter_rules or self.whitelist_rules:
                self._update_filter_lists(rules=self.current_filter_rules,
                                          iteration=iteration,
                                          is_init_phase=True)

            webrequests = self._visit_url(iteration=iteration, suffix="_init")
            self._sleep_after_visit()
            # get site feedback, and update initial site feedback to keep max
            new_site_feedback = self._get_site_feedback()
            initial_site_feedback.update_keep_max(new_site_feedback)
            #logger.debug("\tInit Iteration %d, Max Site Feedback: %s", iteration, initial_site_feedback)
            self._before_leave_site(iteration=iteration)
            self._take_screenshot(iteration, suffix="_init", force=True)
            if self.current_filter_rules or self.whitelist_rules:
                self._save_abp_hitrecords(iteration)
            if self.save_dissimilar_hashes:
                self._save_dissimilar_hashes(iteration=iteration)
            if self.tmp_url:
                self.driver.get(self.tmp_url)
            data_row = self._create_data_object(aggregate_data, new_site_feedback,
                                                webrequests, iteration)
            aggregate_data.append(data_row)

            self._end_iteration()

        # save data
        df = self._create_main_dataframe()
        df = df.from_dict(aggregate_data)
        df.to_csv(self.output_path + os.sep + STATS_INIT_FILE_NAME,
                  index=False, encoding='utf-8')

        logger.info(f"Done with initial site feedback: {initial_site_feedback}")

        return initial_site_feedback, self.current_filter_rules

    def init_and_start(self):
        initial_site_feedback, rules = self.get_init_site_feedback()

        if initial_site_feedback.ad_counter < self.min_ad_threshold:
            logger.warning("Ads detected below threshold %d, so exiting...", self.min_ad_threshold)
            return

        self.start(initial_site_feedback=initial_site_feedback)

    def start(self,
              initial_site_feedback: SiteFeedback = None):

        if self.do_initial_state_only:
            logger.warning(f"Called start() when do_initial_state_only is True, exiting...")
            return

        self._update_filter_lists(rules=self.current_filter_rules,
                                  whitelist_rules=self.whitelist_rules,
                                  iteration=0)
        aggregate_data = []
        iteration = 1
        #logger.info("--------------------------------------")
        logger.info("Starting gathering site feedback: iteration %d" % (iteration))
        webrequests = self._visit_url(iteration=iteration, suffix="_start")
        self._sleep_after_visit()
        new_site_feedback = self._get_site_feedback()
        self._take_screenshot(iteration)
        self._save_abp_hitrecords(iteration)
        if self.tmp_url:
            self.driver.get(self.tmp_url)
        data_row = self._create_data_object(aggregate_data,
                                            new_site_feedback,
                                            webrequests,
                                            iteration)
        aggregate_data.append(data_row)

        self._end_iteration()

        df = self._create_main_dataframe()
        df = df.from_dict(aggregate_data)
        df.to_csv(self.output_path + os.sep + STATS_FILE_NAME,
                  index=False, encoding='utf-8')


class BrowserWithAdHighlighter(BrowserWithAdHighlighterBase):
    """
    Browser uses Ad-Highlighter
    Browser that blocks by web requests
    """

    def _get_empty_data_object(self) -> dict:
        data = {'iteration': 0,
                'ad_counter': 0,
                'image_counter': 0,
                'textnode_counter': 0,
                'filter_matches': 0,
                'block_decision_with_matches': "",
                'block_decision_no_matches': "",
                BLOCK_DECISION: ""}

        return data

    def _create_data_object(self, aggregate_data: list,
                            new_site_feedback: SiteFeedback,
                            webrequests: list, iteration: int) -> Any:

        data_row = self._get_empty_data_object()
        data_row['ad_counter'] = new_site_feedback.ad_counter
        data_row['image_counter'] = new_site_feedback.image_counter
        data_row['textnode_counter'] = new_site_feedback.textnode_counter
        data_row['iteration'] = iteration

        if iteration in self.abp_hitrecords:
            iteration_abp_hitrecords, iteration_abp_hitrecords_len = self.abp_hitrecords[iteration]
            data_row['filter_matches'] = iteration_abp_hitrecords_len

            # get block decision that matches or did not match
            if self.current_filter_rules:
                filter_records_by_rule = get_filter_records_by_rule(iteration_abp_hitrecords)
                # logger.info("filters by domain: %s" % str(filters_by_domain))

                block_decision_with_matches = []
                block_decision_no_matches = []
                for rule in self.current_filter_rules:
                    if rule in filter_records_by_rule:
                        block_decision_with_matches.append(rule)
                    else:
                        block_decision_no_matches.append(rule)

                #logger.debug("block_decision_with_matches: %s" % str(block_decision_with_matches))
                #logger.debug("block_decision_no_matches: %s" % str(block_decision_no_matches))

                data_row['block_decision_with_matches'] = ",".join(block_decision_with_matches)
                data_row['block_decision_no_matches'] = ",".join(block_decision_no_matches)

        if self.current_filter_rules:
            data_row[BLOCK_DECISION] = ",".join(self.current_filter_rules)

        return data_row


class BrowserWithAdHighlighterSimple(BrowserWithAdHighlighter):

    def start(self,
              initial_site_feedback: SiteFeedback = None):
        aggregate_data = []
        iteration = 0

        # load items to block
        len_filter_rules = 0
        if self.current_filter_rules:
            len_filter_rules = len(self.current_filter_rules)
        if len_filter_rules < 4:
            logger.info(f"Deciding to block using rule(s) ({len_filter_rules}): {self.current_filter_rules}")
        else:
            logger.info(f"Deciding to block using rule(s): {len_filter_rules}")

        self._update_filter_lists(rules=self.current_filter_rules,
                                  whitelist_rules=self.whitelist_rules,
                                  iteration=iteration)

        webrequests = self._visit_url(iteration=iteration, suffix="_start")

        # important sleep to let ad-highlighter detect ads
        # there is no way right now to figure out when ad-highlighter is done
        # as it is constantly checking the iframes for new changes
        self._sleep_after_visit()

        before_processing = time.time()
        before = time.time()
        new_site_feedback = self._get_site_feedback()
        self._take_screenshot(iteration, force=True)

        self._save_abp_hitrecords(iteration)
        #logger.info("Iteration time to get abp_hitrecords: %d", int(time.time() - before))

        data_row = self._create_data_object(aggregate_data, new_site_feedback,
                                            webrequests, iteration)

        self._end_iteration(reset_counters=False, clear_cookies=False)

        aggregate_data.append(data_row)
        df = self._create_main_dataframe()
        df = df.from_dict(aggregate_data)
        df.to_csv(self.output_path + os.sep + STATS_FILE_NAME,
                  index=False, encoding='utf-8')

        logger.info("Iteration time for processing: %d", int(time.time() - before_processing))


class BrowserCreateChromeProfile(BrowserWithAdHighlighter):
    """
    Create chrome profile only
    """

    def __init__(self, *args, **kwargs):
        super(BrowserCreateChromeProfile, self).__init__(*args, **kwargs)
        self.do_initial_state_only = True
        self.clean_up_profile_path = False
