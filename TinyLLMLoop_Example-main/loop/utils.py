import logging
import re
import asyncio
from loop.controller import tinyLLMLoop

logger = logging.getLogger(__name__)


def extract_code(
    output_string: str, 
    code_language_type: str,
    ) -> str:
    """
    Extract last code block from model output, specified by code_language_type
    """
    trimmed = output_string.strip()
    code_matches = re.findall(rf"```{code_language_type}(.*?)```", trimmed, re.DOTALL)

    try:
        # Take the last match
        code = code_matches[-1].strip()
        return code
    except IndexError:
        logger.error(f"[Error] Error in finding code in strings !!")
        return " "

def extract_error_lines(log_text):
    error_lines = []
    for line in log_text.split('\n'):
        if 'error' in line.lower():
            error_lines.append(line)
    return '\n'.join(error_lines)

async def concurrent_subtag_first_completed_(
    name_tag: str, 
    _input_filename: str,
    concurrence: int, 
    stamp: str,
    max_loop_times: int,
):

    tags = [
        tinyLLMLoop(
            tag_path = name_tag,
            _input_filename = _input_filename,
            max_loop_times = max_loop_times,
            async_stamp = stamp+str(i),
            verbose = False,
        ) for i in range(concurrence)
    ]
    tasks = [asyncio.create_task(tag.run()) for tag in tags]
    pending = set(tasks)
    
    while pending:
        done, pending = await asyncio.wait(
            pending,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            result = task.result()
            print(f"[{name_tag}] [PASS] [async-{result['async_stamp']}] [loop-{result['cur_loop']}] ['pass' : {result['pass']}]", flush = True)

            if result['pass']:
                for t in pending:
                    t.cancel()
                return result
    return result
    


if __name__ == "__main__":
    strings = "sduaibdaksndkajsnd ```c\n heiheihei ``` sduhdsaijdoisndansdj\n"
    print(extract_code(strings, "cuda"))
