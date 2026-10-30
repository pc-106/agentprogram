import os

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.config_handler import chroma_conf
from model.factory import chat_model, embedding_model
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.logger_handler import logger
from utils.path_tool import get_abs_path


class VectorStoreService():
    def __init__(self):
        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],
            persist_directory=get_abs_path(chroma_conf["persist_directory"]),
            embedding_function=embedding_model,
        )

        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf['separators'],
            length_function=len,
        )

    def get_retriever(self):
        return self.vector_store.as_retriever(
            search_kwargs={"k": chroma_conf["k"]},
        )

    def load_document(self):
        """
        从数据文件夹内读取数据文件，转为向量存入向量库
        要计算文件的MD5值去重
        :return:
        """

        def check_md5_hex(md5_for_check: str):
            if not os.path.exists(get_abs_path(chroma_conf['md5_hex_store'])):
                with open(get_abs_path(chroma_conf['md5_hex_store']), 'w', encoding='utf-8') as f:
                    pass
                return False  # md5没处理过
            with open(get_abs_path(chroma_conf['md5_hex_store']), 'r', encoding='utf-8') as fr:
                for line in fr.readlines():
                    if md5_for_check == line.strip():
                        return True
                return False

        def save_md5_hex(md5_for_save: str):
            with open(get_abs_path(chroma_conf['md5_hex_store']), 'a', encoding='utf-8') as f:
                f.write(md5_for_save + '\n')

        def get_file_documents(read_path: str) -> list[Document]:
            if read_path.endswith("txt"):
                return txt_loader(read_path)
            elif read_path.endswith("pdf"):
                return pdf_loader(read_path)
            else:
                return []

        allowed_files_path: list[str] = listdir_with_allowed_type(get_abs_path(chroma_conf['data_path']),
                                                                  tuple(chroma_conf['allow_knowledge_file_type'])
                                                                  )

        for path in allowed_files_path:
            md5_hex = get_file_md5_hex(path)
            if check_md5_hex(md5_hex):
                logger.info(f"[加载知识库]文件: {path} 已处理过,已存在在知识库内，跳过")
                continue
            # documents = get_file_documents(path)
            # if documents:
            #     texts = self.spliter.split_documents(documents)
            #     self.vector_store.add_documents(texts)
            #     save_md5_hex(md5_hex)
            try:
                documents: list[Document] = get_file_documents(path)
                if not documents:
                    logger.info(f"[加载知识库] {path} 无有效文本,跳过")
                    continue
                split_documents: list[Document] = self.spliter.split_documents(documents)

                if not split_documents:
                    logger.info(f"[加载知识库]文件: {path} 分片后没有有效内容,跳过")
                    continue
                # 添加向量到向量库
                self.vector_store.add_documents(split_documents)
                # 记录下文件的MD5值，避免重复假造
                save_md5_hex(md5_hex)
                logger.info(f"[加载知识库]文件: {path} 内容加载成功")
            except Exception as e:
                # exc_info=True: 记录详细的报错堆栈，如果为False: 只记录报错信息
                logger.error(f"[加载知识库]文件: {path} 加载失败,{str(e)}", exc_info=True)
                continue


if __name__ == '__main__':
    vector_store = VectorStoreService()
    vector_store.load_document()
    retriever = vector_store.get_retriever()
    res = retriever.invoke("迷路")
    for r in res:
        print(r.page_content)
        print("-" * 20)