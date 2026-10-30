from utils.config_handler import prompts_conf
from utils.logger_handler import logger
from utils.path_tool import get_abs_path


def load_system_prompts():
    """
    加载系统提示语
    :return:
    """
    try:
        system_prompt_path = get_abs_path(prompts_conf["main_prompt_path"])

    except Exception as e:
        logger.error(f"[load_system_prompts]加载系统提示语失败,yaml配置中没有 main_prompt_path 配置项,{str(e)}")
        raise e

    try:
        return open(system_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_system_prompts]加载 [main_prompt] 提示语失败,{str(e)}")
        raise e


def load_rag_prompts():
    """
    加载系统提示语
    :return:
    """
    try:
        rag_prompt_path = get_abs_path(prompts_conf["rag_summarize_prompt_path"])

    except Exception as e:
        logger.error(f"[load_rag_prompts]加载系统提示语失败,yaml配置中没有 rag_summarize_prompt_path 配置项,{str(e)}")
        raise e

    try:
        return open(rag_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_rag_prompts]加载 [rag] 提示语失败,{str(e)}")
        raise e


def load_report_prompts():
    """
    加载系统提示语
    :return:
    """
    try:
        report_prompt_path = get_abs_path(prompts_conf["report_prompt_path"])

    except Exception as e:
        logger.error(f"[load_report_prompts]加载系统提示语失败,yaml配置中没有 report_prompt_path 配置项,{str(e)}")
        raise e

    try:
        return open(report_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_report_prompts]加载 [报告生成] 提示语失败,{str(e)}")
        raise e


if __name__ == '__main__':
    print(load_system_prompts())
    print(load_rag_prompts())
    print(load_report_prompts())