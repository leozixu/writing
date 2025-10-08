import json
import sys
import logging
import os
import asyncio
import time
from openai import OpenAI
from function import function_leo

import subprocess as sp
#from loop.utils import extract_code, extract_error_lines
import pdb
import re

client = OpenAI(
    api_key="d61217e7-8ff3-4937-83ed-3dd2bebf72ad",
    base_url="https://ark.cn-beijing.volces.com/api/v3"
)



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


    file_path = f"./{dir_name}/results-{async_stamp}/loop-{cur_loop}_begin_.json" 
    with open(file_path, "r", encoding="utf-8") as f:
        object_dict_ = json.load(f)
    response_text = object_dict_["response"]
    word_count = function_leo.count_words(response_text) #用自己定义的函数计算字数


    response = client.chat.completions.create(
        model="deepseek-r1-250528",  # 或者 "deepseek-reasoner"
        messages=[
            {"role": "system", "content": "你是大模型提示词生成者,负责根据收到的文本,生成一整段的英文提示词指导另一个大模型完成此文本的优化任务，你只需要生成提示词即可."
                                          f"文本优化的目标如下,也就是需要生成英文提示词指导另一个大模型完成以下任务:1.文本总中文字数{word_count}需要保持在4500到8000之间,若不满足,则应该作概括或者扩充,但不能违背文章本意;2.需要是中文的文本"
                                          f"你的任务:根据你接收到的文本与文本优化目标的匹配程度打分,满分为100,且只有文本字数{word_count}大于4000并且文本字数{word_count}小于8000时你才能输出大于80的分数,分数越高表示匹配程度越高,你无需输出这个分数,之后,当这个分数大于80时,你就不用输出提示词了,只用输出一个数字1就行了;否则,输出英文提示词指导另一个大模型改进文本,目的是使得分数提高."
                                          f"注意:输入文本的实际字数已由外部统计得出,为 {word_count} 个字。请严格依赖此数值来判断接收到的文本是否满足字数要求,不要自行统计。"
                                          "因为你的输出会直接传给另一个大模型并指导它优化文本,所以要精简,比如,如果满足优化目标了你就仅仅输出一个'1',否则你就仅仅输出一段英文提示词即可"
                                          # "如果要让另一个大模型修改文本字数,那么你要强调是中文的字数(Chinese character),不然另一个大模型可能理解为字符character了" 
             },
            {"role": "user", "content": f"请分析以下文本:\n\n{response_text}"}
            # {"role": "user", "content":"请分析以下文本:\n\n{response_text}"}
        ],
        stream=False  # 是否启用流式响应
    )


    prompt_leo = response.choices[0].message.content
    length = len(prompt_leo)


    prompt_get = re.search(r"\d+", prompt_leo)
    word_count_ds = 1
    if prompt_get:
        word_count_ds = int(prompt_get.group())  # 提取并转成 int




    new_kernel = response_text
    print('The word count is %d in leo and length is %d' % (word_count,length))
    print(prompt_leo)

    file_path = f"./{dir_name}/results-{async_stamp}/loop-{cur_loop}result.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_kernel)


    if length < 5 and 4500 < word_count < 8000:
        return {
            'pass' : True,
            'async_stamp': async_stamp,
            'cur_loop': cur_loop,
            'cur_kernel': new_kernel,
            'error_message' : "",
        }
    elif length < 5 and word_count >= 8000:
        return {
            'pass': False,
            'async_stamp': async_stamp,
            'cur_loop': cur_loop,
            'cur_kernel': new_kernel,
            'error_message': "This text is too long; please help me summarize it to around 6000 Chinese characters, without missing important information."
        }
    elif length < 5 and word_count <= 4500 :
        return {
            'pass': False,
            'async_stamp': async_stamp,
            'cur_loop': cur_loop,
            'cur_kernel': new_kernel,
            'error_message': "This article is a bit short; please help me expand it so that the total word count is around 6000."
        }
    else:
        return {
            'pass': False,
            'async_stamp': async_stamp,
            'cur_loop': cur_loop,
            'cur_kernel': new_kernel,
            'error_message': prompt_leo
        }

if __name__ == "__main__":
    dir_name, cur_loop, async_stamp = get_eva_inputs()
    result = asyncio.run(evaluate(dir_name, cur_loop, async_stamp))
    with open(f"./{dir_name}/results-{async_stamp}/loop-{cur_loop}_evaluate_.json", "w") as f:
        json.dump(result, f) 
    
    






