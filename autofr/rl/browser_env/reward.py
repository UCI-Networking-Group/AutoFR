import logging
import os
import pickle
import typing

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

NOISE_THRESHOLD = 0.05
SITE_FEEDBACK_CACHE_CSV = "site_feedback_cache.pickle"


class SiteFeedback:

    def __init__(self, ad_counter=0, image_counter=0, textnode_counter=0, ad_logo_urls: list = None):
        self.ad_counter = ad_counter
        self.image_counter = image_counter
        self.textnode_counter = textnode_counter
        self.ad_logo_urls = ad_logo_urls or []

    def update_keep_max(self, feedback: 'SiteFeedback'):
        self.image_counter = max(self.image_counter, feedback.image_counter)
        self.ad_counter = max(self.ad_counter, feedback.ad_counter)
        self.textnode_counter = max(self.textnode_counter, feedback.textnode_counter)

    def __str__(self) -> str:
        return "Site Feedback: image counter %d, ad counter %d, text node counter %d" % (
        self.image_counter, self.ad_counter, self.textnode_counter)

    @staticmethod
    def create_feedback_from_data_row(data_row: pd.core.series.Series) -> 'SiteFeedback':
        feedback = SiteFeedback()
        feedback.ad_counter = data_row["ad_counter"]
        feedback.image_counter = data_row["image_counter"]
        feedback.textnode_counter = data_row["textnode_counter"]
        return feedback


class SiteFeedbackCache(dict):
    KEY = "key"
    VALUE = "value"

    def save(self, output_directory: str):
        cache_file = output_directory + os.sep + SITE_FEEDBACK_CACHE_CSV
        with open(cache_file, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def read_cache(directory: str) -> "SiteFeedbackCache":
        cache_file = directory + os.sep + SITE_FEEDBACK_CACHE_CSV
        if os.path.isfile(cache_file):
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        logger.debug(f"Could not find cache, so returning new one")
        return SiteFeedbackCache()


class SiteFeedbackRange:

    def __init__(self):
        self.site_feedbacks = []

    def set_site_feedbacks(self, df: pd.DataFrame) -> int:
        rows_added = 0
        for index, row in df.iterrows():
            feedback = SiteFeedback.create_feedback_from_data_row(row)
            self.site_feedbacks.append(feedback)
            rows_added += 1

        return rows_added

    def get_min(self) -> typing.Optional[SiteFeedback]:
        if len(self.site_feedbacks) == 0:
            return None

        ad_counter = np.min([x.ad_counter for x in self.site_feedbacks])
        image_counter = np.min([x.image_counter for x in self.site_feedbacks])
        textnode_counter = np.min([x.textnode_counter for x in self.site_feedbacks])

        return SiteFeedback(ad_counter=ad_counter,
                            image_counter=image_counter,
                            textnode_counter=textnode_counter)

    def get_max(self) -> typing.Optional[SiteFeedback]:
        if len(self.site_feedbacks) == 0:
            return None

        ad_counter = np.max([x.ad_counter for x in self.site_feedbacks])
        image_counter = np.max([x.image_counter for x in self.site_feedbacks])
        textnode_counter = np.max([x.textnode_counter for x in self.site_feedbacks])

        return SiteFeedback(ad_counter=ad_counter,
                            image_counter=image_counter,
                            textnode_counter=textnode_counter)

    def get_average(self, ignore_no_ads: bool = False) -> typing.Optional[SiteFeedback]:
        if len(self.site_feedbacks) == 0:
            return None

        # if ignore_no_ads is true, we only care about the feedback that has ads
        # use ignore_no_ads carefully
        site_feedbacks_tmp = self.site_feedbacks
        if ignore_no_ads:
            site_feedbacks_tmp = [x for x in self.site_feedbacks if x.ad_counter > 0]

        if len(site_feedbacks_tmp) == 0:
            return None

        ad_counter = round(np.average([x.ad_counter for x in site_feedbacks_tmp]))
        image_counter = round(np.average([x.image_counter for x in site_feedbacks_tmp]))
        textnode_counter = round(np.average([x.textnode_counter for x in site_feedbacks_tmp]))

        return SiteFeedback(ad_counter=ad_counter,
                            image_counter=image_counter,
                            textnode_counter=textnode_counter)

    def __str__(self) -> str:
        val = f"Number of states in SiteFeedbackRange: {len(self.site_feedbacks)}. "
        if len(self.site_feedbacks) > 0:
            avg_site_feedback = self.get_average()
            val += f"Average Site Feedback: {str(avg_site_feedback)}."
        return val


class RewardTerms:
    def __init__(self, ad_removed: float, image_missing: float,
                 textnode_missing: float, reward: float = 0,
                 breakage: float = -1, page_intact: float = -1):
        self.reward = reward
        self.ad_removed = ad_removed
        self.image_missing = image_missing
        self.textnode_missing = textnode_missing
        self.breakage = breakage
        self.page_intact = page_intact

    def __str__(self) -> str:
        return f"reward: {self.reward}, Ads Removed: {self.ad_removed}, " \
               f"Images Missing: {self.image_missing}, Textnodes Missing: {self.textnode_missing}, " \
               f"Breakage: {self.breakage}, Page Intact: {self.page_intact}"


class RewardBase:

    def __init__(self, init_site_feedback: SiteFeedback, new_site_feedback: SiteFeedback, w: float):
        self.init_site_feedback = init_site_feedback
        self.new_site_feedback = new_site_feedback
        self.w = w

    @classmethod
    def get_classname(cls):
        return cls.__name__

    def calculate_terms(self) -> RewardTerms:
        ad_removed = 0
        if self.init_site_feedback.ad_counter > 0:
            ad_counter = self.new_site_feedback.ad_counter
            if self.new_site_feedback.ad_counter > self.init_site_feedback.ad_counter:
                ad_counter = self.init_site_feedback.ad_counter
            ad_removed = (self.init_site_feedback.ad_counter - ad_counter) / self.init_site_feedback.ad_counter

        # if there are more images than before, then it is ok
        image_missing = 0
        if self.init_site_feedback.image_counter > 0:
            if abs(self.init_site_feedback.image_counter - self.new_site_feedback.image_counter) > self.init_site_feedback.image_counter:
                image_missing = 1
            else:
                image_missing = abs(self.init_site_feedback.image_counter - self.new_site_feedback.image_counter) / self.init_site_feedback.image_counter

        # if there are more text than before, then we count them as breakage (for now)
        textnode_missing = 0
        if self.init_site_feedback.textnode_counter > 0:
            if abs(self.init_site_feedback.textnode_counter - self.new_site_feedback.textnode_counter) > self.init_site_feedback.textnode_counter:
                textnode_missing = 1
            else:
                textnode_missing = abs(
                    self.init_site_feedback.textnode_counter - self.new_site_feedback.textnode_counter) / self.init_site_feedback.textnode_counter

        return RewardTerms(ad_removed, image_missing, textnode_missing)

    def calculate_page_breakage(self, reward_terms: RewardTerms) -> float:
        return (reward_terms.image_missing + reward_terms.textnode_missing) / 2

    def calculate_page_intact(self, reward_terms: RewardTerms) -> float:
        page_breakage = self.calculate_page_breakage(reward_terms)
        return 1 - page_breakage

    def calculate(self) -> RewardTerms:
        raise NotImplementedError()


class RewardByCasesVer1 (RewardBase):
    """
    Calculates reward based on specific cases:
    1. if the action did not help at all with blocking ads, it will always get -1
    2. otherwise, if it caused breakage beyond w, then it gets 0
    3. otherwise, reward is how much the filter rule helped block rules (ad_removed)
    """

    def calculate(self) -> RewardTerms:
        reward_terms = self.calculate_terms()

        page_breakage = self.calculate_page_breakage(reward_terms)
        page_intact = 1 - page_breakage
        if reward_terms.ad_removed <= 0:
            reward = -1
        else:
            if page_intact < self.w:
                reward = 0
            else:
                reward = reward_terms.ad_removed

        reward_terms.reward = reward
        reward_terms.breakage = page_breakage
        reward_terms.page_intact = page_intact

        return reward_terms


def get_site_feedback_range_from_file(file_path: str) -> typing.Optional[SiteFeedbackRange]:
    """
    Given a file of file_path, we return the max counters
    """

    if os.path.isfile(file_path):
        pd_stats = pd.read_csv(file_path)
        feedback_range = SiteFeedbackRange()
        feedback_range.set_site_feedbacks(pd_stats)
        return feedback_range
    return None


def get_site_feedback_from_file(file_path: str, index: int = 0) -> typing.Optional[SiteFeedback]:
    """
    Given file_path, we return the index row as the state
    """

    if os.path.isfile(file_path):
        pd_stats = pd.read_csv(file_path)
        site_feedback = SiteFeedback()
        site_feedback.ad_counter = pd_stats["ad_counter"][index]
        site_feedback.image_counter = pd_stats["image_counter"][index]
        site_feedback.textnode_counter = pd_stats["textnode_counter"][index]
        return site_feedback
    return None


def get_reward_klass(reward_func_name: str = RewardByCasesVer1.get_classname()) \
        -> typing.Callable:
    for reward_klass in RewardBase.__subclasses__():
        if reward_func_name == reward_klass.get_classname():
            return reward_klass


