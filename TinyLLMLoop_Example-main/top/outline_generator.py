import asyncio
import json
import os
from loop.config import Config, load_config
from loop.llm.ensemble import LLMEnsemble
from function import function_leo

pdf_path = "./top/paper_test.pdf"

pdf_info_path = "top/pdf_info.json"
with open(pdf_info_path, "r", encoding="utf-8") as f:
    pdf_info_json = json.load(f)

abstract_page_start = pdf_info_json["chapters"][0]["start_page"]
abstract_page_end = pdf_info_json["chapters"][0]["end_page"]
contents_page_start = pdf_info_json["chapters"][1]["start_page"]
contents_page_end = pdf_info_json["chapters"][1]["end_page"]

text_ref_abstract = function_leo.extract_text_from_pdf(pdf_path, pages=(abstract_page_start - 1, abstract_page_end))  # 摘要
text_ref_contents = function_leo.extract_text_from_pdf(pdf_path, pages=(contents_page_start - 1, contents_page_end))  # 目录
text_ref_judgement = function_leo.extract_text_from_pdf(pdf_path, pages=(11, 40))  # 部分内容
name_tag0 = "TAG_cuda_syntax"


class MdGenerator:

    def __init__(self, tag_path: str, mark: str, verbose: bool = False):
        config_file = f"./{tag_path}/config.yaml"
        self.config = load_config(config_file)
        self.llm_ensemble = LLMEnsemble(self.config.llm.models)
        self.verbose = verbose
        self.mark = mark

    async def run(self):
        # === 构造 Prompt ===
        picture_json_file = "top/image_report.json"  # 图片库
        path = "./top"
        filename = f"outline_for_user_change.md"
        full_path = os.path.join(path, filename)
        os.makedirs(path, exist_ok=True)  # 确定生成大纲文件(md格式)的目录

        with open(picture_json_file, "r", encoding="utf-8") as f:
            picture_data = json.load(f)

        with open("./top/Outline_ref.md", "r", encoding="utf-8") as f:
            outline_ref = f.read()

        prompt = f"""
                你是一个论文写作助理。

                任务：根据参考论文概要和章节目录，以及提供的图片库(JSON格式)，生成完整的论文提纲（Markdown 格式），该提纲要足够详细,用于指导另一个大模型完成论文写作。

                要求：
                1. 输出内容为markdown格式。
                2. 提纲精确到段落，每段包含写作要点。
                3. 每段尽量关联图片，从图片库中找到相关联的图片并放置,使用 Markdown 图片语法：
                   ![legend](path)，这里"path" 必须是图片库中的"path"字段（完全相同）
                4. 图片信息来源于我后面给你的图片库(JSON格式)，按与提纲的匹配程度分配。
                5. Markdown 标题层级应与章节目录一致（# 第1章, ## 1.1 小节, ### 1.1.1 段落）。
                6. 仅输出 Markdown 内容，不要解释。
                7. 图片库以JSON格式给出,包含了很多图片,我希望你根据其中的"legend"部分,找到你需要的图片.注意要求3的path要从JSON图片库中对应的"path"提取
                8. 提纲的内容要完整,涵盖"参考论文概要和目录"的全部方面
                9. 从图片库中挑选图片时,请不要从内容不完整的键值对中选
                10. 输出markdown格式时,开头请不要含有"```markdown"
                11. 输出的纲要内容要完整,最后不能遗漏总结与展望
                12. 输出的提纲格式参考下方我给出的"参考提纲",仅参考其格式,内容以"参考论文概要"和"参考论文目录"为主

                参考论文概要:
                {text_ref_abstract}
                参考论文目录:
                {text_ref_contents}
                参考提纲:
                {outline_ref}

                图片库(JSON格式)：
                {picture_data}
                """

        system_message = f""" "role": "system", "content": "你是一个专业的论文写作助理。" """

        response = await asyncio.gather(
            *[
                self.llm_ensemble.generate_with_context(
                    system_message, [{"role": "user", "content": prompt}],
                )
                for _ in range(3)
            ]
        )
        candidates_text = "\n\n".join(
            [f"候选 {i + 1}:\n{resp}" for i, resp in enumerate(response)]
        )
        # 构造评审 prompt
        evaluation_prompt = f"""
        以下是三段候选论文提纲，请你从中选出最优的一个。
        评判标准：
        1. 字数是否足够多
        2. 语句是否通顺
        3. 图片与文章的贴合度是否足够高
        4. 提纲是否详尽
        请你在综合考量后,输出最佳的一段全文,请只输出最佳的一段全文,不要有其他任何说明文字。

        {candidates_text}
        """
        # 调用大模型进行评审
        best_paragraph = await self.llm_ensemble.generate_with_context(
            "你是一个学术文本评审专家。",
            [{"role": "user", "content": evaluation_prompt}],
            temperature=0.0  # 评审任务建议低温度，保证稳定性
        )

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(best_paragraph)


# === 外部调用入口 ===
async def main():
    tag = MdGenerator(tag_path=name_tag0, mark="syn0", verbose=False)
    await tag.run()
    return "Markdown 提纲已生成"


if __name__ == "__main__":
    asyncio.run(main())

# class MdGenerator:
#
#     def __init__(
#             self,
#             tag_path: str,
#             verbose: bool = False,
#     ):
#         config_file = f"./{tag_path}/config.yaml"
#         self.config = load_config(config_file)
#         self.llm_ensemble = LLMEnsemble(self.config.llm.models)
#         self.verbose = verbose
#
#     async def run(self):
#         # === 构造 Prompt ===
#         #picture_json_file = "./outline_output_test/pdf_picture_json_final.json"  # 图片库
#         picture_json_file = "top/image_report.json"  # 图片库
#         path = "./top"
#         filename = f"outline_for_user_change.md"
#         full_path = os.path.join(path, filename)
#         os.makedirs(path, exist_ok=True)  # 确定生成大纲文件(md格式)的目录
#
#         with open(picture_json_file, "r", encoding="utf-8") as f:
#             picture_data = json.load(f)
#
#         with open("./top/Outline_ref.md", "r", encoding="utf-8") as f:
#             outline_ref = f.read()
#
#         prompt = f"""
#                 你是一个论文写作助理。
#
#                 任务：根据参考论文概要和章节目录，以及提供的图片库(JSON格式)，生成完整的论文提纲（Markdown 格式），该提纲要足够详细,用于指导另一个大模型完成论文写作。
#
#                 要求：
#                 1. 输出内容为markdown格式。
#                 2. 提纲精确到段落，每段包含写作要点。
#                 3. 每段尽量关联图片，从图片库中找到相关联的图片并放置,使用 Markdown 图片语法：
#                    ![legend](path),这里"path" 必须是图片库中的"path"字段（完全相同）
#                 4. 图片信息来源于我后面给你的图片库(JSON格式)，按与提纲的匹配程度分配。
#                 5. Markdown 标题层级应与章节目录一致（# 第1章, ## 1.1 小节, ### 1.1.1 段落）。
#                 6. 仅输出 Markdown 内容，不要解释。
#                 7.图片库以JSON格式给出,包含了很多图片,我希望你根据其中的"legend"部分,找到你需要的图片.注意要求3的path要从JSON图片库中对应的"path"提取
#                 8.提纲的内容要完整,涵盖"参考论文概要和目录"的全部方面
#                 9.从图片库中挑选图片时,请不要从内容不完整的键值对中选
#                 10.输出markdown格式时,开头请不要含有"```markdown"
#                 11.输出的纲要内容要完整,最后不能遗漏总结与展望
#                 12.输出的提纲格式参考下方我给出的"参考提纲"
#
#                 参考论文概要:
#                 {text_ref_abstract}
#                 参考论文目录:
#                 {text_ref_contents}
#                 参考提纲:
#                 {outline_ref}
#
#                 图片库(JSON格式)：
#                 {picture_data}
#                 """
#
#         system_message = f""" "role": "system", "content": "你是一个专业的论文写作助理。" """
#
#         response = await asyncio.gather(
#             *[
#                 self.llm_ensemble.generate_with_context(
#                     system_message, [{"role": "user", "content": prompt}],
#                     max_tokens=16000
#                 )
#                 for _ in range(3)
#             ]
#         )
#         candidates_text = "\n\n".join(
#             [f"候选 {i + 1}:\n{resp}" for i, resp in enumerate(response)]
#         )
#         # 构造评审 prompt
#         evaluation_prompt = f"""
#         以下是三段候选论文提纲，请你从中选出最优的一个。
#         评判标准：
#         1. 字数是否足够多
#         2. 语句是否通顺
#         3. 图片与文章的贴合度是否足够高
#         4. 提纲是否详尽
#         请你在综合考量后,输出最佳的一段全文,请只输出最佳的一段全文,不要有其他任何说明文字。
#
#         {candidates_text}
#         """
#         # 调用大模型进行评审
#         best_paragraph = await self.llm_ensemble.generate_with_context(
#             "你是一个学术文本评审专家。",
#             [{"role": "user", "content": evaluation_prompt}],
#             max_tokens=16000,
#             temperature=0.0  # 评审任务建议低温度，保证稳定性
#         )
#
#         with open(full_path, "w", encoding="utf-8") as f:
#             f.write(best_paragraph)
#
#
# async def concurrent_test(concurrence: int = 1):
#     if concurrence == 1:
#         # 直接跑一个任务，避免额外调度开销
#         tag = MdGenerator(
#             tag_path=name_tag0,
#             verbose=False,
#         )
#         await tag.run()
#         #return await tag.run()
#
#     # 多任务时再用 gather
#     tags = [
#         MdGenerator(
#             tag_path=name_tag0,
#             verbose=False,
#         ) for i in range(concurrence)
#     ]
#     tasks = [tag.run() for tag in tags]
#     results = await asyncio.gather(*tasks, return_exceptions=True)
#     return results
#
#
#
# if __name__ == "__main__":
#     # res = asyncio.run(single_test())
#     res = asyncio.run(concurrent_test())
#     print(res)
