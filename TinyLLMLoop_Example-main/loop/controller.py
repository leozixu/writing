import subprocess as sp
from loop.config import Config, load_config
from loop.llm.ensemble import LLMEnsemble

from function import function_leo

import json
import os
import logging
import asyncio
import traceback
import re

import time
import pdfplumber

logger = logging.getLogger(__name__)

class tinyLLMLoop:
    '''
    Base Backbone:
     {LLM} <-- Prompt
         -      ->
          ->   -  
     --> Evaluate -->
    '''

    def __init__(
        self,
        tag_path: str,
        _input_filename: str,
        max_loop_times: int,
        section_number: str,
        title: str,
        writing_points: str,
        idx: int,
        async_stamp: str,
        verbose: bool = False,
        images_json: list = None,
    ):

        # config_file = f"./{tag_path}/config.yaml"
        # prompt_file = f"{tag_path}.prompt"
        # evaluate_file = f"{tag_path}.evaluate"
        config_file = f"TinyLLMLoop_Example-main/{tag_path}/config.yaml"
        prompt_file = f"TinyLLMLoop_Example-main/{tag_path}.prompt"
        evaluate_file = f"TinyLLMLoop_Example-main/{tag_path}.evaluate"
        
        self.tag_path = tag_path
        self.config = load_config(config_file)
        self.llm_ensemble = LLMEnsemble(self.config.llm.models)
        self.prompt_file = prompt_file
        self.evaluate_file = evaluate_file
        self.max_loop_times = max_loop_times
        self.section_number = section_number
        self.title = title
        self._input_filename = _input_filename
        self.writing_points = writing_points
        self.async_stamp = async_stamp
        self.idx = idx
        self.verbose = verbose
        self.images_json = images_json
    
    async def _run_subprocess(self, *args): 
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        async def _stream_output(stream, prefix):
            while True:
                line = await stream.readline()
                if not line:
                    break
                print(f"{prefix}{line.decode().strip()}", flush = True)
        
        stdout_task = asyncio.create_task(_stream_output(process.stdout, ""))
        stderr_task = asyncio.create_task(_stream_output(process.stderr, ""))
        return_code = await process.wait()
        await asyncio.gather(stdout_task, stderr_task)

        process._cmd = args
        return return_code, process



    async def run(self):
        ## initially copy input dict
        cur_loop = 0
        loop_begin_dict = f"TinyLLMLoop_Example-main/{self.tag_path}/results-{self.async_stamp}/loop-{cur_loop}_begin_.json"
        os.makedirs(os.path.dirname(loop_begin_dict), exist_ok = True)
        with open(self._input_filename, "r", encoding="utf-8") as f:
            object_dict_ = json.load(f)#######################
        with open(loop_begin_dict, "w", encoding="utf-8") as f:######################
            json.dump(object_dict_, f,ensure_ascii=False)     #################    



        pdf_info_path = "TinyLLMLoop_Example-main/top/pdf_info.json"
        print("whether to find pdf_info_path......")
        with open(pdf_info_path, "r", encoding="utf-8") as f:
            pdf_info_json = json.load(f)
        print(f"pdf_info : {pdf_info_json}")
        first_number_chapter = int(self.section_number.split(".")[0]) #提取章节数
        pdf_path_ref = "TinyLLMLoop_Example-main/top/paper_test.pdf"
        ref_page_start = pdf_info_json["chapters"][first_number_chapter + 1]["start_page"]
        ref_page_end = pdf_info_json["chapters"][first_number_chapter + 1]["end_page"]
        print(f"ref_page_start : {ref_page_start} , ref_page_end : {ref_page_end}")
        text_ref = function_leo.extract_text_from_pdf(pdf_path_ref, pages=(ref_page_start - 1, ref_page_end))



        writing_guidance = self.writing_points  #提取写作要点
        writing_guidance_length = len(writing_guidance)

        while cur_loop < self.max_loop_times:
            if writing_guidance_length <= 2:
                break
            evaluate_res_dict = f"TinyLLMLoop_Example-main/{self.tag_path}/results-{self.async_stamp}/loop-{cur_loop}_evaluate_.json"
            prompt_res_dict = f"TinyLLMLoop_Example-main/{self.tag_path}/results-{self.async_stamp}/loop-{cur_loop}_prompt_.json"

            ## run evaluate.py
            return_code, process = await self._run_subprocess(
                "python3", "-m", self.evaluate_file,
                self.tag_path, str(cur_loop), self.async_stamp,
            )
            if return_code != 0:
                raise sp.CalledProcessError(return_code, process._cmd)
            
            ## check evaluation result
            with open(evaluate_res_dict, "r") as f:
                evaluate_result = json.load(f)
            json_path = "TinyLLMLoop_Example-main/top/outline.json"
            if evaluate_result["pass"] == True:
                # with open(file_path_final_md, "w", encoding="utf-8") as f:
                #     f.write(evaluate_result["cur_kernel"])\
                function_leo.update_writing_point(json_path,self.section_number,self.idx,evaluate_result["cur_kernel"])
                break

            ## if not pass, prompt the LLM for next loop's evaluation
            return_code, process = await self._run_subprocess(
                "python3", "-m", self.prompt_file,
                self.tag_path, str(cur_loop), self.async_stamp,
            )
            if return_code != 0:
                raise sp.CalledProcessError(return_code, process._cmd)

            ## read prompt result
            with open(prompt_res_dict, "r") as f:
                prompt_result = json.load(f)

            ## query LLM
            print(f"[{self.tag_path}] [async-{self.async_stamp}] [loop-{cur_loop}] [Query] Starting Query LLM at {time.time()}", flush = True)
            # response = await self.llm_ensemble.generate_with_context(
            #     prompt_result["system"], [{"role":"user", "content":f"""{prompt_result["user"]}
            #
            #                                 参考文本:{text_ref}
            #
            #                                 写作要点:{writing_guidance}
            #
            #                                 请严格按照写作要点展开，写成一篇完整的学术风格中文文段，字数不少于4000字。"""}],
            #     max_tokens = 30000
            # )

            response = await asyncio.gather(
                *[
                    self.llm_ensemble.generate_with_context(
                        prompt_result["system"], [{"role":"user", "content":f"""{prompt_result["user"]}
                                            参考文本:{text_ref}
                                            
                                            写作要点:{writing_guidance}
                                            
                                            图片库:{self.images_json}
                                            请严格按照写作要点展开，写成一篇完整的学术风格中文文段，字数不少于4000字。"""}]
                       # max_tokens=16000
                    )
                    for _ in range(3)
                ]
            )

            # 假设 response 是一个 List[str]，里面有 3 段文本
            candidates_text = "\n\n".join(
                [f"候选 {i + 1}:\n{resp}" for i, resp in enumerate(response)]
            )
            # 构造评审 prompt
            evaluation_prompt = f"""
            以下是三段候选学术文段，请你从中选出最优的一段。
            评判标准：
            1. 字数是否足够多
            2. 语句是否通顺
            3. 是否含有错别字
            4. 不要含有太多数学公式或者数学推导
            请你在综合考量后,输出最佳的一段全文,请只输出最佳的一段全文,不要有其他任何说明文字。

            {candidates_text}
            """
            # 调用大模型进行评审
            best_paragraph = await self.llm_ensemble.generate_with_context(
                "你是一个学术文本评审专家。",
                [{"role": "user", "content": evaluation_prompt}],
            #    max_tokens=16000,
                temperature=0.0  # 评审任务建议低温度，保证稳定性
            )

            # evaluate_result["cur_kernel"] = response
            # response = await self.llm_ensemble.generate_with_context(
            #     prompt_result["system"],
            #     [{"role": "user", "content": prompt_result["user"], "Reference text": text_ref2}]
            # )





            print(f"[{self.tag_path}] [async-{self.async_stamp}] [loop-{cur_loop}] [Response] Executing Response at {time.time()}", flush = True)

            ## update object_dict_, evaluate or prompt may change it through fileio
            with open(loop_begin_dict, "r",encoding="utf-8") as f:
                object_dict_ = json.load(f)
            object_dict_["response"] = best_paragraph

            
            cur_loop += 1
            loop_begin_dict = f"TinyLLMLoop_Example-main/{self.tag_path}/results-{self.async_stamp}/loop-{cur_loop}_begin_.json"
            with open(loop_begin_dict, "w", encoding='utf-8') as f:##########################
                json.dump(object_dict_, f,ensure_ascii=False) #####################

            if cur_loop == self.max_loop_times:
                function_leo.update_writing_point(json_path,self.section_number,self.idx,evaluate_result["cur_kernel"])
                break

        return evaluate_result


