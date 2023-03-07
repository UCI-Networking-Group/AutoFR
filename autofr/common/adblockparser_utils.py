import copy
import logging
import typing

from adblockparser import AdblockRules, AdblockRule

logger = logging.getLogger(__name__)

def _domain_variants(domain):
    """
    >>> list(_domain_variants("foo.bar.example.com"))
    ['foo.bar.example.com', 'bar.example.com', 'example.com']
    >>> list(_domain_variants("example.com"))
    ['example.com']
    >>> list(_domain_variants("localhost"))
    ['localhost']
    """
    parts = domain.split('.')
    if len(parts) == 1:
        yield parts[0]
    else:
        for i in range(len(parts), 1, -1):
            yield ".".join(parts[-i:])


class AutoFRAdblockRules (AdblockRules):

    def should_block_2(self, url, options=None) -> typing.Tuple[bool, typing.List[AdblockRule]]:
        """
        Returns whether the url was blocked and the rules that matched.
        If False, then the returned matched rules are whitelisted rules
        If True, then the returned matched rules are blacklisted rules
        """
        options = options or {}
        white_listed, matched_rules = self._is_whitelisted(url, options)
        if white_listed:
            return False, matched_rules

        return self._is_blacklisted(url, options)

    def _is_whitelisted(self, url, options) -> typing.Tuple[bool, typing.List[AdblockRule]]:
        return self._matches(
            url, options,
            self.whitelist_re,
            self.whitelist_require_domain,
            self.whitelist_with_options,
            self.whitelist
        )
    def _is_blacklisted(self, url, options) -> typing.Tuple[bool, typing.List[AdblockRule]]:
        return self._matches(
            url, options,
            self.blacklist_re,
            self.blacklist_require_domain,
            self.blacklist_with_options,
            self.blacklist
        )

    def _matches(self, url, options,
                 general_re,
                 domain_required_rules,
                 rules_with_options,
                 curr_rules) -> typing.Tuple[bool, typing.List[AdblockRule]]:
        """
        Return if ``url``/``options`` are matched by rules defined by
        ``general_re``, ``domain_required_rules`` and ``rules_with_options``.
        ``general_re`` is a compiled regex for rules without options.
        ``domain_required_rules`` is a {domain: [rules_which_require_it]}
        mapping.
         ``rules_with_options`` is a list of AdblockRule instances that
        don't require any domain, but have other options.
        """
        # Note: we cannot rely on general_re because we need to know which rules matched

        #if general_re and general_re.search(url):
        #    return True

        rules = copy.deepcopy(curr_rules)
        if 'domain' in options and domain_required_rules:
            src_domain = options['domain']
            for domain in _domain_variants(src_domain):
                if domain in domain_required_rules:
                    rules.extend(domain_required_rules[domain])

        rules.extend(rules_with_options)

        if self.skip_unsupported_rules:
            rules = [rule for rule in rules if rule.matching_supported(options)]

        matched_rules = []
        for rule in rules:
            if rule.match_url(url, options):
                matched_rules.append(rule)

        return len(matched_rules) > 0, matched_rules

