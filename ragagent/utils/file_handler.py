import hashlib

from langchain_core.documents import Document

from utils.logger_handler import logger
import os
from langchain_community.document_loaders import PyPDFLoader, TextLoader


def get_file_md5_hex(filepath: str):
    """
    获取文件的MD5的十六进制字符串
    :return:
    """
    if not os.path.exists(filepath):
        logger.error(f"[md5计算]文件: {filepath} 不存在")
        return

    if not os.path.isfile(filepath):
        logger.error(f"[md5计算]路径: {filepath} 不是文件")
        return

    md5_obj = hashlib.md5()

    chunk_size = 1024
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk)

            """
            chunk=f.read(chunk_size)
            while chunk:
                md5_obj.update(chunk) 
                chunk=f.read(chunk_size)
            """

    except Exception as e:
        logger.error(f"[md5计算]文件: {filepath} 读取失败,{str(e)}")
        return

    return md5_obj.hexdigest()


def listdir_with_allowed_type(path: str, allowed_types: tuple[str]):
    """
    获取指定目录下的指定文件类型的文件列表
    :return:
    """
    files = []
    if not os.path.isdir(path):
        logger.error(f"[listdir_with_allowed_type]路径: {path} 不是文件夹")
        return []

    for f in os.listdir(path):
        if f.endswith(allowed_types):
            files.append(os.path.join(path, f))
    return tuple(files)


def pdf_loader(filepath: str, password=None) -> list[Document]:
    return PyPDFLoader(filepath, password).load()


def txt_loader(filepath: str) -> list[Document]:
    return TextLoader(filepath, encoding="utf-8").load()