# import re
# import os
#
# def load_outline(outline_path):
#     """读取论文提纲，返回每一行作为一个 section"""
#     with open(outline_path, "r", encoding="utf-8") as f:
#         outline = [line.strip() for line in f if line.strip()]
#     return outline
#
# def load_markdown(md_path):
#     """读取 markdown 文件，返回 [(caption, path)]"""
#     figures = []
#     with open(md_path, "r", encoding="utf-8") as f:
#         for line in f:
#             match = re.match(r'!\[(.*?)\]\((.*?)\)', line.strip())
#             if match:
#                 caption, path = match.groups()
#                 figures.append((caption, path))
#     return figures
#
# def match_figures_to_outline(outline, figures):
#     """
#     根据 caption 中的关键词，将图片插入到对应的提纲部分。
#     简单策略：如果 caption 里包含某个提纲的关键词，就绑定过去。
#     """
#     outline_with_figures = []
#
#     for section in outline:
#         matched_figs = []
#         for caption, path in figures:
#             # 如果提纲的小节标题出现在 caption 中，就绑定
#             if any(word in caption for word in section.split()):
#                 matched_figs.append((caption, path))
#
#         outline_with_figures.append((section, matched_figs))
#
#     return outline_with_figures
#
# def save_output(outline_with_figures, output_path):
#     """输出为一个 markdown 文件，带章节和图片"""
#     with open(output_path, "w", encoding="utf-8") as f:
#         for section, figs in outline_with_figures:
#             f.write(f"## {section}\n\n")
#             if figs:
#                 for caption, path in figs:
#                     f.write(f"![{caption}]({path})\n\n")
#
#     print(f"已生成: {output_path}")
#
#
# if __name__ == "__main__":
#     outline_file = "/root/PythonProject6_LLMprompt_done/TinyLLMLoop_Example-main/top/framework.txt"       # 存放论文提纲
#     markdown_file = "/root/PythonProject6_LLMprompt_done/TinyLLMLoop_Example-main/pdf_picture_figures3.md"       # 提取的图片+caption
#     output_file = "/root/PythonProject6_LLMprompt_done/TinyLLMLoop_Example-main/result3_outline_markdown.md"
#
#     outline = load_outline(outline_file)
#     figures = load_markdown(markdown_file)
#     outline_with_figures = match_figures_to_outline(outline, figures)
#
#     save_output(outline_with_figures, output_file)

#改进版本 只取匹配度最高的
import re
import os
from fuzzywuzzy import fuzz

def load_outline(outline_path):
    """读取论文提纲，返回每一行作为一个 section"""
    with open(outline_path, "r", encoding="utf-8") as f:
        outline = [line.strip() for line in f if line.strip()]
    return outline

def load_markdown(md_path):
    """读取 markdown 文件，返回 [(caption, path)]"""
    figures = []
    with open(md_path, "r", encoding="utf-8") as f:
        for line in f:
            match = re.match(r'!\[(.*?)\]\((.*?)\)', line.strip())
            if match:
                caption, path = match.groups()
                figures.append((caption, path))
    return figures

def match_figures_to_outline(outline, figures, threshold=50):
    """
    用模糊匹配（fuzzywuzzy）将 caption 和提纲对应。
    每个小节只保留匹配度最高的一张图。
    """
    outline_with_figures = []

    for section in outline:
        best_match = None
        best_score = 0

        for caption, path in figures:
            score = fuzz.partial_ratio(section, caption)  # 部分匹配得分
            if score > best_score and score >= threshold:
                best_match = (caption, path, score)
                best_score = score

        if best_match:
            outline_with_figures.append((section, [best_match]))
        else:
            outline_with_figures.append((section, []))

    return outline_with_figures

def save_output(outline_with_figures, output_path):
    """输出为一个 markdown 文件，带章节和图片"""
    with open(output_path, "w", encoding="utf-8") as f:
        for section, figs in outline_with_figures:
            f.write(f"## {section}\n\n")
            if figs:
                caption, path, score = figs[0]
                f.write(f"![{caption}]({path})  <!-- 匹配度: {score} -->\n\n")
            else:
                f.write("_无匹配图片_\n\n")
    print(f"已生成: {output_path}")


if __name__ == "__main__":
    outline_file = "/root/PythonProject6_LLMprompt_done/TinyLLMLoop_Example-main/top/framework.txt"       # 存放论文提纲
    markdown_file = "/root/PythonProject6_LLMprompt_done/TinyLLMLoop_Example-main/pdf_picture_figures3.md"       # 提取的图片+caption
    output_file = "/root/PythonProject6_LLMprompt_done/TinyLLMLoop_Example-main/result3_outline_markdown.md"

    outline = load_outline(outline_file)
    figures = load_markdown(markdown_file)
    outline_with_figures = match_figures_to_outline(outline, figures, threshold=60)

    save_output(outline_with_figures, output_file)
