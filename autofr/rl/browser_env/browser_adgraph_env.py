import glob
import logging
import os
import shutil
import time
import traceback
import typing

from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, WebDriverException
from selenium.webdriver.common.by import By

from autofr.common.adgraph_version import get_adgraph_version
from autofr.common.exceptions import MissingRawAdgraphException, SiteSnapshotInvalid
from autofr.common.selenium_utils import get_node_stack_traces_of_annotated_iframe_ads, \
    get_node_stack_traces_of_annotated_images, get_node_stack_traces_of_annotated_textnodes, switch_to_defaultcontent, \
    switch_to_frame, \
    trigger_js_event_annotate_iframe_as_ad, trigger_js_event_label_iframes_with_ids_selenium
from autofr.common.utils import dump_to_json, TOPFRAME
from autofr.rl.browser_env.browser_env import BrowserWithAdHighlighter
from autofr.rl.browser_env.reward import SiteFeedback
from autofr.rl.controlled.site_snapshot import SiteSnapshot, get_adgraph_rendering_output_dir, \
    clean_adgraph_rendering_dir, \
    FLG_IFRAME_ID, get_main_raw_adgraph_file_path

logger = logging.getLogger(__name__)
ADGRAPH_DIR = "adgraph"
NOT_VISITED = "not_visited"
PARTIAL_VISITED = "partial_visited"

CDP_IMAGES_NODE_STACK_TRACES_FILE = "images_cdp_node_stack_traces"
CDP_TEXTNODES_NODE_STACK_TRACES_FILE = "textnodes_cdp_node_stack_traces"
CDP_ADS_NODE_STACK_TRACES_FILE = "ads_cdp_node_stack_traces"

class AdgraphBrowserWithAdHighlighter(BrowserWithAdHighlighter):
    # these hardcoded strings are taken from AdGraph
    ADGRAPH_SAVE_JS = "document.createCDATASection('NOTVERYUNIQUESTRING');"
    ADHIGHLIGHTER_AD_CLASS = "CITP_isAnAd"

    def __init__(self, *args, **kwargs):
        kwargs["tmp_url"] = None
        super(AdgraphBrowserWithAdHighlighter, self).__init__(*args, **kwargs)
        self.ads_annotated = 0
        self.site_feedback = None
        self.tmp_url = None
        self._snapshot_klass = SiteSnapshot
        self._snapshot = None

    def _create_dirs(self):
        super()._create_dirs()
        self.adgraph_dir = self.output_path + os.sep + ADGRAPH_DIR

    def move_adgraphs_to_output(self):
        adgraph_default_dir = get_adgraph_rendering_output_dir()
        if os.path.isdir(adgraph_default_dir):
            shutil.rmtree(self.adgraph_dir, ignore_errors=True)
            shutil.copytree(adgraph_default_dir, self.adgraph_dir,
                            ignore_dangling_symlinks=True)
            clean_adgraph_rendering_dir()
        else:
            logger.warning(f"Missing {adgraph_default_dir}")

    def clean_up(self):
        super().clean_up()
        self.move_adgraphs_to_output()
        if os.path.isdir(self.adgraph_dir):
            adgraph_raw_file_path = get_main_raw_adgraph_file_path(self.adgraph_dir, self.url)
            if not adgraph_raw_file_path:
                raise MissingRawAdgraphException(f"Could not find main raw adgraph for {self.adgraph_dir}")

            # this converts the raw adgraph into site snapshots
            self._snapshot = self._snapshot_klass(self.url,
                         base_name=self.agent_name,
                         output_directory=self.output_path,
                         adgraph_raw_file_path=adgraph_raw_file_path)

            if not self._snapshot.has_ads() or not self._snapshot.has_page_content():
                raise SiteSnapshotInvalid("Site snapshot does not have ads or any page content (no images and textnodes)")


    def _get_all_adgraph_files(self) -> list:
        rendering_stream_dir = get_adgraph_rendering_output_dir()
        adgraph_raw_file_paths = glob.glob(rendering_stream_dir + os.sep + "**" + os.sep + "log*.json",
                                               recursive=True)
        return adgraph_raw_file_paths

    def _get_latest_adgraph_file(self) -> typing.Optional[str]:
        adgraph_raw_file_paths = self._get_all_adgraph_files()
        if len(adgraph_raw_file_paths) > 0:
            latest_file = max(adgraph_raw_file_paths, key=os.path.getmtime)
            #logger.debug(f"Found latest adgraph file: {latest_file}")
            return latest_file

    def _save_adgraph(self, iframe_flg_id: str = None, sleep_time: int = 0.2) -> typing.Tuple[
        typing.Optional[str], typing.Optional[str]]:
        try:
            self.driver.execute_script(self.ADGRAPH_SAVE_JS)
        except BaseException as ex:
            logger.warning(f'Could not save adgraph: ', str(ex))
        else:
            time.sleep(sleep_time)

            if iframe_flg_id:
                latest_file = self._get_latest_adgraph_file()
                if latest_file:
                    done_writing = False
                    before = time.time()
                    while not done_writing:
                        try:
                            with open(latest_file, "r"):
                                done_writing = True
                        except OSError as e:
                            logger.warning(f"file {latest_file} is not done writing {repr(e)} {e}")
                            time.sleep(0.1)

                    if FLG_IFRAME_ID not in latest_file:
                        # do replacement this way to be affected by urls that has the word json in it
                        new_file_name = latest_file[:-len(".json")] + f"{FLG_IFRAME_ID}{iframe_flg_id}.json"
                        return latest_file, new_file_name
                    else:
                        logger.warning(f"Could not find file to rename: {latest_file}")
        return None, None

    def _before_leave_site(self, iteration: int = 0):
        super()._before_leave_site(iteration=iteration)
        self._save_adgraph()

    def annotate_iframes(self) -> int:
        """
        Annotate iframes and count number of iframes identified by AdHighlighter
        returns the number of ads annotated
        """
        logger.info("Annotating iframes")

        def _annotate_as_ad(_iframe_to_annotate_id) -> bool:
            # annotate the top frames as ads
            #self.driver.switch_to.default_content()
            switch_to_defaultcontent(self.driver)
            annotate_success = trigger_js_event_annotate_iframe_as_ad(self.driver, _iframe_to_annotate_id)
            if annotate_success:
                self.ads_annotated += 1
                #logger.debug(f"Annotate iframe as ad {_iframe_to_annotate_id}")

            else:
                logger.debug(f"Could not annotate iframe as ad {_iframe_to_annotate_id}")
                with open(self.downloads_path + os.sep + "main.html", "w") as f:
                    f.write(self.driver.page_source)
            return annotate_success

        adgraph_files_to_rename = []
        # keep track of frames to annotate later
        iframes_to_annotate = []
        # For crawling sub frames
        iframe_elements_queue = []
        top_level_iframes = []

        prefix = TOPFRAME
        iframes_found = trigger_js_event_label_iframes_with_ids_selenium(self.driver, prefix)
        for index in range(0, iframes_found):
            frame_id = f"{prefix}{index}"
            iframe_elements_queue.append((frame_id, [], NOT_VISITED))
            top_level_iframes.append(frame_id)

        current_iframe_context = None
        while len(iframe_elements_queue) > 0:
            try:
                iframe_holder = iframe_elements_queue.pop()
                iframe_flg_id = iframe_holder[0]
                iframe_parents = iframe_holder[1]
                visit_status = iframe_holder[2]

                # always switch to default content when it is part of top_level_iframes
                if iframe_flg_id in top_level_iframes and current_iframe_context:
                    #self.driver.switch_to.default_content()
                    #switch_to_defaultcontent(self.driver)
                    current_iframe_context = None

                # this is done
                if visit_status == PARTIAL_VISITED:
                    if iframe_flg_id not in top_level_iframes:
                        current_iframe_context = None
                    #logger.debug(f"done with visit for {iframe_flg_id}")
                    continue

                if not current_iframe_context:
                    switch_to_defaultcontent(self.driver)
                    for parent_flg_id in iframe_parents:
                        switch_success = switch_to_frame(self.driver, parent_flg_id)
                        if not switch_success:
                            raise WebDriverException(f"Could not switch to parent iframe {parent_flg_id}")
                        current_iframe_context = parent_flg_id

                # switch to iframe at hand
                switch_success = switch_to_frame(self.driver, iframe_flg_id)
                if not switch_success:
                    raise WebDriverException(f"Could not switch to current iframe {iframe_flg_id}")
                current_iframe_context = iframe_flg_id
                #logger.debug(f"Current iframe context: {current_iframe_context}")

                ad_match = None
                try:
                    if hasattr(self.driver, "find_element_by_class_name"):
                        ad_match = self.driver.find_element_by_class_name(self.ADHIGHLIGHTER_AD_CLASS)
                    else:
                        ad_match = self.driver.find_element(By.CLASS_NAME, self.ADHIGHLIGHTER_AD_CLASS)

                except NoSuchElementException as e:
                    logger.debug(f"No {self.ADHIGHLIGHTER_AD_CLASS} found, {e}")

                prefix = f"{iframe_flg_id}_"
                child_iframes_found = trigger_js_event_label_iframes_with_ids_selenium(self.driver, prefix)

                if child_iframes_found > 0:
                    # add the current one back in the stack
                    iframe_elements_queue.append((iframe_flg_id, iframe_parents, PARTIAL_VISITED))

                # add the children
                new_iframe_parents = iframe_parents + [iframe_flg_id]
                for index in range(0, child_iframes_found):
                    iframe_elements_queue.append((f"{prefix}{index}", new_iframe_parents, NOT_VISITED))

                # save current frame, and rename later
                file_name, new_file_name = self._save_adgraph(iframe_flg_id=iframe_flg_id)
                if file_name:
                    adgraph_files_to_rename.append((file_name, new_file_name))

                # if there are no children, then switch up again
                if child_iframes_found == 0:
                    switch_to_defaultcontent(self.driver)
                    current_iframe_context = None

                if ad_match:
                    # annotate the top frames as ad ASAP before it changes
                    # even if this element changes later on, we still captured it in the timeline
                    iframe_to_annotate_id = iframe_flg_id
                    if len(iframe_parents) > 0:
                        iframe_to_annotate_id = iframe_parents[0]
                    iframes_to_annotate.append(iframe_to_annotate_id)
                    _annotate_as_ad(iframe_to_annotate_id)
                    current_iframe_context = None

            except StaleElementReferenceException:
                logger.debug('Stale element encountered')
                logger.debug(traceback.format_exc())
                current_iframe_context = None
                #self.driver.switch_to.default_content()
                #switch_to_defaultcontent(self.driver)
            except WebDriverException:
                logger.warning(traceback.format_exc())
                current_iframe_context = None

        # rename output files to correspond flg-iframe-ids
        for file_name, new_file_name in adgraph_files_to_rename:
            if os.path.isfile(file_name):
                #logger.debug(f"Renaming file {file_name} to {new_file_name}")
                os.rename(file_name, new_file_name)

        switch_to_defaultcontent(self.driver)
        return self.ads_annotated

    def _visit_url(self, iteration: int = 0, suffix: str = "",
                   force_wait_time: int = None) -> list:
        webrequests = super()._visit_url(iteration=iteration, suffix=suffix,
                                         force_wait_time=force_wait_time)

        # annotate iframes
        time.sleep(5)

        # annotate iframes
        self.annotate_iframes()
        logger.info(f"Ads annotated: {self.ads_annotated}")

        return webrequests

    def _get_site_feedback(self) -> SiteFeedback:
        """
        The ads counter should be the one we annotated to make sure we get good snapshots
        """
        site_feedback = super(AdgraphBrowserWithAdHighlighter, self)._get_site_feedback()
        site_feedback.ad_counter = self.ads_annotated

        # EXPERIMENTAL
        if get_adgraph_version().is_new_adgraph():
            results = get_node_stack_traces_of_annotated_images(self.driver)
            dump_to_json(results, CDP_IMAGES_NODE_STACK_TRACES_FILE, self.downloads_path)
            results = get_node_stack_traces_of_annotated_textnodes(self.driver)
            dump_to_json(results, CDP_TEXTNODES_NODE_STACK_TRACES_FILE, self.downloads_path)
            results = get_node_stack_traces_of_annotated_iframe_ads(self.driver)
            dump_to_json(results, CDP_ADS_NODE_STACK_TRACES_FILE, self.downloads_path)

        return site_feedback

    def _end_iteration(self, reset_counters: bool = False, clear_cookies: bool = False):
        super()._end_iteration(reset_counters=reset_counters, clear_cookies=clear_cookies)
