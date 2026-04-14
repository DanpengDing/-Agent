"""
Pinecone向量数据库工具模块

该模块提供Pinecone向量数据库的连接和操作功能，
用于存储和查询菜品信息的向量化数据，支持语义搜索
"""

import  os
import dashscope
from  dotenv import load_dotenv
from  typing import List,Dict,Any
from pinecone import Pinecone
from pinecone import ServerlessSpec
from http import HTTPStatus

load_dotenv()

import  logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class   PineconeVectorDB:
    """PineCone向量数据库的操作"""

    def  __init__(self):
        self.pinecone_api_key=os.getenv("PINECONE_API_KEY","pcsk_438teh_QavQpvLarFGgtS1E9MPDqEq4dmzkzs8dj7xxU5rVGMkb5gj8v8eWAeZ3fwAzcY5")
        self.dashscope_api_key=os.getenv("DASHSCOPE_API_KEY","sk-26d57c968c364e7bb14f1fc350d4bff0")
        self.pinecone_env=os.getenv("PINECONE_ENV","us-east-1")

        # 配置索引名字、嵌入模型名字、嵌入模型的维度
        self.index_name="menu-item-index"
        self.embedding_model="text-embedding-v4"
        self.dimension=1536

        # 配置pinecone客户端对象以及索引对象
        self.pc=None
        self.index=None


    def  initialize_connection(self)->bool:
        """初始化PineCone向量数据库的客户端对象以及索引对象"""
        try:
            # 1.判断pinecone_api_key
            if  not self.pinecone_api_key:
                logger.error("pinecone api_key  not found!")
                return False

            # 2.初始化客户端对象
            self.pc = Pinecone(api_key=self.pinecone_api_key)

            # 3.初始化索引对象
            if not self.pc.has_index(self.index_name):
                self.pc.create_index(
                    name=self.index_name,
                    vector_type="dense",
                    dimension=self.dimension,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws",
                                        region=self.pinecone_env)
                )

           #  4. 获取并赋值
            self.index=self.pc.Index(self.index_name)
            logger.info("初始化向量数据库PineCone客户端以及索引对象成功")
            return  True
        except Exception as e:
            logger.error(f"初始化向量数据库PineCone客户端以及索引对象失败:{e}")
            return  False



    def  clear_index_vectors(self)->bool:
        """清空指定索引下的向量数据【不是删除索引，索引结构保留，向量数据删除】"""

        try:
            if  not self.index and  not self.initialize_connection():
                logger.error("索引不存在")
                return False

            # 判断索引下是否已经有向量数据。如果有向量数据，直接删除向量数据  如果没有向量数据，不用在删除
            vector_status=self.index.describe_index_stats()
            count=vector_status['total_vector_count']
            if  count==0:
                logger.info("该索引下不存在任何向量数据")
                return  True
            self.index.delete(delete_all=True)

            logger.info("成功删除索引下所有的向量数据")

            return  True
        except Exception as e:
            logger.error(f"删除索引下的向量数据失败:{e}")
            return  False


    def  _embedding_content(self,content:str)->List[float] or None:
        """对文本进行向量化
        args:content:要向量的文本
        :return:文本向量后的结果。[0.1111,0.23,...]
        """
        try:
            # 1.判断dashscope_api_key
            if  not self.dashscope_api_key:
                logger.error("dashscope api_key  not found!")
                return None

            # 2.发送请求
            resp = dashscope.TextEmbedding.call(
                api_key=self.dashscope_api_key,
                model=self.embedding_model,
                input=content,
                dimension=self.dimension,  # 指定向量维度（仅 text-embedding-v3及 text-embedding-v4支持该参数）
            )

            # 3.解析响应结果，提取要的向量列表值
            if resp.status_code == HTTPStatus.OK:
                logger.info(f"文本{content}向量化成功")
                return  resp.get('output').get('embeddings')[0].get('embedding')
            else:
                logger.error("发送文本嵌入模型请求处理失败")
                return None
        except Exception as e:
            logger.error(f"发送文本嵌入模型请求处理失败,原因:{e}")
            return None


    def _validate_datasource(self,validation_content:str)->bool:
        """校验数据源"""

        # 1.校验是否有
        if  not validation_content:
            logger.error("数据源不存在")
            return False

        # 2.校验是否能用
        validate_result_str=("当前无可用的菜品信息","查询菜品信息失败")

        # 3.判断最终结果
        return  not validation_content.startswith(validate_result_str)


    def  _splite_content(self,splite_content:str)->List[str]:
        """切割加载到的菜品信息"""
        try:

            # 1.定义文本切分器（递归的文本切分器）
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            text_spliter=RecursiveCharacterTextSplitter(chunk_size=100,chunk_overlap=0,separators=["\n"],length_function=len)

            # 2.切割
            docs=text_spliter.create_documents([splite_content])

            # 3.处理切后的文档列表
            clearn_docs=[]
            for  doc  in docs:
                # a) 提取的文档对象的内容
                page_content=doc.page_content
                # b) 提取的文档对象的内容做一个小清洗
                clearn_content=page_content.strip()
                clearn_docs.append(clearn_content)
            print(f"菜品信息切割后的块个数：{len(clearn_docs)}")
            return clearn_docs
        except Exception as e:
            logger.error(f"文本切割失败:{e}")
            return []

    def upsert_menu_data(self, menu_data: str = None, batch_size: int = 30, clear_existing: bool = True) -> bool:
        """
        将文本向量存储到PineCone向量数据库
        args1:菜品信息
        args2:批量插入向量数据库中的阈值大小
        args3:是否要清空之前索引下的向量数据。
        """

        try:
           if  not menu_data:
               from smart_diancan.tools.db_tool import get_all_menu_items
               # 0. 清除现有数据
               if clear_existing:
                   self.clear_index_vectors()
               # 1.从数据库查
               menu_item_str=get_all_menu_items()

               # 2.校验数据源
               if  not self._validate_datasource(menu_item_str):
                   logger.error("校验数据源失败,不能进行向量")
                   return False

               # 3.对加载到的数据切分
               embedding_chunks=self._splite_content(menu_item_str)
               if  not  embedding_chunks:
                   logger.error("切片失败，不能进行向量")
                   return  False


               # 4.对切分后的chunk进行向量操作
               batch=[]
               for  line_num,chunk in enumerate(embedding_chunks,1):
                   # a) 对chunk进行向量操作
                   vectors_content=self._embedding_content(chunk)

                   # b) 判断向量结果
                   if not vectors_content or  len(vectors_content)!=self.dimension:
                       logger.error("向量值不存在或者维度不匹配")
                       return False

                   # c) 判断索引对象
                   if not self.index and not self.initialize_connection():
                       logger.error("索引不存在")
                       return False

                   # d) 准备一些元数据
                   menu_medata={
                       "content": chunk,   # 原始文本
                       "line_number": line_num,
                       "dish_id":f"菜品ID:{line_num}", # 真正应该利用正则表达式提取菜品ID
                       "type": "menu_item"
                   }
                   # e) 准备向量数据的唯一标识(假设充当)
                   unique_vector_id=str(line_num)

                   batch.append((unique_vector_id,vectors_content,menu_medata))


                   # f) 将文本向量的结果插入到向量数据库中
                   if len(batch)>=batch_size:
                       # 可以插入
                       self.index.upsert(vectors=batch)
                       batch=[] # 清空

               if batch:
                   self.index.upsert(vectors=batch)
               logger.info("切分之后的文本内容成功存储到向量数据库中...")
               return  True

           else:
               logger.info("处理文本数据")
               logger.info("向量化文本数据")
               logger.info("向量结果存储到向量数据库")
               return   False

        except Exception as e:
            logger.error(f"同步数据到向量数据库失败{e}")
            return  False



    def  search_similar_menu_item(self,query:str,top_k:int=2)->List[Dict[str,Any]]:
        """相似性检索"""

        try:
            # 1.确保索引存在
            if  not self.index and  not self.initialize_connection():
                logger.error("索引不存在")
                return False

            # 2.向量问题
            query_vector=self._embedding_content(query)

            # 3.判断向量是否有效
            if not query_vector or len(query_vector)!=self.dimension:
                logger.error("向量值不存在或者维度不匹配")
                return   False

            # 4.执行语义搜索
            similar_result=self.index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True
            )

            # 5.提取相似文档结果
            matches_result=similar_result['matches']

            if  not  matches_result:
                logger.info("暂无查询到相似性文档")
                return []


            final_matches_result=[]
            for  item  in matches_result:
                match_item = {
                    "id": item['id'],  # 向量数据库生成的
                    "score": item['score'],
                    "content": item['metadata']['content'],  # 原始文本
                    "line_number": item['metadata']['line_number']
                }
                final_matches_result.append(match_item)
            logger.info(f"查询到相似的文档命中个数{len(final_matches_result)}")

            return     final_matches_result

        except  Exception as e:
            logger.error(f"相似性检索失败：{e}")
            return []



# 定义全局实例
pinecone_db=PineconeVectorDB()



# 定义全局同步向量数据库操作方法
def pinecone_input(menu_data: str = None, clear_existing: bool = True) -> bool:
    """
    将菜品数据输入到Pinecone向量数据库

    Args:
        menu_data: 菜品数据字符串，每行一个菜品的完整信息。如果为None，则从数据库获取
        clear_existing: 是否在插入前清除现有数据，默认为True

    Returns:
        bool: 是否输入成功
    """
    return pinecone_db.upsert_menu_data(menu_data, clear_existing=clear_existing)



# 定义全局查询向量数据库操作方法
def search_menu_items(query: str, top_k: int = 2) -> List[str]:
    """
    根据查询搜索相关菜品

    Args:
        query: 查询文本
        top_k: 返回结果数量

    Returns:
        List[str]: 相关菜品信息列表
    """
    match_result=pinecone_db.search_similar_menu_item(query, top_k=top_k)

    if not match_result:
        return []

    return [ item['content'] for item  in match_result]
# 前端展示用
def search_menu_items_with_ids(query: str, top_k: int = 2) -> Dict[str,Any]:
    """
        根据查询文本搜索相似的菜品
       Args:
           query: str: 查询文本
           top_k: int: 返回的结果数量

       Returns:
           Dict[str,Any]:包含菜品内容列表和真实菜品ID列表的字典
           {
               "contents": [菜品内容列表],
               "ids": [真实菜品ID列表],
               "scores": [相似度分数列表]
           }
       """

    match_result=pinecone_db.search_similar_menu_item(query=query, top_k=top_k)

    if not match_result:
        return []

    ids=[]
    for item  in  match_result:
        content=item['content']
        import  re
        # 计算机 \n(换行)  \t（制表符） \b（退格）
        # 正则： \d(处理数字) \s  \b(边界)

        re_match=re.search(r"菜品ID:(\d+)",content)  # "菜品ID:"():捕获组    \d:处理数字(0-9)  + 可以出现一次或者多次连续数字。
        id=re_match.group(1) if re_match else item['id']
        ids.append(id)

    return {
        "contents":[ item['content'] for item  in match_result],
        "ids":ids,
        "scores":[ item['score'] for item  in match_result]
    }





if __name__ == "__main__":

    # print("\n1.测试pinecone客户端和索引的创建")
    # pinecone_db.initialize_connection()

    # print("\n2.上传菜品信息到向量数据库")
    #
    # pinecone_db.upsert_menu_data(menu_data=None,batch_size=10)

    # print("\n3.菜品的相似性检索")
    # match_result=pinecone_db.search_similar_menu_item(query="请给我推荐川菜系列的菜品",top_k=3)  # 本质上利用了嵌入模型能力
    #
    # for  match in match_result:
    #     print(match)

    # print("\n4.菜品的相似性检索,使用全局方法")
    #
    # similar_content=search_menu_items(query="请给我推荐素食系列的菜品",top_k=2)
    #
    # for   item_content in similar_content:
    #     print(item_content)


    print("\n4.菜品的相似性检索,使用全局方法")

    similar_content=search_menu_items_with_ids(query="请给我推荐素食系列的菜品",top_k=2)

    print(similar_content)













































































































