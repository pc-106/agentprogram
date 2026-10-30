import os
import random
import re

import requests
from langchain_core.tools import tool
from rag.rag_service import RagSummarizeService
from utils.config_handler import agent_conf
from utils.logger_handler import logger
from utils.path_tool import get_abs_path

rag = RagSummarizeService()
user_ids = ['1001', '1002', '1003', '1004', '1005', '1006', '1007', '1008', '1009', '1010']
month_arr = ['2025-01', '2025-02', '2025-03', '2025-04', '2025-05', '2025-06', '2025-07', '2025-08', '2025-09',
             '2025-10',
             '2025-11', '2025-12']
external_data = {}


@tool(description="从向量存储中检索参考资料")
def rag_summarize(query: str) -> str:
    return rag.rag_summarize(query)


AMAP_HOST = "https://restapi.amap.com/v3"

# 高德 IP 定位对 IPv6 经常返回空，源 IP 定位失败时用这些服务取公网 IPv4 再查
PUBLIC_IPV4_URLS = (
    "https://ipv4.icanhazip.com",
    "https://v4.ident.me",
)
IPV4_PATTERN = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


def _amap_get(path: str, params: dict) -> dict:
    """调用高德 Web 服务接口，返回已校验 status 的 JSON 数据。"""
    key = os.environ.get("AMAP_API_KEY", "").strip()
    if not key:
        raise RuntimeError("未配置高德 Key，请在项目根目录 .env 中填写 AMAP_API_KEY")

    resp = requests.get(
        f"{AMAP_HOST}/{path}",
        params={"key": key, **params},
        timeout=8,
    )
    resp.raise_for_status()
    data = resp.json()
    if str(data.get("status")) != "1":
        raise RuntimeError(
            f"高德接口返回错误：{data.get('info')}（infocode={data.get('infocode')}）"
        )
    return data


def _get_public_ipv4() -> str | None:
    """获取当前网络的公网 IPv4 地址，全部失败时返回 None。"""
    for url in PUBLIC_IPV4_URLS:
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            ip = resp.text.strip()
            if IPV4_PATTERN.match(ip):
                return ip
            logger.warning(f"[get_user_location]公网 IP 服务返回非 IPv4 内容:{url} -> {ip[:50]}")
        except Exception as e:
            logger.warning(f"[get_user_location]获取公网 IPv4 失败:{url} -> {e}")
    return None


def _parse_city(data: dict) -> str | None:
    """从高德 IP 定位结果中取出城市名，直辖市取 province。"""
    city = data.get("city")
    province = data.get("province")
    if isinstance(city, str) and city:
        return city
    if isinstance(province, str) and province:
        return province
    return None


@tool(description="获取指定城市的实时天气，以消息字符串形式返回")
def get_weather(city: str) -> str:
    city = (city or "").strip()
    if not city:
        return "天气查询失败：城市不能为空"

    # 高德天气接口的城市参数用「北京」而不是「北京市」
    query_city = city[:-1] if len(city) > 2 and city.endswith("市") else city

    try:
        data = _amap_get("weather/weatherInfo", {"city": query_city, "extensions": "base"})
        lives = data.get("lives") or []
        if not lives:
            return f"天气查询失败：高德未返回「{city}」的天气数据，请确认城市名是否正确（仅支持中国城市）"

        live = lives[0]
        return (
            f"{live.get('province', '')}{live.get('city', '')}实时天气：{live.get('weather', '未知')}，"
            f"气温{live.get('temperature', '未知')}℃，湿度{live.get('humidity', '未知')}%，"
            f"{live.get('winddirection', '')}风{live.get('windpower', '')}级，"
            f"发布时间{live.get('reporttime', '未知')}。"
        )
    except Exception as e:
        logger.error(f"[get_weather]查询「{city}」天气失败：{e}")
        return f"天气查询失败：{e}"


@tool(description="通过高德 IP 定位获取用户所在城市，以纯城市名字符串返回")
def get_user_location() -> str:
    try:
        data = _amap_get("ip", {})
        location = _parse_city(data)
        if location:
            return location

        # 源 IP 可能是 IPv6，高德定位返回空；改用公网 IPv4 再查一次
        ipv4 = _get_public_ipv4()
        if ipv4:
            data = _amap_get("ip", {"ip": ipv4})
            location = _parse_city(data)
            if location:
                logger.info(f"[get_user_location]源 IP 定位失败，改用公网 IPv4:{ipv4} 定位成功:{location}")
                return location
            logger.warning(f"[get_user_location]高德无法定位公网 IPv4:{ipv4}")

        logger.warning("[get_user_location]高德 IP 定位未返回城市信息")
        return "定位失败：高德未能根据当前 IP 识别出城市，请直接询问用户所在城市"
    except Exception as e:
        logger.error(f"[get_user_location]IP 定位失败：{e}")
        return f"定位失败：{e}"


@tool(description="获取用户的ID，以纯字符串形式返回")
def get_user_id() -> str:
    return random.choice(user_ids)


@tool(description="获取当前月份，以纯字符串形式返回")
def get_current_month() -> str:
    return random.choice(month_arr)


def generate_external_data():
    """
    {
        "user_id":{
            "month":{"特征“:xxx,"效率”:xxx,...},
            "month":{"特征“:xxx,"效率”:xxx,...},
            "month":{"特征“:xxx,"效率”:xxx,...},
        },
        "user_id":{
            "month":{"特征“:xxx,"效率”:xxx,...},
            "month":{"特征“:xxx,"效率”:xxx,...},
            "month":{"特征“:xxx,"效率”:xxx,...},
        },
        ...
    }
    :return:
    """
    if not external_data:
        external_data_path = get_abs_path(agent_conf['external_data_path'])

        if not os.path.exists(external_data_path):
            raise FileNotFoundError(f"[generate_external_data]外部数据文件不存在:{external_data_path}")

        with open(external_data_path, 'r', encoding='utf-8') as fr:
            for line in fr.readlines()[1:]:
                arr: list[str] = line.strip().split(',')

                user_id: str = arr[0].replace('"', '')
                feature: str = arr[1].replace('"', '')
                efficiency: str = arr[2].replace('"', '')
                consumables: str = arr[3].replace('"', '')
                comparison: str = arr[4].replace('"', '')
                time: str = arr[5].replace('"', '')

                if user_id not in external_data:
                    external_data[user_id] = {}

                external_data[user_id][time] = {
                    "特征": feature,
                    "效率": efficiency,
                    "耗材": consumables,
                    "对比": comparison,
                }


@tool(description="从外部系统中获取指定用户在指定月份的使用记录，以纯字符串形式返回，如果没有检索到返回空字符串")
def fetch_external_data(user_id: str, month: str) -> str:
    generate_external_data()  # 生成外部数据

    try:
        return external_data[user_id][month]
    except KeyError:
        logger.warning(f"[fetch_external_data]用户:{user_id} 在月份:{month} 没有使用记录")
        return ""


@tool(
    description="无入参，无返回值，调用后触发中间件自动为报告生成的场景动态注入上下文信息，为后续提示词切换提供上下文信息")
def fill_context_for_report():
    return "fill_context_for_report已调用"


if __name__ == '__main__':
    # print(fetch_external_data("1011", "2025-01"))
    pass
