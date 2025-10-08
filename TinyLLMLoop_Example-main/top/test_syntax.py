# -*- coding: utf-8 -*-
import asyncio
import json
import pdfplumber
from openai import OpenAI
from function import function_leo #函数声明处
from loop.controller import tinyLLMLoop

async def process_point(section_number, title, point, idx,images_data, name_tag1, name_tag0, progress, total, lock):
    """处理单个写作要点，并更新进度"""
    obj_file = f"syn_obj_{section_number}.json"
    object_dict_ = {"response": "start"}
    with open(obj_file, "w", encoding="utf-8") as f:
        json.dump(object_dict_, f, ensure_ascii=False)

    tag = tinyLLMLoop(
        tag_path=name_tag1,
        _input_filename=obj_file,
        max_loop_times=10,
        section_number=section_number,
        title=title,
        writing_points=point["text"],
        idx=idx,
        async_stamp=f"syn-{idx}",
        verbose=False,
        images_json = images_data,
    )
    result = await tag.run()


    # 打印结果
    print(
        f"[{name_tag0}] [async-{result['async_stamp']}] "
        f"[loop-{result['cur_loop']}] [PASS] ['pass' : {result['pass']}]",
        flush=True,
    )

    # 更新进度
    async with lock:
        progress[0] += 1
        print(f"进度: {progress[0]} / {total}", flush=True)



    return result

async def concurrent_test(concurrence : int = 10, progress_callback=None):
    
    name_tag0 = "TAG_cuda_syntax"
    name_tag1 = "TAG_enlarge"
    # 示例使用
    pdf_path = "/root/PythonProject7_outline/TinyLLMLoop_Example-main/top/paper_test.pdf"
    text = function_leo.extract_text_from_pdf(pdf_path,pages=(0,8))

    md_initial_path = "top/Outline_initial.md"


    with open(md_initial_path, "r", encoding="utf-8") as f:
        response2 = f.read()

    # object_dict_ = {
    #     "response": response2,
    # }

    # obj_file = f"syn_obj_.json"
    # with open(obj_file, "w", encoding="utf-8") as f:
    #     json.dump(object_dict_, f, ensure_ascii=False)

    md_file = "top/Outline_initial.md"
    json_file = "top/outline.json"
    data = function_leo.md_to_json3(md_file, json_file)#md_json转换



    tasks = []
    total = sum(len(sec["writing_points"]) for chap in data for sec in chap["sections"])
    progress = [0]  # 用 list 包一层，可以在闭包里修改
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(concurrence)

    async def sem_task(section_number, title, point, idx,images_data):
        async with sem:
            return await process_point(section_number, title, point, idx,images_data, name_tag1, name_tag0, progress, total, lock)

    for chapter in data:
        for section in chapter["sections"]:
            section_number = section["section_number"]
            title = section["title"]
            for idx, point in enumerate(section["writing_points"]):
                images_data = point["images"]
                tasks.append(asyncio.create_task(sem_task(section_number, title, point, idx,images_data)))


    await asyncio.gather(*tasks, return_exceptions=True)
    # results = await asyncio.gather(*tasks, return_exceptions=True)
    # return results


if __name__ == "__main__":

    res = asyncio.run(concurrent_test())
    print(res)

