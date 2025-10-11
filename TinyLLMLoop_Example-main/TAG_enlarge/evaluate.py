#TAG_enlarge的evaluate
from loop.config import Config, load_config
from loop.llm.ensemble import LLMEnsemble
import asyncio
import logging
import sys
import json
from function import function_leo


logger = logging.getLogger(__name__)





def get_eva_inputs() -> str:
    dir_name = sys.argv[1]
    cur_loop = sys.argv[2]
    async_stamp = sys.argv[3]
    return dir_name, cur_loop, async_stamp


async def evaluate(
    dir_name: str,
    cur_loop: int,
    async_stamp: str,
) -> dict:

    #config_file = f"./{dir_name}/config.yaml"
    config_file = f"TinyLLMLoop_Example-main/{dir_name}/config.yaml"
    
    config = load_config(config_file)
    llm_ensemble = LLMEnsemble(config.llm.models)

    #file_path = f"./{dir_name}/results-{async_stamp}/loop-{cur_loop}_begin_.json" #要处理的文本路径
    file_path = f"TinyLLMLoop_Example-main/{dir_name}/results-{async_stamp}/loop-{cur_loop}_begin_.json" #要处理的文本路径
    
    with open(file_path, "r", encoding="utf-8") as f:
        object_dict_ = json.load(f)
    response_text = object_dict_["response"]

    word_count = function_leo.count_words(response_text)

    prompt_scoring = f"""
                    ## 角色
                    你是一位专业的文本评估专家，严格遵循指令。
                    
                    ## 任务
                    评估下方“待改进的段落”是否满足特定的“论文要求”。
                    
                    ## 论文要求
                    1. 字数应大于700（当前系统提供的字数为：{word_count}，你无需自行计算）。
                    2. 语句通顺，不能含有错别字。
                    
                    ## 输出要求
                    - **如果满足论文要求**：仅输出一个阿拉伯数字 `1`，不要有任何其他文字、符号或空格。
                    - **如果不满足论文要求**：生成一段非常简短（尽量控制在50字以内）的提示词，指导另一个大模型如何修改文段。例如：“请将字数扩充至4000字以上”或“请精简内容并将字数减少至6000字以内并检查错别字”。输出仅包含提示词，不要有任何其他说明文字。
                    
                    ## 重要注意事项
                    - 判断字数时，**必须**以系统提供的字数 `{word_count}` 为准，无需自行计算。
                    - 请再次确认你的输出：要么是 `1`，要么是一段简短的修改提示词，没有第三种形式。
                    
                    ## 待改进的段落
                    {response_text}
                    """
    system_message_scoring = f""" "role": "system", "content": "你是一个专业的文段评价者。" """

    response_comments = await llm_ensemble.generate_with_context(
        system_message_scoring, [{"role": "user", "content": prompt_scoring}]
    )


    length = len(response_comments)

    print('The word count is %d in leo and length is %d' % (word_count,length))
    print(f"{async_stamp}")
    #print(response_comments)

    new_kernel = response_text
    #file_path = f"./{dir_name}/results-{async_stamp}/loop-{cur_loop}result.md"
    file_path = f"TinyLLMLoop_Example-main/{dir_name}/results-{async_stamp}/loop-{cur_loop}result.md"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_kernel)


    if length <= 3:
        return {
            'pass' : True,
            'async_stamp': async_stamp,
            'cur_loop': cur_loop,
            'cur_kernel': new_kernel,
            'error_message' : "",
        }
    else:
        return {
            'pass': False,
            'async_stamp': async_stamp,
            'cur_loop': cur_loop,
            'cur_kernel': new_kernel,
            'error_message': response_comments
        }











if __name__ == "__main__":
    dir_name, cur_loop, async_stamp = get_eva_inputs()
    result = asyncio.run(evaluate(dir_name, cur_loop, async_stamp))
    with open(f"TinyLLMLoop_Example-main/{dir_name}/results-{async_stamp}/loop-{cur_loop}_evaluate_.json", "w") as f:
        json.dump(result, f)
