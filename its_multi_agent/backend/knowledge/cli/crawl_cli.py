import os
import time
from  services.crawler.client import KnowledgeApiClient
from  services.crawler.parser import HtmlParser
from  utils.text_utils import  TextUtils
from  config.settings import  settings
from  repositories.file_repository import FileRepository


def  main():

    success=0
    fail=0
    for  i in range(1000):
        print(f"[{i+1}/1000] 获取KnowledgeNo:{i+1}")

        knowledge_content=KnowledgeApiClient.fetch_knowledge_content(knowledge_no=str(i+1))

        if knowledge_content and knowledge_content['content']:

            # 1.创建HTML解析器
            parser = HtmlParser()

            # 2.解析HTML为MarkDown
            md_content=parser.parse_html_to_markdown(str(i+1),knowledge_content)

            # 3.生成语义化文件名 {KnowledgeNo}1-{title}.md
            # 3.1 获取文件名
            md_title=knowledge_content.get('title',"无标题")

            # 3.2 清洗文件名（非法字符处理）
            clean_title=TextUtils.clean_filename(md_title.strip())

            # 3.3 限制文件名长度
            if len(clean_title)>50:
                clean_title=clean_title[:50].rstrip("_")

            # 4.构建MarkDown文件名

            file_name=f"{i+1:04d}-{clean_title}.md"

            # 5.构建文件路径
            file_path=os.path.join(settings.CRAWL_OUTPUT_DIR, file_name)

            # 6.保存文件到指定目录
            FileRepository.save_file(md_content,file_path)
            success+=1
            print(f" {i+1}-> 保存成功:{file_name} ")

        else:
            fail+=1
            print(f" {i+1}-> 暂无内容,保存失败")


        time.sleep(0.05)

    print(f"\n爬取完成! 成功: {success}, 失败: {fail}")



if __name__ == '__main__':
    main()


















































