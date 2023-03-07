import logging

logger = logging.getLogger(__name__)

# 2019 version
DEFAULT_DOCKER_NAME_ADGRAPH_OLD = "flg-ad-highlighter-adgraph"
# 2022 version
DEFAULT_DOCKER_NAME_ADGRAPH_NEW = "flg-ad-highlighter-adgraph-new"
# default
DEFAULT_DOCKER_NAME_ADGRAPH = DEFAULT_DOCKER_NAME_ADGRAPH_OLD

# adgraph version singleton
_adgraph_version = None


class AdGraphVersion:

    def __init__(self, version: str = DEFAULT_DOCKER_NAME_ADGRAPH):
        self.set_adgraph_version(version)

    def __str__(self):
        return self.version

    def set_adgraph_version(self, version: str):
        assert version in [DEFAULT_DOCKER_NAME_ADGRAPH_OLD, DEFAULT_DOCKER_NAME_ADGRAPH_NEW], f"AdGraph version not recognized {version}"
        self.version = version

    def is_new_adgraph(self) -> bool:
        return self.version == DEFAULT_DOCKER_NAME_ADGRAPH_NEW


def get_adgraph_version() -> AdGraphVersion:
    global _adgraph_version
    if _adgraph_version is None:
        _adgraph_version = AdGraphVersion()
    return _adgraph_version


def set_adgraph_version(adgraph_version: str):
    #logger.info(f"setting adgraph version to {adgraph_version}")
    version_obj = get_adgraph_version()
    version_obj.set_adgraph_version(adgraph_version)
