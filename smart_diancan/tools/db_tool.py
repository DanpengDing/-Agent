"""
数据库查询工具模块

该模块提供MySQL数据库连接和查询功能，
专门用于查询menu数据库中的menu_items表的全部信息
"""
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import mysql.connector

from dotenv import load_dotenv
from typing import Dict, Any, List

load_dotenv()


class DataBaseConnection:
    """数据库管理相关的操作"""

    def __init__(self):
        """初始化数据库配置信息"""

        # 1.定义了数据库的配置信息
        self.host = os.getenv("MYSQL_HOST", "localhost")
        self.port = os.getenv("MYSQL_PORT", "3306")
        self.user = os.getenv("MYSQL_USER_NAME", "root")
        self.password = os.getenv("MYSQL_USER_PASSWORD", "root")
        self.db_name = os.getenv("MYSQL_DB_NAME", "menu")

        # 2.数据库操作的两个对象
        self.connection = None  # 连接对象
        self.cursor = None  # 真正执行SQL的对象

    def initialize_connection(self) -> bool:
        """初始化数据库连接对象和游标对象"""

        try:
            # 1.初始化连接对象
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.db_name,
                charset="utf8")

            # 2.初始化游标对象
            self.cursor = self.connection.cursor(
                dictionary=True)  # 游标的作用：执行SQL语句 获取SQL语句对应的结果。  select name from temp===(name,"zs")  {"name":"zs"}

            logger.info(f"数据库{self.db_name}连接初始化成功")
            return True

        except mysql.connector.Error as e:
            logger.error(f"数据库{self.db_name}连接初始化失败: {e}")
            return False

    def disconnect_connection(self) -> bool:
        """关闭数据库游标和连接资源"""
        try:
            # 1.关闭游标对象
            if self.cursor:
                self.cursor.close()  # 游标对象关闭
                self.cursor = None  # 内部置空

            # 2.关闭连接
            if self.connection and self.connection.is_connected():
                self.connection.close()  # 断开外部链接
                self.connection = None  # 内部置空
            logger.info("关闭数据库连接成功")
            return True
        except mysql.connector.Error as e:
            logger.error(f"关闭数据库资源失败: {e}")
            return False

    def __enter__(self):
        """
        上下文管理器对象入口
        调用时机：实例化后，在with代码块执行前
        返回值：一定是一个上下文管理器对象（自己：self）
        """

        if self.initialize_connection():
            logger.info("数据库初始化成功")
            return self
        else:
            raise Exception

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        上下文管理器对象出口
        调用时机：在with代码块执行之后
        exc_type：异常类型
        exc_val: 异常类型对应的具体说明
        exc_tb:  记录哪个模块 哪一行代码出现（栈的跟踪）

        """

        self.disconnect_connection()

        if exc_type:
            logger.error(f"执行with代码块期间出现了异常：{exc_val}")

        return False  # 默认返回的是False.  False:我只是告你有异常，我不会处理，会继续向上抛出。 True:不仅会告诉你有异常，而且直接处理了。不会向上抛。


def get_all_menu_items() -> str:
    """
    作用：查询menu_items中所有的菜品信息，并且对每一条菜品信息用\n连接，最终形成一个大字符串（向量化）
    :return:str
    """

    try:
        with DataBaseConnection() as db:
            # 1.定义SQL语句
            query_sql = """
              SELECT 
                    id, dish_name, price, description, category, 
                    spice_level, flavor, main_ingredients, cooking_method, 
                    is_vegetarian, allergens, is_available
                FROM menu_items 
                WHERE is_available = 1
                ORDER BY category, dish_name
            """
            # 2.执行SQL语句
            db.cursor.execute(query_sql)
            menu_items = db.cursor.fetchall()

            # 3.处理结果
            if not menu_items:
                logger.info("当前无可用的菜品信息")
                return "当前无可用的菜品信息"

            menu_items_strings = []
            for item in menu_items:
                # 1.格式化辣度级别
                spice_level_mapping = {0: "不辣", 1: "微辣", 2: "中辣", 3: "重辣"}
                format_spice_level = spice_level_mapping.get(item.get('spice_level'), "暂无辣度级别")
                # 2.格式化是否是素食
                format_is_vegetarian = "是" if item.get('is_vegetarian') else "否"
                # 3.格式化菜品描述
                format_description = item.get('description') if item.get('description', '').strip() else "暂无描述"
                # 4.格式化主要食材
                format_main_ingredients = item.get('main_ingredients') if item.get('main_ingredients',
                                                                                   '').strip() else "暂无主要食材"
                # 5.格式化过敏源
                format_allergens = item.get('allergens') if item.get('allergens', '').strip() else "暂无过敏源"

                # 拼接菜品结构为字符串
                menu_item_string = f"菜品ID:{item['id']}|菜品名称:{item['dish_name']}|价格:¥{item['price']:.2f}|菜品描述:{format_description}|分类:{item['category']}|辣度:{format_spice_level}|口味:{item['flavor']}|主要食材:{format_main_ingredients}|烹饪方法:{item['cooking_method']}|素食:{format_is_vegetarian}|过敏原:{format_allergens}"
                menu_items_strings.append(menu_item_string)

            logger.info(f"查询菜品信息成功，且菜品个数:{len(menu_items_strings)}")

            # 4.返回处理后的结果
            return "\n".join(menu_items_strings)

    except Exception as e:
        logger.error(f"查询所有菜品信息字符串结果失败: {e}")
        return "查询菜品信息失败"



def get_menu_items() -> List[Dict[str, Any]]:
    """
    前端菜品区域展示
    :return: 字典列表（菜品列表）
    """

    try:
        with DataBaseConnection() as db:
            # 1.定义SQL语句
            query_sql = """
                            SELECT 
                            id, dish_name, price, description, category, 
                            spice_level, flavor, main_ingredients, cooking_method, 
                            is_vegetarian, allergens, is_available
                            FROM menu_items 
                            WHERE is_available = 1
                            ORDER BY category, dish_name
                            """

            # 2.执行SQL语句
            db.cursor.execute(query_sql)
            # 3.获取结果
            menu_items = db.cursor.fetchall()

            # 4.处理结果并返回
            if not  menu_items:
                logger.error("暂无可用菜品信息")
                return  []


            menu_items_list=[]

            for  item  in menu_items:
                # 辣度等级转换
                spice_levels = {0: "不辣", 1: "微辣", 2: "中辣", 3: "重辣"}
                spice_text = spice_levels.get(item['spice_level'], "未知")

                # 处理数据
                processed_item = {
                    "id": item['id'],
                    "dish_name": item['dish_name'],
                    "price": float(item['price']),
                    "formatted_price": f"¥{item['price']:.2f}",
                    "description": item['description'] or "暂无描述",
                    "category": item['category'],
                    "spice_level": item['spice_level'],
                    "spice_text": spice_text,
                    "flavor": item['flavor'] or "暂无口味",
                    "main_ingredients": item['main_ingredients'] or "暂无主要食材",
                    "cooking_method": item['cooking_method'] or "暂无烹饪方法",
                    "is_vegetarian": bool(item['is_vegetarian']),
                    "vegetarian_text": "是" if item['is_vegetarian'] else "否",
                    "allergens": item['allergens'] if item['allergens'] and item['allergens'].strip() else "暂无过敏原",
                    "is_available": bool(item['is_available'])
                }
                menu_items_list.append(processed_item)

            logger.info(f"查询菜品结构化列表信息成功，且菜品个数:{len(menu_items_list)}")
            return menu_items_list

    except Exception as e:
        logger.error(f"查询菜品结构化列表信息失败:{e}")
        return []


def test_connection():
    with DataBaseConnection() as db:

        # 业务逻辑（定义SQL 执行SQL）
        db.cursor.execute("select 1")
        test_res = db.cursor.fetchone()  # 获取SQL语句的结果
        if test_res:
            print(f"测试数据库连接成功，且查询结果是:{test_res}")
        else:
            print(f"测试数据库连接失败")


if __name__ == "__main__":
    # print("\n1.测试数据库连接可用性:")
    # test_connection()

    # print("\n2.测试所有菜品信息的字符串:向量化的前置")
    # menu_item_str = get_all_menu_items()
    #
    # print(menu_item_str)

    print("\n3.测试所有菜品信息的列表结构:前端展示")
    menu_item_list=get_menu_items()

    for  index,item in enumerate(menu_item_list,1):
        print(f"当前是第{index}菜品，对应的结构:{item}")






