import json
import sys
import logging

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

    strategy_message = '''
        You are a paper expander. Within the given framework, you need to find relevant information from the reference text and summarize and expand it into the provided framework.
        # Input: You will receive a paper outline along with some content.

        # HARDWARE: CPU

        # TASK: You will receive a paper that contains a framework (mainly composed of headings at various levels) along with some content. You must not make any changes to the framework itself; instead, you should follow the optimization requirements and, based on the outline within the framework, extract, summarize, revise, and expand details from the reference text to fill the content under the paper’s outline.
        
        # GOAL:Ensure that the generated text meets the optimization requirements (including word count, fluency, etc.).
        
        # SUCCESS CRITERIA:
        - **word count**: The word count should be adjusted to meet the required length of the article.
        - **Requirement**: You cannot change the basic framework of the paper (composed of headings at various levels); you can only fill in the content under each heading while ensuring smooth sentences.
        - **Language**:The result should be written in Chinese.


        '''

    format_message = '''
        For the paper framework you receive, including the title, subtitles, and various headings, you must not make any changes. However, you may modify the content under each heading based on the reference text.\n
        Please write in Chinese.\n
        When expanding the framework of the paper, you only need to expand the parts for which you can find content in the reference text; if no relevant information is found, you do not need to expand the corresponding section of the framework.\n
        Your output should contain only the optimized paper content; please do not include any additional explanatory text.\n
        '''

    user_message = '''
        I have provided you with the paper to be optimized, the optimization suggestions, and the reference text. Please optimize the paper based on the suggestions, drawing information from the reference text.:\n
        # ''' + evaluate_result["cur_kernel"] + evaluate_result["error_message"]  #evaluate_result["cur_kernel"]即为上一轮的LLM输出结果,evaluate_result["error_message"]为evaluate的建议

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
    

