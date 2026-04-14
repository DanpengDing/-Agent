"""
高德地图工具模块

该模块提供高德地图的API调用功能，
用于获取地图上的地点信息、路线规划等

中间件开发（技术路线）
"""
import logging
from http.client import responses
from json import JSONDecodeError
from typing import Dict, Any, Optional, Literal, Union
from dataclasses import dataclass
from urllib3 import Retry
from requests.adapters import HTTPAdapter
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Python对数据处理有两种方式的验证
# 1.静态检查：（程序员以及编译器） 并且不会在运行的时候做约束：类型约束  typing
# 2.动态约束：（在程序运行的时候对数据做校验）运行时产生的：动态约束：pydantic库

PathInputModel = Literal["1", "2", "3"]  # 外部用
PathModel = Literal["walking", "electrobike", "driving"]  # 内部


# 路径模式转换工具
class PathModeConverter:
    """路径模式转换工具类"""

    # 映射关系  外部输入的路径模式 -> 内部使用的路径模式
    MODE_MAPPING = {
        "1": "walking",
        "2": "electrobike",
        "3": "driving",

    }

    @classmethod
    def to_mode(cls, mode_input: Union[PathInputModel]) -> PathModel:
        """将输入的模式转换为内部使用的模式"""

        if mode_input in cls.MODE_MAPPING:
            return cls.MODE_MAPPING[mode_input]
        else:
            raise ValueError(f"不支持的路径模式: {mode_input}，支持的模式: {list(cls.MODE_MAPPING.keys())}")


@dataclass  # 快速的对对象做一些赋值(重复工作少做）
class AmapConfig:
    AMAP_API_KEY: str = os.getenv("AMAP_API_KEY")
    MERCHANT_LONGITUDE: str = os.getenv("MERCHANT_LONGITUDE")
    MERCHANT_LATITUDE: str = os.getenv("MERCHANT_LATITUDE")
    DELIVERY_RADIUS: int = int(os.getenv("DELIVERY_RADIUS"))
    DEFAULT_PATH_MODE = os.getenv("DEFAULT_PATH_MODE")

    def __post_init__(self):
        """自动调用"""
        if self.AMAP_API_KEY is None:
            raise ValueError("AMAP_API_KEY不存在")


# 创建配置实例
config = AmapConfig()


def create_session_with_retries():
    """创建带重试机制的requests会话"""

    # 1.创建session对象
    session = requests.Session()

    # 2.定义重试机制（规则）
    retry_strategy = Retry(
        total=3,  # 总共重试次数（不包括含第一次请求）
        backoff_factor=1,  # 退避因子(backoff_factor)*(2^重试次数-1)   第一次：1s 第二次：2 第三次：4s
        status_forcelist=[429, 500, 502, 503, 504, 505]  # # 429:请求过快  5xx系列的状态码都是服务内部出现各种问题
    )

    # 3.创建HttpAdapter(自定义Http请求的行为)
    adapter = HTTPAdapter(max_retries=retry_strategy)

    # 4.将适配器挂载到session中
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def safe_request(base_url: str, params: dict) -> Optional[Dict]:
    """安全的HTTP请求，处理重试和SSL降级"""
    # HTTPS(加密)协议请求：1.ssl协议过期了或者错误--->降级HTTP协议  2.HTTPS协议的网络连接没建立 建立网络连接超时了 读取超时

    # 1. 获取到带重试机制的session对象
    session = create_session_with_retries()
    try:
        # 2.发送请求
        response = session.get(url=base_url, params=params, timeout=10)

        response.raise_for_status()  # 遇到【400 600) 状态码 都会raise抛出异常

        return response.json()  # 将网络传输的字节反序列化成字典对象。【字节--->对象：方便应用程序处理】反序列化 序列化【对象--->字节（网络传输、IO读写）】
    except requests.exceptions.SSLError as e:
        # 2.发送请求
        try:
            http_request_url = base_url.replace("https://", "http://")
            response = session.get(url=http_request_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"HTTP协议的请求发送失败,原因是{e}")
            raise requests.exceptions.RequestException(f"HTTP协议的请求发送失败,原因:{e}")

    except requests.exceptions.RequestException as e:
        logging.error(f"HTTPS协议的请求发送失败,原因是{e}")
        raise requests.exceptions.RequestException(f"HTTPS协议的请求发送失败,原因:{e}")

    except json.decoder.JSONDecodeError as e:
        logging.error("解析响应结果失败,原因:{e}")
        raise JSONDecodeError(f"反序列化失败，原因{e}")


def geocode_address(address: str) -> Dict[str, Any]:
    """
    地理编码功能 将地址转换为坐标

    Args:
       address: 用户输入要查询的地址
    Returns:
        Dict: 地理编码结果 包含格式化后的地址、经纬度
   """
    try:
        # 1.构建请求URL
        request_url = "https://restapi.amap.com/v3/geocode/geo"

        # 2.构建请求param
        params = {
            "address": address,
            "key": config.AMAP_API_KEY
        }

        # 3.发送请求,得到响应
        response = safe_request(request_url, params)

        # 4.根据响应，解析结果
        # 4.1 失败
        if response['status'] != "1":
            return {
                "success": False,
                "message": response['info']
            }

        # 4.2 成功 # 提取地址编码信息列表
        geocodes = response['geocodes'][0]
        return {
            "formatted_address": geocodes['formatted_address'],
            "location": geocodes['location'],
            "success": True,
        }

    except Exception as e:
        logging.error(f"调用高德地图进行地理位置编码失败,原因:{e}")
        raise e


def calculate_distance(origin_location: str, destination_location: str,
                       path_mode_input: PathInputModel or None) -> Dict[str, Any]:
    """
    不同的路径模式计算两个地点之间的距离和预计时间

    Args:
        origin_location: 起点经纬度
        destination_location:  终点经纬度
        path_mode_input:  路径模式，1:步行，2:骑行，3:驾车

    Returns:
        Dict: 路径结果，包含路径模式、距离、预计时间等

    """
    try:
        # 1.计算高德的API_KEY
        if config.AMAP_API_KEY is None:
            raise ValueError("AMAP_API_KEY 不存在")

        # 2.将外部路径模式转换为内部用的
        inner_model = PathModeConverter.to_mode(path_mode_input)

        # 3.构建请求的URL
        path_endpoint = {
            "walking": "https://restapi.amap.com/v5/direction/walking",
            "electrobike": "https://restapi.amap.com/v5/direction/electrobike",
            "driving": "https://restapi.amap.com/v5/direction/driving"

        }

        # 4.构建param
        params = {
            "key": config.AMAP_API_KEY,
            "origin": origin_location,
            "destination": destination_location
        }
        if inner_model == "driving":
            params["show_fields"] = "cost"

        # 5.发送请求获取响应
        response = safe_request(path_endpoint[inner_model], params)
        # 6.解析响应结果
        # 6.1 失败
        if response['status'] != "1":
            return {
                "success": False,
                "message": response['info']
            }

        # 6.2
        path = response['route']["paths"][0]
        duration = path['duration'] if inner_model == "electrobike" else path['cost']['duration']
        return {
            "distance": int(path["distance"]),  # 两点之间距离
            "duration": duration,  # 两点之间某一种路径规划下的时间
            "success": True  # 状态
        }
    except Exception as e:
        logging.error(f"调用高德地图进行路径规划失败,原因:{e}")
        raise e


def check_delivery_range(address: str, path_mode_input: PathInputModel = None) -> Dict[str, Any]:
    """检查地址是否在配送范围内

    Args:
        address: 用户输入的地址

        path_mode_input: 路径模式，支持 "1"(walking), "2"(electrobike), "3"(driving)。如果为None则使用配置的默认模式

    Returns:
          包含检查结果的 Dict 对象
    """
    try:
        # 1.获取终点的坐标
        geocode_result = geocode_address(address)

        if not geocode_result['success']:
            return {
                "status": "fail",
                "message": geocode_result['message']
            }

        # 2.调用距离函数
        # 2.1 起点坐标（餐厅地址）拼接经纬度
        origin_location = f"{config.MERCHANT_LONGITUDE},{config.MERCHANT_LATITUDE}"
        calculate_distance_result = calculate_distance(origin_location, geocode_result['location'],
                                                       path_mode_input=path_mode_input or config.DEFAULT_PATH_MODE)  # or 运算符的使用 返回第一个真值或者最后一个假值

        if not calculate_distance_result['success']:
            return {
                "status": "fail",
                "message": calculate_distance_result['message']
            }

        # 两点之间的距离 时间 是否在配送范围之类  格式化的地址 message=[当前地址+之间距离+时间+在（不在）范围之内]
        distance =calculate_distance_result['distance']  # 2000
        in_range = distance <= config.DELIVERY_RADIUS
        return {
            "status": "success",
            "in_range": in_range,  # 是否在配送范围之内
            "distance":round(distance/1000,2) ,  # 距离
            "duration": int(calculate_distance_result['duration']),
            "formatted_address": geocode_result['formatted_address'],
            "message": (
                f"配送地址：{geocode_result['formatted_address']}\n"
                f"配送距离：{distance/1000:.2f}公里\n"
                f"配送状态：{'在配送范围内' if in_range else '超出配送范围'}"
            )
        }
    except Exception as  e:
        logging.error(f"配送范围服务查询失败，原因:{e}")
        raise e



if __name__ == '__main__':
    pass

    # print(geocode_address(address="武汉大学"))  # formatted_address:湖北省武汉市武昌区武汉大学 'location': '114.364514,30.536243'
    # print(geocode_address(address="清华大学"))  # formatted_address:北京市海淀区清华大学 'location': '116.326936,40.003213'
    # print(geocode_address(address="宏福科技园"))  # formatted_address:北京市昌平区宏福科技园(郑平路) 'location': '116.365533,40.102488'
    # print(geocode_address(address="北京市昌平区温都水城"))  # formatted_address:北京市北京市昌平区温都水城 'location': '116.376890,40.100204'

    # print(calculate_distance(origin_location="116.365533,40.102488",destination_location="116.376890,40.100204"))
    # print(calculate_distance(origin_location="116.365533,40.102488",destination_location="116.326936,40.003213"))
    # print(calculate_distance(origin_location="116.365533,40.102488",destination_location="114.364514,30.536243",path_mode_input="1"))
    # print(calculate_distance(origin_location="114.397745,30.466352",destination_location="114.364514,30.536243"))

    # 不同模式的使用
    pass
    # test_address = "北京市昌平区温都水城"  # 测试地址
    test_address = "海淀区清华大学"  # 测试地址
    print("\n=== 测试不同路径模式 ===")
    # 测试步行模式 (1)
    print("\n1. 步行模式测试:")
    result1 = check_delivery_range(test_address, "1")
    minutes = result1['duration'] // 60
    seconds = result1['duration'] % 60
    print(f"步行模式距离: {result1['distance']}公里 时间: {result1['duration']}秒 ({minutes}分{round(seconds, 2)}秒)")
    print(f"是否在配送范围内: {result1['message']}")

    # # 测试骑行模式 (2)
    print("\n2. 骑行模式测试:")
    result2 = check_delivery_range(test_address, "2")
    minutes = result1['duration'] // 60
    seconds = result1['duration'] % 60
    print(f"步行模式距离: {result2['distance']}公里 时间: {result2['duration']}秒 ({minutes}分{round(seconds, 2)}秒)")
    print(f"是否在配送范围内: {result2['message']}")
    #
    # # 测试驾车模式 (3)
    print("\n3. 驾车模式测试:")
    result3 = check_delivery_range(test_address, "3")
    minutes = result3['duration'] // 60
    seconds = result3['duration'] % 60
    print(f"步行模式距离: {result3['distance']}公里 时间: {result3['duration']}秒 ({minutes}分{round(seconds, 2)}秒)")
    print(f"是否在配送范围内: {result3['message']}")





