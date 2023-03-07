
class AutoFRException(Exception):
    pass


class InvalidSiteFeedbackException(AutoFRException):
    pass


class SiteFeedbackNoAdsException (InvalidSiteFeedbackException):
    pass


class ActionSpaceException(AutoFRException):
    pass


class RootMissingException(ActionSpaceException):
    pass


class MissingActionSpace(ActionSpaceException):
    pass


class BrowserEnvException(AutoFRException):
    pass


class BlockActionMissingException(BrowserEnvException):
    pass


class SiteSnapshotException(AutoFRException):
    pass


class MissingRawAdgraphException(SiteSnapshotException):
    pass


class MissingSnapshotException(SiteSnapshotException):
    pass


class MissingWebRequestFilesException(SiteSnapshotException):
    pass


class BuildingSnapshotException(SiteSnapshotException):
    pass


class PolicyException(AutoFRException):
    pass


class MissingQValueException(PolicyException):
    pass


class DockerException(AutoFRException):
    pass


class SiteNotFoundException(AutoFRException):
    pass


class FilterRulesNotFoundException(AutoFRException):
    pass


class BanditPullTimeout(AutoFRException):
    pass


class BanditPullInvalid(AutoFRException):
    pass


class SiteSnapshotTimeout(SiteSnapshotException):
    pass


class SiteSnapshotInvalid(SiteSnapshotException):
    pass
