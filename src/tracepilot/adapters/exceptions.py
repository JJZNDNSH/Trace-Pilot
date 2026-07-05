"""TracePilot adapter 层异常定义。"""


class ScenarioDataError(Exception):
    """场景数据读取基类异常。"""


class ScenarioNotFoundError(ScenarioDataError):
    """场景目录不存在时抛出的异常。"""


class ScenarioFileMissingError(ScenarioDataError):
    """场景文件缺失时抛出的异常。"""
