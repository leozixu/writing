#TAG_enlarge的prompt
import json
import sys
import logging
from function import function_leo
logger = logging.getLogger(__name__)



def get_prompt_inputs():
    try:
        dir_name = sys.argv[1]
        cur_loop = sys.argv[2]
        async_stamp = sys.argv[3]
        return dir_name, cur_loop, async_stamp

    except Exception as e:
        logger.error(f"Error in getting prompt inputs: {str(e)}")
        return 0



def prompt_const(
    evaluate_result: dict,
):
    chapter_number = function_leo.extract_number(async_stamp) + 1
    strategy_message = f'''
        你是一个专业的文段优化者.
        '''

    format_message = '''
                你的输出应该是一个完整的段落,保持语句通顺流畅、通俗易懂,保持一定的专业性,但是不要含有大量的公式.
                你的输出应该只包含上述完整的段落,不要有其他任何说明文字.
                如果图片库内包含图片json信息,则输出要关联图片.
                如果用到图片,则文本中使用"如图x-x"字样表示引用,并在文段末尾放置图片,紧贴图片下方要包含上述 "图x-x" 和 图片库内的"legend"内容作为图片标题
                插入图片时,使用markdown语法:![legend](path),其中legend和path分别采用 图片库 内的“legend”和"path"(完全相同)
            '''

    user_message = f"""
                下方我为你提供了待改进的文段,优化建议,相应的参考文本,以及相应的写作要点,和图片库,请基于这几个部分信息进行改进:
                
                ## 待改进的文段
                {evaluate_result["cur_kernel"]}
  
                ## 优化建议
                {evaluate_result["error_message"]}
  
            """

    return {
        "system": strategy_message + format_message,
        "user": user_message,
    }


if __name__ == "__main__":
    dir_name, cur_loop, async_stamp = get_prompt_inputs()
    with open(f"./{dir_name}/results-{async_stamp}/loop-{cur_loop}_evaluate_.json", "r") as f:
        evaluate_result = json.load(f)

    result = prompt_const(evaluate_result)

    with open(f"./{dir_name}/results-{async_stamp}/loop-{cur_loop}_prompt_.json", "w") as f:
        json.dump(result, f)

