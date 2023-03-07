import json
import logging
import os
import typing

import numpy as np

from autofr.common.filter_rules_utils import RULES_DELIMITER, FilterRuleBlockRecord, create_rule_simple, \
    output_filter_list_with_value, output_filter_list
from autofr.common.utils import get_unique_str, json_convert_helper
from autofr.rl.action_space import ACTION_ATTEMPTS, SLEEPING_ARM, Q_VALUE, QUCB_VALUE, AVG_REWARD, \
    REWARD, UNKNOWN_ARM, Q_VALUE_FROM_PRIOR, AD_COUNTER, IMAGE_COUNTER, TEXTNODE_COUNTER, \
    AD_REMOVED, TEXTNODE_MISSING, IMAGE_MISSING, INIT_NODE_HISTORY_ACTION_TIMES, NODE_HISTORY_ACTION_TIMES, \
    NO_MATCH_NODE_HISTORY_ACTION_TIMES, NODE_HISTORY_Q, \
    NODE_HISTORY_AGENT_INFO, NODE_HISTORY_AGENT_INFO__INIT_STATE_INFO, NODE_HISTORY_AGENT_INFO__INIT_STATE_MIN, \
    NODE_HISTORY_AGENT_INFO__INIT_STATE_MAX, NODE_HISTORY_AGENT_INFO__INIT_STATE_AVERAGE, ROUND_HISTORY, \
    ActionSpace, DEFAULT_Q_VALUE, ACTION_SPACE, ACTION_SPACE_TOTAL_NODES, ACTION_SPACE_TOTAL_EDGES, \
    ACTION_SPACE_EXPLORED_NODES, CHOSEN_ACTIONS
from autofr.rl.base import Agent as BanditsAgent
from autofr.rl.browser_env.reward import SiteFeedback, RewardTerms, NOISE_THRESHOLD
from autofr.rl.policy import DomainHierarchyUCBPolicy

logger = logging.getLogger(__name__)

DH_NODE_HISTORY = "dh_nodes_history"
FINAL_RULES = "final_rules"
LOW_Q_RULES = "low_q_rules"


class DomainHierarchyAgent(BanditsAgent):
    """
    An Agent is able to take one of a set of actions at each time step. The
    action is chosen using a strategy based on the history of prior actions
    and outcome observations.
    """

    def __init__(self, bandit: "DomainHierarchyMAB",
                 policy=None, prior=0, gamma=None,
                 output_directory=None, stop=False,
                 noise_threshold: float = NOISE_THRESHOLD,
                 default_q_value: float = DEFAULT_Q_VALUE,
                 action_space_class: typing.Callable = ActionSpace):
        self.policy = policy or DomainHierarchyUCBPolicy()
        self.bandit = bandit
        self.prior = prior
        self.gamma = gamma
        self.t = 1
        self.output_directory = output_directory or ""
        self.default_q_value = default_q_value
        self.noise_threshold = noise_threshold

        # internal variables
        self.last_action = None
        self.node_history = {}
        self.stop = stop
        self.unique_suffix = get_unique_str()
        self.current_arms = []
        self.final_rules = []
        self.unknown_rules = []
        self.low_q_rules = []
        self.potential_tracking_rules = []
        self.misc_rules = []
        self.round_history = []
        self.chosen_actions = []
        self.action_space = action_space_class(self.output_directory,
                                               self.unique_suffix,
                                               default_q_value=self.default_q_value)

    def __str__(self):
        lr_str = ""
        if self.gamma is None:
            lr_str = "1overN"
        else:
            lr_str = str(self.gamma)
        return f"Q0={self.default_q_value},lr={lr_str},{str(self.policy)},{str(self.bandit)}"

    def reset(self):
        """
        Resets the agent's memory to an initial state.
        """
        self.last_action = None
        self.t = 1
        self.node_history.clear()
        self.unique_suffix = get_unique_str()
        self.action_space.reset()
        self.stop = False
        self.current_arms.clear()
        self.final_rules.clear()
        self.unknown_rules.clear()
        self.low_q_rules.clear()
        self.potential_tracking_rules.clear()
        self.misc_rules.clear()
        self.round_history.clear()
        self.bandit.reset()

    def save(self):

        node_history_file = f"{DH_NODE_HISTORY}_{self.unique_suffix}.json"
        if self.output_directory:
            node_history_file = self.output_directory + os.sep + node_history_file

        # save chosen actions
        self.node_history[CHOSEN_ACTIONS] = self.chosen_actions

        # add extra agent info
        node_history_obj = {}
        if hasattr(self.policy, "confidence_level"):
            node_history_obj["confidence_level"] = str(self.policy.confidence_level)
            node_history_obj["gamma"] = str(self.gamma)
        node_history_obj["w"] = str(round(self.bandit.w_threshold, 2))

        self.node_history[NODE_HISTORY_AGENT_INFO] = node_history_obj

        # add round history (t of when each round started)
        self.node_history[ROUND_HISTORY] = self.round_history

        self.node_history[NODE_HISTORY_AGENT_INFO][NODE_HISTORY_AGENT_INFO__INIT_STATE_INFO] = []

        # keep track of action space explored
        self.node_history[ACTION_SPACE] = dict()
        self.node_history[ACTION_SPACE][ACTION_SPACE_TOTAL_NODES] = self.action_space.get_number_of_nodes()
        self.node_history[ACTION_SPACE][ACTION_SPACE_TOTAL_EDGES] = self.action_space.get_number_of_edges()
        self.node_history[ACTION_SPACE][ACTION_SPACE_EXPLORED_NODES] = self.action_space.get_number_of_explored_nodes()

        # keep track of all the init states
        if self.bandit.init_site_feedback_range:
            for state in self.bandit.init_site_feedback_range.site_feedbacks:
                self.node_history[NODE_HISTORY_AGENT_INFO][NODE_HISTORY_AGENT_INFO__INIT_STATE_INFO].append({
                    AD_COUNTER: state.ad_counter,
                    IMAGE_COUNTER: state.image_counter,
                    TEXTNODE_COUNTER: state.textnode_counter
                })

            # add the min,max,average
            for key, state in [
                (NODE_HISTORY_AGENT_INFO__INIT_STATE_MIN, self.bandit.init_site_feedback_range.get_min()),
                (NODE_HISTORY_AGENT_INFO__INIT_STATE_MAX, self.bandit.init_site_feedback_range.get_max()),
                (NODE_HISTORY_AGENT_INFO__INIT_STATE_AVERAGE, self.bandit.init_site_feedback_range.get_average())]:
                self.node_history[NODE_HISTORY_AGENT_INFO][key] = {
                    AD_COUNTER: state.ad_counter,
                    IMAGE_COUNTER: state.image_counter,
                    TEXTNODE_COUNTER: state.textnode_counter
                }

        # save action space
        self.action_space.save()

        with open(node_history_file, "w") as node_history_f:
            json.dump(self.node_history, node_history_f,
                      default=json_convert_helper)

        self.save_rules()

    def get_filter_rules_file_path(self) -> str:
        """
        Returns the path to the filter list if it exists
        """
        final_rules_file = f"{FINAL_RULES}_{self.unique_suffix}.txt"
        if self.output_directory:
            final_rules_file = self.output_directory + os.sep + final_rules_file
        return final_rules_file

    def get_filter_rules_low_q_file_path(self) -> str:
        low_q_rules_file = f"{LOW_Q_RULES}_{self.unique_suffix}.txt"
        if self.output_directory:
            low_q_rules_file = self.output_directory + os.sep + low_q_rules_file
        return low_q_rules_file

    def save_rules(self):
        final_rules_file = self.get_filter_rules_file_path()
        filter_rule_and_qs = self.get_arms_and_data(self.final_rules)
        output_filter_list_with_value(filter_rule_and_qs, [], file_path=final_rules_file)

        low_q_rules_file = self.get_filter_rules_low_q_file_path()
        low_q_filter_rule_and_qs = self.get_arms_and_data(self.low_q_rules)
        output_filter_list_with_value(low_q_filter_rule_and_qs, [], file_path=low_q_rules_file)

        potential_tracking_rules_files = "potential_tracking_rules_%s.txt" % self.unique_suffix
        if self.output_directory:
            potential_tracking_rules_files = self.output_directory + os.sep + potential_tracking_rules_files

        potential_tracking_rules_and_data = self.get_arms_and_data(self.potential_tracking_rules)
        output_filter_list_with_value(potential_tracking_rules_and_data, [], file_path=potential_tracking_rules_files)

        misc_rules_files = "misc_tracking_rules_%s.txt" % self.unique_suffix
        if self.output_directory:
            misc_rules_files = self.output_directory + os.sep + misc_rules_files

        misc_rules_and_data = self.get_arms_and_data(self.misc_rules)
        output_filter_list_with_value(misc_rules_and_data, [], file_path=misc_rules_files)

        unknown_rules_files = "unknown_rules_%s.txt" % self.unique_suffix
        if self.output_directory:
            unknown_rules_files = self.output_directory + os.sep + unknown_rules_files
        output_filter_list(domains=set(self.unknown_rules), file_path=unknown_rules_files)

    def _get_node_history_average_by_key(self, node: str, key: str) -> float:
        if node in self.node_history and NODE_HISTORY_ACTION_TIMES in self.node_history[node]:
            values = [x[key] for x in self.node_history[node][NODE_HISTORY_ACTION_TIMES] if key in x]
            if len(values) > 0:
                return np.average(values)
        return 0

    def get_arms_and_data(self, arms: list) -> dict:
        """
        Make a dictionary of arms and its values that we care about
        This will most likely used to output a filter list
        """
        arm_and_qs = dict()
        for arm in arms:
            values_dict = dict()
            if self.action_space.contains(arm):
                values_dict[Q_VALUE] = self.action_space.get(arm)[Q_VALUE]
                values_dict[REWARD] = self._get_node_history_average_by_key(arm, REWARD)
                values_dict[AD_COUNTER] = self._get_node_history_average_by_key(arm, AD_COUNTER)
                values_dict[IMAGE_COUNTER] = self._get_node_history_average_by_key(arm, IMAGE_COUNTER)
                values_dict[TEXTNODE_COUNTER] = self._get_node_history_average_by_key(arm, TEXTNODE_COUNTER)
                values_dict[AVG_REWARD] = self._get_node_history_average_by_key(arm, AVG_REWARD)
                values_dict[AD_REMOVED] = self._get_node_history_average_by_key(arm, AD_REMOVED)
                values_dict[IMAGE_MISSING] = self._get_node_history_average_by_key(arm, IMAGE_MISSING)
                values_dict[TEXTNODE_MISSING] = self._get_node_history_average_by_key(arm, TEXTNODE_MISSING)
            arm_and_qs[arm] = values_dict
        return arm_and_qs

    def update_arms_based_on_q_values_new(self, node_type: str = None,
                                          high_q_arms: list = None) -> list:
        """
        Current arms become children of arms that have  -NOISE < Q(a) < NOISE
        """
        low_q_arms = []
        remove_from_arms = []
        for arm in self.current_arms:
            if (-1 * self.noise_threshold) <= self.action_space.get(arm)[Q_VALUE] <= self.noise_threshold:
                low_q_arms.append(arm)
            remove_from_arms.append(arm)

        self.low_q_rules += low_q_arms

        # add successors of bad arms to current arms. Put the rest to sleep
        for arm in low_q_arms:
            self.action_space.get(arm)[SLEEPING_ARM] = True
            # make sure successor is not sleeping or has been considered already
            for succ in self.action_space.get_successors_by_type(arm, node_type):
                if not self.action_space.get(succ)[SLEEPING_ARM] and succ not in self.current_arms:
                    self.current_arms.append(succ)
                logger.info("Adding new successor arm: %s", succ)

        # remove old arms
        for arm in remove_from_arms:
            self.action_space.get(arm)[SLEEPING_ARM] = True
            self.current_arms.remove(arm)

        logger.info("Current arms after update based on q values %d", len(self.current_arms))
        return low_q_arms

    def update_rules_potential_tracking(self, remove_arms: bool = False) -> list:
        """
        Identify arms that may be tracking, where ads_removed = image_missing = textnode_missing = 0
        """
        TRACKING_THRESHOLD = 0.05
        matched_arms = []
        for arm in self.current_arms:
            ad_removed_majority = round(self._get_node_history_majority_by_key(arm, AD_REMOVED), 2)
            textnode_missing_majority = round(self._get_node_history_majority_by_key(arm, TEXTNODE_MISSING), 2)
            image_missing_majority = round(self._get_node_history_majority_by_key(arm, IMAGE_MISSING), 2)

            if ((ad_removed_majority == 0) and
                    (textnode_missing_majority <= TRACKING_THRESHOLD) and
                    (image_missing_majority <= TRACKING_THRESHOLD)):
                matched_arms.append(arm)

        self.potential_tracking_rules += matched_arms

        if remove_arms:
            for arm in matched_arms:
                self.action_space.get(arm)[SLEEPING_ARM] = True
                self.current_arms.remove(arm)

        return matched_arms

    def update_rules_based_on_q_values_new(self) -> list:
        """
        All positive arms become a rule
        All negative arms are put to sleep

        Returns newly found final rules
        """
        remove_from_arms = []
        high_q_arms = []

        for arm in self.current_arms:
            if self.action_space.get(arm)[Q_VALUE] > self.noise_threshold:
                high_q_arms.append(arm)
            elif self.action_space.get(arm)[Q_VALUE] < (-1 * self.noise_threshold):
                remove_from_arms.append(arm)

        self.final_rules += high_q_arms

        for arm in remove_from_arms:
            self.action_space.get(arm)[SLEEPING_ARM] = True
            self.current_arms.remove(arm)

        logger.info("Final rules after update based on q values %d", len(self.final_rules))

        return high_q_arms

    def _get_node_history_majority_by_key(self, node: str, key: str) -> float:
        """
        Returns the majority value, if there are multiple values that have the same max occurrence,
        then return the max value among them
        """
        if node in self.node_history and NODE_HISTORY_ACTION_TIMES in self.node_history[node]:
            values = [x[key] for x in self.node_history[node][NODE_HISTORY_ACTION_TIMES] if key in x]
            if len(values) > 0:
                values, counts = np.unique(values, return_counts=True)
                max_occur = values[counts == counts.max()]
                return max(max_occur)
        return 0

    def init_history_for_all_nodes(self):
        for node in self.action_space.get_nodes():
            self.node_history[node] = dict()
            self.node_history[node][NODE_HISTORY_ACTION_TIMES] = []
            self.node_history[node][NO_MATCH_NODE_HISTORY_ACTION_TIMES] = []
            self.node_history[node][INIT_NODE_HISTORY_ACTION_TIMES] = []
            self.node_history[node][NODE_HISTORY_Q] = []

    def wakeup_arm(self, node: str):
        if self.action_space.get(node)[SLEEPING_ARM]:
            self.action_space.get(node)[SLEEPING_ARM] = False
            #logger.debug("Waking up a sleeping arm: %s", node)

    def wakeup_unknown_arm(self, node: str):
        self.wakeup_arm(node)
        if self.action_space.get(node)[UNKNOWN_ARM]:
            self.action_space.get(node)[UNKNOWN_ARM] = False
            #logger.debug("Setting unknown arm to False: %s", node)

    def initialize_arms(self, url: str, arms: list,
                        increment_time: bool = False):
        """
        Initialize arms with default q value. Does not go to the site.
        """

        logger.info("Before - Initializing arms: %d", len(arms))

        # get arms that have no q value yet from prior
        arms_to_init = []
        for arm in arms:
            if not self.action_space.get(arm)[Q_VALUE_FROM_PRIOR] and not self.action_space.get(arm)[SLEEPING_ARM]:
                arms_to_init.append(arm)

        if len(arms_to_init) > 0:
            self.action_space.set_nodes_as_explored(arms_to_init)
            for arm in arms_to_init:
                block_items_and_match = dict()
                # An arm can be multiple rules
                for x in arm.split(RULES_DELIMITER):
                    rule = create_rule_simple(x)
                    block_items_and_match[rule] = [FilterRuleBlockRecord(rule, arm, "", "")]
                # We assume that the filter rule always hit
                reward_data = RewardTerms(1, 0, 0, self.default_q_value)
                new_site_feedback = SiteFeedback()
                self.force_choose(arm)
                if increment_time:
                    self.observe(reward_data, block_items_and_match, new_site_feedback)
                else:
                    self.observe_init(reward_data, block_items_and_match, new_site_feedback)

    def force_choose(self, action):
        """
        choose the action without policy
        """
        self.last_action = action
        return action

    def choose(self, trial: int):
        """
        use a policy to chose the action
        """
        action = self.policy.choose(self, self.action_space.get_graph(), trial)
        logger.info(f"SELECTED ACTION {str(action)} for trial {trial}")
        self.last_action = action
        self.chosen_actions.append(self.last_action)

        optimal_actions = self.policy.get_optimal_actions(self, self.action_space.get_graph(), trial)
        #logger.debug(f"OPTIMAL ACTION(s) {str(optimal_actions)} for trial {trial}")
        self.bandit.set_optimal_actions(optimal_actions)
        return action

    def _track_last_action(self, reward_terms: RewardTerms, state: SiteFeedback, key_name: str):
        self.node_history[self.last_action][key_name].append(
            {"time": self.t,
             "q": self.action_space.get(self.last_action)[Q_VALUE],
             "q_ucb": self.action_space.get(self.last_action)[QUCB_VALUE],
             REWARD: reward_terms.reward,
             AD_COUNTER: state.ad_counter, IMAGE_COUNTER: state.image_counter,
             TEXTNODE_COUNTER: state.textnode_counter,
             AD_REMOVED: reward_terms.ad_removed, IMAGE_MISSING: reward_terms.image_missing,
             TEXTNODE_MISSING: reward_terms.textnode_missing,
             "arm": self.last_action})

    def track_last_action(self, reward_terms: RewardTerms, state: SiteFeedback):
        self._track_last_action(reward_terms, state, NODE_HISTORY_ACTION_TIMES)

    def track_last_action_with_no_match(self, reward_terms: RewardTerms, state: SiteFeedback):
        self._track_last_action(reward_terms, state, NO_MATCH_NODE_HISTORY_ACTION_TIMES)

    def track_init_action(self, reward_terms: RewardTerms, state: SiteFeedback):
        """
        tracks action during init phase
        """
        self._track_last_action(reward_terms, state, INIT_NODE_HISTORY_ACTION_TIMES)

    def _observe_no_match(self):
        self.action_space.get(self.last_action)[SLEEPING_ARM] = True
        # don't update q value cause there is no match
        self.action_space.get(self.last_action)[UNKNOWN_ARM] = True
        self.unknown_rules.append(self.last_action)
        if self.last_action in self.current_arms:
            self.current_arms.remove(self.last_action)
            logger.info("Remove arm from set of current arms %s", self.last_action)
        #logger.debug("Action %s did not have filter matches, putting arm to sleep", self.last_action)

    def _observe_change_in_q(self, reward: float, prefix_log: str = ""):
        g = self.gamma
        if self.gamma is None:
            #logger.debug(f"Using learning rate 1/n")
            g = 1 / (self.action_space.get(self.last_action)[ACTION_ATTEMPTS] + 1)

        q = self.action_space.get(self.last_action)[Q_VALUE]

        self.action_space.get(self.last_action)[Q_VALUE] = round(q + g * (reward - q), 2)

        logger.info("%s - New reward %f, q value %f, for %s",
                    prefix_log,
                    reward,
                    self.action_space.get(self.last_action)[Q_VALUE],
                    self.last_action)

    def observe_init(self, reward_terms: RewardTerms, block_items_and_match: dict, site_feedback: SiteFeedback):
        """
        Observe action during initiation too. Does not affect attempt times or self.t
        This sets the initial value of Q only
        """
        # if it did not produce any matches, put it to sleep
        domains = self.last_action.split(RULES_DELIMITER)
        has_blocked = False
        for d in domains:
            rule = create_rule_simple(d)
            if rule in block_items_and_match and len(block_items_and_match[rule]) > 0:
                has_blocked = True
                break

        if not has_blocked:
            self._observe_no_match()
            # keep track of no match
            self.track_last_action_with_no_match(reward_terms, site_feedback)
        else:
            self._observe_change_in_q(reward_terms.reward, prefix_log="Init action")
            self.track_init_action(reward_terms, site_feedback)

    def has_blocked(self, block_items_and_match) -> bool:
        # if it did not produce any matches, put it to sleep
        domains = self.last_action.split(RULES_DELIMITER)
        has_blocked = False
        for d in domains:
            rule = create_rule_simple(d)
            if rule in block_items_and_match and len(block_items_and_match[rule]) > 0:
                has_blocked = True
                break

        return has_blocked

    def observe(self,
                reward_terms: RewardTerms,
                block_items_and_match: dict,
                site_feedback: SiteFeedback) -> bool:
        """
        Observe a real action
        Returns whether we associate the reward to the action
        """
        self.action_space.get(self.last_action)[ACTION_ATTEMPTS] += 1

        # if it did not produce any matches, put it to sleep
        has_blocked = self.has_blocked(block_items_and_match)

        if not has_blocked:
            self._observe_no_match()
            # keep track of no match
            self.track_last_action_with_no_match(reward_terms, site_feedback)
            return False
        else:
            self._observe_change_in_q(reward_terms.reward)
            self.track_last_action(reward_terms, site_feedback)
            self.t += 1
            return True
