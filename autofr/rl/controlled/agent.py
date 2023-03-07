
import logging
import os

from autofr.common.action_space_utils import TYPE_ESLD, TYPE_FQDN, TYPE_FQDN_PATH
from autofr.common.filter_rules_utils import FilterRule, create_rule_simple_with_subdocumnt, \
    output_filter_list_with_comments
from autofr.common.utils import get_variations_of_domains
from autofr.rl.agent import DomainHierarchyAgent
from autofr.rl.controlled.bandits import AutoFRMultiArmedBanditGetSnapshots

logger = logging.getLogger(__name__)

class DomainHierarchyAgentControlled (DomainHierarchyAgent):

    def get_filter_rules_from_iframe_file_path(self, rule_type: str) -> str:
        file_name = f"iframe_rules_{rule_type}_{self.unique_suffix}.txt"
        file_path = file_name
        if self.output_directory:
            file_path = self.output_directory + os.sep + file_name
        return file_path

    def save_iframe_rules(self):
        assert isinstance(self.bandit, AutoFRMultiArmedBanditGetSnapshots), "Bandit is not of type AutoFRMultiArmedBanditGetSnapshots"

        urls = set()
        for site_snapshot, _ in self.bandit.site_snapshots:
            urls = urls.union(site_snapshot.extract_script_from_annotated_iframes())

        #logger.debug(f"Found {len(urls)} urls from ad iframes in site snapshots")

        esld_rules = set()
        fqdn_rules = set()
        fqdn_and_path_rules = set()

        for url in urls:
            esld, fqdn, fqdn_and_path, _ = get_variations_of_domains(url)
            if esld:
                rule_str = create_rule_simple_with_subdocumnt(esld)
                rule = FilterRule(rule_str, comment="")
                esld_rules.add(rule)
            if fqdn:
                rule_str = create_rule_simple_with_subdocumnt(fqdn)
                rule = FilterRule(rule_str, comment="")
                fqdn_rules.add(rule)
            if fqdn_and_path:
                rule_str = create_rule_simple_with_subdocumnt(fqdn_and_path)
                rule = FilterRule(rule_str, comment="")
                fqdn_and_path_rules.add(rule)

        for rule_type, rules_set in [(TYPE_ESLD, esld_rules), (TYPE_FQDN, fqdn_rules), (TYPE_FQDN_PATH, fqdn_and_path_rules)]:
            if len(rules_set) > 0:
                file_path = self.get_filter_rules_from_iframe_file_path(rule_type)
                output_filter_list_with_comments(list(rules_set), file_path=file_path)
