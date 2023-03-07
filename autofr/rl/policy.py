import logging

import networkx as nx
import numpy as np

from autofr.common.exceptions import MissingQValueException
from autofr.rl.action_space import ACTION_ATTEMPTS, Q_VALUE, QUCB_VALUE
from autofr.rl.base import Policy

logger = logging.getLogger(__name__)


class DomainHierarchyUCBPolicy(Policy):

    def __init__(self, confidence_level: float = 1, c: float = 2):
        self.c = c
        self.confidence_level = confidence_level

    def __str__(self):
        return 'UCB(c={})'.format(self.confidence_level)

    def get_optimal_actions(self, agent, dh_graph: nx.DiGraph, trial: int) -> list:
        """
        Get current optimal actions based on Q value
        """

        logger.info("Finding optimal action during time %d, trial %d", agent.t, trial)

        # update the qucb values for all current arms
        q_value_list = []
        for arm in agent.current_arms:
            node_data = dh_graph.nodes.get(arm)
            q_value_list.append(node_data[Q_VALUE])

        if len(agent.current_arms) != len(q_value_list):
            raise MissingQValueException(f"Q value List does not match length of current arms, expected {agent.current_arms}, found {q_value_list}")

        optimal_action_indices = np.flatnonzero(q_value_list == np.max(q_value_list))
        optimal_actions = [agent.current_arms[index] for index in optimal_action_indices]
        return optimal_actions

    def choose(self, agent, dh_graph: nx.DiGraph, trial: int) -> str:
        """
        First update all the qucb values for current arms, then pick the largest qucb arm.
        Current_arms are awake arms
        """

        logger.info("Choosing action during time %d, trial %d", agent.t, trial)
        # sort arms to make things deterministic
        agent.current_arms.sort()

        # update the qucb values for all current arms
        qucb_list = []
        for arm in agent.current_arms:
            node_data = dh_graph.nodes.get(arm)
            try:
                exploration = np.log(trial+1) / (node_data[ACTION_ATTEMPTS] + 1)
                exploration = self.confidence_level * np.power(exploration, 1 / self.c)

                qucb = node_data[Q_VALUE] + exploration
                # logger.debug("nodeId: %s, qucb value: %s", node_id, str(qucb))
                node_data[QUCB_VALUE] = qucb
                qucb_list.append(qucb)

            except (ArithmeticError, TypeError, KeyError) as e:
                logger.warning("Could not update qucb for %s, node_data %s, error: %s", arm, str(node_data), str(e))
                raise e

        if len(agent.current_arms) != len(qucb_list):
            raise MissingQValueException(f"Q UCB List does not match length of current arms, expected {agent.current_arms}, found {qucb_list}")

        return agent.current_arms[np.argmax(qucb_list)]
