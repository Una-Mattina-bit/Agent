import json
import os
from datetime import datetime
from urllib.parse import quote
from urllib.request import urlopen

from langchain_core.tools import tool

from rag.rag_service import RagSummarizeService
from utils.config_handler import agent_conf
from utils.logger_handler import logger
from utils.path_tool import get_abs_path
from utils.user_context import get_current_user_context

rag = RagSummarizeService()

external_data = {}
VALID_TOOL_MODES = {"mock", "real"}


def get_tool_runtime_mode() -> str:
    mode = os.getenv("AGENT_TOOL_MODE", "mock").strip().lower() or "mock"
    if mode not in VALID_TOOL_MODES:
        logger.warning("[tool runtime] AGENT_TOOL_MODE=%s 不受支持，已回退到 mock 模式", mode)
        return "mock"
    return mode


def get_env_or_default(env_name: str, default: str) -> str:
    value = os.getenv(env_name, "").strip()
    return value or default


def get_effective_tool_mode() -> str:
    user_context = get_current_user_context()
    return str(user_context.get("tool_mode") or get_tool_runtime_mode())


def get_runtime_user_id() -> str:
    user_context = get_current_user_context()
    if user_context.get("user_id"):
        return str(user_context["user_id"]).strip()
    if get_effective_tool_mode() == "mock":
        return get_env_or_default("AGENT_MOCK_USER_ID", "1001")
    return ""


def get_runtime_location() -> str:
    user_context = get_current_user_context()
    if user_context.get("city"):
        return str(user_context["city"]).strip()
    if get_effective_tool_mode() == "mock":
        return get_env_or_default("AGENT_MOCK_USER_LOCATION", "北京")
    return ""


def get_runtime_month() -> str:
    configured_month = os.getenv("AGENT_CURRENT_MONTH", "").strip()
    if configured_month:
        return configured_month

    mode = get_effective_tool_mode()
    if mode == "mock":
        return get_env_or_default("AGENT_MOCK_MONTH", "2025-01")
    return datetime.now().strftime("%Y-%m")


def has_report_access() -> bool:
    user_context = get_current_user_context()
    mode = str(user_context.get("tool_mode") or get_tool_runtime_mode())
    if mode == "mock":
        return True
    return bool(user_context.get("authenticated")) and bool(user_context.get("user_id"))


def fetch_real_weather(city: str) -> str:
    query_city = quote(city)
    url = f"https://wttr.in/{query_city}?format=j1"

    try:
        with urlopen(url, timeout=5) as response:
            weather_data = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        logger.warning("[get_weather] 真实天气查询失败 city=%s error=%s", city, error)
        return f"城市{city}天气查询失败，请检查网络连接或切换到 mock 模式。"

    current = weather_data.get("current_condition", [{}])[0]
    weather_desc = current.get("weatherDesc", [{}])[0].get("value", "未知")
    temp_c = current.get("temp_C", "未知")
    feels_like_c = current.get("FeelsLikeC", "未知")
    humidity = current.get("humidity", "未知")

    return (
        f"城市{city}当前天气：{weather_desc}；"
        f"温度{temp_c}°C；体感{feels_like_c}°C；湿度{humidity}%"
    )


@tool(description="从向量存储中检索参考资料")
def rag_summarize(query) -> str:
    return rag.rag_summarize(query)


@tool(description="获取指定城市的天气，以消息字符串的形式返回")
def get_weather(city) -> str:
    mode = get_effective_tool_mode()
    if mode == "mock":
        return f"城市{city}当前天气：晴；温度22°C；湿度45%（mock 数据）"
    return fetch_real_weather(city)


@tool(description="获取用户所在城市的名称，以纯字符串形式返回")
def get_user_location() -> str:
    location = get_runtime_location()
    if location:
        return location
    return "当前会话未解析到真实用户位置，请通过受信请求头、userinfo 接口或 IP 定位补充上下文。"


@tool(description="获取用户的ID，以纯字符串形式返回")
def get_user_id() -> str:
    user_id = get_runtime_user_id()
    if user_id:
        return user_id
    return "当前会话未完成身份校验，无法提供真实用户ID。"


@tool(description="获取当前月份，以纯字符串形式返回")
def get_current_month() -> str:
    return get_runtime_month()


def generate_external_data():
    if external_data:
        return

    external_data_path = get_abs_path(agent_conf["external_data_path"])

    if not os.path.exists(external_data_path):
        logger.error("外部数据文件%s不存在", external_data_path)
        raise FileNotFoundError(f"外部数据文件{external_data_path}不存在")

    with open(external_data_path, "r", encoding="utf-8") as file:
        for line in file.readlines()[1:]:
            arr = line.strip().split(",")

            user_id = arr[0].replace('"', "")
            feature = arr[1].replace('"', "")
            efficiency = arr[2].replace('"', "")
            consumables = arr[3].replace('"', "")
            comparison = arr[4].replace('"', "")
            month = arr[5].replace('"', "")

            if user_id not in external_data:
                external_data[user_id] = {}

            external_data[user_id][month] = {
                "特征": feature,
                "效率": efficiency,
                "耗材": consumables,
                "对比": comparison,
            }


@tool(description="从外部系统中获取指定用户在指定月份的使用记录，以纯字符串形式返回，如果未检索到返回空字符串")
def fetch_external_data(user_id, month) -> str:
    current_user_context = get_current_user_context()
    current_user_id = str(current_user_context.get("user_id", "")).strip()

    if not has_report_access():
        return "当前会话未完成身份校验，无法读取个人报告数据。"

    if current_user_id and current_user_id != str(user_id).strip():
        logger.warning(
            "[fetch_external_data] 当前会话 user_id=%s 尝试读取 user_id=%s 的报告数据",
            current_user_id,
            user_id,
        )
        return "当前会话无权读取其他用户的报告数据。"

    generate_external_data()

    try:
        return external_data[user_id][month]
    except KeyError:
        logger.warning("[fetch_external_data] 未能检索到用户 %s 在 %s 的使用记录", user_id, month)
        return ""


@tool(description="无入参，无返回值，调用后触发中间件自动为报告生成场景动态注入上下文信息，为后续提示词切换提供上下文信息")
def fill_context_for_report():
    if not has_report_access():
        return "fill_context_for_report 已调用，但当前会话未完成身份校验，报告能力会受限。"
    return "fill_context_for_report 已调用"
