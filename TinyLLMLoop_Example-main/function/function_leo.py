import pdfplumber
import fitz  # PyMuPDF
import cv2
import numpy as np
import os
import re
import json
from pathlib import Path #用于拼接md文件
from PyPDF2 import PdfReader

def page_ranges_from_list(pages):
    """把页码列表合并成连续区间"""
    if not pages:
        return []
    pages = sorted(set(pages))
    ranges = []
    start = prev = pages[0]
    for p in pages[1:]:
        if p == prev + 1:
            prev = p
        else:
            ranges.append((start, prev))
            start = prev = p
    ranges.append((start, prev))
    return ranges

def is_toc_like(text):
    """判断页面是否像目录页"""
    if not text or not text.strip():
        return False
    if "目录" in text:
        return True
    page_end_re = re.compile(r'(\.{2,}|\s{2,})\d{1,4}\s*$')
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    matches = sum(1 for ln in lines if page_end_re.search(ln))
    return matches >= 2

def chinese_char_ratio(text):
    """计算中文字符比例"""
    if not text:
        return 0.0
    total = len(text)
    chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
    return chinese / total if total > 0 else 0.0

# def extract_pdf_info(pdf_path):
#     doc = fitz.open(pdf_path)
#     page_texts = [doc[p].get_text("text") or "" for p in range(doc.page_count)]
#     total_pages = doc.page_count
#
#     # 提取 PDF 内置 TOC
#     toc = doc.get_toc()
#     level1 = [(title.strip(), int(page)) for lv, title, page in toc if lv == 1]
#     level1.sort(key=lambda x: x[1])
#
#     # 检测摘要页
#     abstract_re = re.compile(r'\babstract\b', re.I)
#     keywords_re = re.compile(r'\bKeywords\b|\b关键词\b', re.I)
#     ch_pages, en_pages = [], []
#     for i, txt in enumerate(page_texts, start=1):
#         if "摘要" in txt and not is_toc_like(txt) and chinese_char_ratio(txt) > 0.02:
#             ch_pages.append(i)
#         if abstract_re.search(txt) and not is_toc_like(txt):
#             en_pages.append(i)
#     ch_ranges = page_ranges_from_list(ch_pages)
#
#     # 英文摘要范围
#     en_range = None
#     if en_pages:
#         start = min(en_pages)
#         end = start
#         for p in range(start, total_pages + 1):
#             txt = page_texts[p - 1]
#             if p != start and (is_toc_like(txt) or keywords_re.search(txt) or re.search(r'第[一二三四五六七八九十0-9]+章', txt)):
#                 end = p - 1
#                 break
#             end = p
#         en_range = (start, end)
#
#     # 找到第一个正式章节起始页
#     main_level1 = [(t, p) for (t, p) in level1 if not re.fullmatch(r'(?i)abstract', t) and '摘要' not in t]
#     first_main_chapter_start = main_level1[0][1] if main_level1 else None
#
#     # 目录页范围 = 摘要结束到第一章之前
#     last_abs_page = 0
#     if ch_ranges:
#         last_abs_page = max(e for (_, e) in ch_ranges)
#     if en_range:
#         last_abs_page = max(last_abs_page, en_range[1])
#     directory = None
#     if last_abs_page and first_main_chapter_start and first_main_chapter_start > last_abs_page + 1:
#         directory = (last_abs_page + 1, first_main_chapter_start - 1)
#
#     # 汇总结果
#     sections = []
#     for s, e in ch_ranges:
#         sections.append({"title": "摘要", "start_page": s, "end_page": e})
#     if en_range:
#         sections.append({"title": "Abstract", "start_page": en_range[0], "end_page": en_range[1]})
#     if directory:
#         sections.append({"title": "目录", "start_page": directory[0], "end_page": directory[1]})
#     for title, page in main_level1:
#         sections.append({"title": title, "start_page": page})
#
#     # 按页码排序
#     sections.sort(key=lambda x: x["start_page"])
#
#     # 填充 end_page
#     for i, sec in enumerate(sections):
#         if "end_page" in sec:
#             continue
#         if i + 1 < len(sections):
#             sec["end_page"] = sections[i + 1]["start_page"] - 1
#         else:
#             sec["end_page"] = total_pages
#         if sec["end_page"] < sec["start_page"]:
#             sec["end_page"] = sec["start_page"]
#
#     # 合并同名条目，修复区间
#     def merge_sections(secs, total):
#         by_title = {}
#         for s in secs:
#             t = s["title"]
#             a, b = int(s["start_page"]), int(s["end_page"])
#             if b < a:
#                 b = a
#             if t in by_title:
#                 by_title[t]["start_page"] = min(by_title[t]["start_page"], a)
#                 by_title[t]["end_page"] = max(by_title[t]["end_page"], b)
#             else:
#                 by_title[t] = {"title": t, "start_page": a, "end_page": b}
#         merged = list(by_title.values())
#         merged.sort(key=lambda x: x["start_page"])
#         skip = {"摘要", "Abstract", "目录"}
#         for i in range(len(merged) - 1):
#             if merged[i]["title"] in skip:
#                 continue
#             if merged[i]["end_page"] >= merged[i + 1]["start_page"]:
#                 merged[i]["end_page"] = merged[i + 1]["start_page"] - 1
#                 if merged[i]["end_page"] < merged[i]["start_page"]:
#                     merged[i]["end_page"] = merged[i]["start_page"]
#         if merged:
#             merged[-1]["end_page"] = min(merged[-1]["end_page"], total)
#         return merged
#
#     return {"chapters": merge_sections(sections, total_pages)}
def extract_pdf_info(pdf_path):
    doc = fitz.open(pdf_path)
    page_texts = [doc[p].get_text("text") or "" for p in range(doc.page_count)]
    total_pages = doc.page_count

    # 提取 PDF 内置 TOC
    toc = doc.get_toc()
    level1 = [(title.strip(), int(page)) for lv, title, page in toc if lv == 1]
    level1.sort(key=lambda x: x[1])

    # 检测摘要页
    abstract_re = re.compile(r'\babstract\b', re.I)
    keywords_re = re.compile(r'\bKeywords\b|\b关键词\b', re.I)
    ch_pages, en_pages = [], []
    for i, txt in enumerate(page_texts, start=1):
        if "摘要" in txt and not is_toc_like(txt) and chinese_char_ratio(txt) > 0.02:
            ch_pages.append(i)
        if abstract_re.search(txt) and not is_toc_like(txt):
            en_pages.append(i)
    ch_ranges = page_ranges_from_list(ch_pages)

    # 英文摘要范围
    en_range = None
    if en_pages:
        start = min(en_pages)
        end = start
        for p in range(start, total_pages + 1):
            txt = page_texts[p - 1]
            if p != start and (is_toc_like(txt) or keywords_re.search(txt) or re.search(r'第[一二三四五六七八九十0-9]+章', txt)):
                end = p - 1
                break
            end = p
        en_range = (start, end)

    # 找到第一个正式章节起始页
    main_level1 = [(t, p) for (t, p) in level1 if not re.fullmatch(r'(?i)abstract', t) and '摘要' not in t]
    first_main_chapter_start = main_level1[0][1] if main_level1 else None

    # 目录页范围 = 摘要结束到第一章之前
    last_abs_page = 0
    if ch_ranges:
        last_abs_page = max(e for (_, e) in ch_ranges)
    if en_range:
        last_abs_page = max(last_abs_page, en_range[1])
    directory = None
    if last_abs_page and first_main_chapter_start and first_main_chapter_start > last_abs_page + 1:
        directory = (last_abs_page + 1, first_main_chapter_start - 1)

    # 汇总结果
    sections = []
    # 👉 整合中英文摘要
    if ch_ranges or en_range:
        s = min([r[0] for r in ch_ranges] + ([en_range[0]] if en_range else []))
        e = max([r[1] for r in ch_ranges] + ([en_range[1]] if en_range else []))
        sections.append({"title": "摘要", "start_page": s, "end_page": e})

    if directory:
        sections.append({"title": "目录", "start_page": directory[0], "end_page": directory[1]})
    for title, page in main_level1:
        sections.append({"title": title, "start_page": page})

    # 按页码排序
    sections.sort(key=lambda x: x["start_page"])

    # 填充 end_page
    for i, sec in enumerate(sections):
        if "end_page" in sec:
            continue
        if i + 1 < len(sections):
            sec["end_page"] = sections[i + 1]["start_page"] - 1
        else:
            sec["end_page"] = total_pages
        if sec["end_page"] < sec["start_page"]:
            sec["end_page"] = sec["start_page"]

    # 合并同名条目，修复区间
    def merge_sections(secs, total):
        by_title = {}
        for s in secs:
            t = s["title"]
            a, b = int(s["start_page"]), int(s["end_page"])
            if b < a:
                b = a
            if t in by_title:
                by_title[t]["start_page"] = min(by_title[t]["start_page"], a)
                by_title[t]["end_page"] = max(by_title[t]["end_page"], b)
            else:
                by_title[t] = {"title": t, "start_page": a, "end_page": b}
        merged = list(by_title.values())
        merged.sort(key=lambda x: x["start_page"])
        skip = {"摘要", "目录"}
        for i in range(len(merged) - 1):
            if merged[i]["title"] in skip:
                continue
            if merged[i]["end_page"] >= merged[i + 1]["start_page"]:
                merged[i]["end_page"] = merged[i + 1]["start_page"] - 1
                if merged[i]["end_page"] < merged[i]["start_page"]:
                    merged[i]["end_page"] = merged[i]["start_page"]
        if merged:
            merged[-1]["end_page"] = min(merged[-1]["end_page"], total)
        return merged

    return {"chapters": merge_sections(sections, total_pages)}





#json转markdown
def json_to_md(json_path, md_path="outline_converted.md"):
    """
    将 JSON 转换回 Markdown 格式
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    lines = []
    for chap in data:
        lines.append(f"# {chap['chapter']}\n")
        for sec in chap["sections"]:
            lines.append(f"## {sec['section_number']} {sec['title']}\n")
            for point in sec["writing_points"]:
                lines.append(f"- \u3000\u3000{point}\n")
            lines.append("\n")

    with open(md_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    return md_path

#更新json文件内容
# def update_writing_point(json_path, section_number, index, new_text):
#     """
#     修改指定 section_number 下某个写作要点
#     :param json_path: JSON 文件路径
#     :param section_number: 章节号 (例如 "1.1")
#     :param index: 写作要点索引 (从 0 开始)
#     :param new_text: 替换后的文本
#     """
#     # 1. 读取 JSON
#     with open(json_path, "r", encoding="utf-8") as f:
#         data = json.load(f)
#
#     # 2. 查找目标 section
#     for chapter in data:
#         for section in chapter["sections"]:
#             if section["section_number"] == section_number:
#                 if 0 <= index < len(section["writing_points"]):
#                     old_text = section["writing_points"][index]
#                     section["writing_points"][index] = new_text
#                     print(f"✅ 已修改: [{section_number}] 第{index}条\n 旧: {old_text}\n 新: {new_text}")
#                 else:
#                     print(f"❌ 索引 {index} 超出范围 (共 {len(section['writing_points'])} 条)")
#
#     # 3. 保存回文件
#     with open(json_path, "w", encoding="utf-8") as f:
#         json.dump(data, f, ensure_ascii=False, indent=4)
#更新json文件内容2
def update_writing_point(json_path, section_number, index, new_text):
    """
    修改指定 section_number 下某个写作要点
    :param json_path: JSON 文件路径
    :param section_number: 章节号 (例如 "1.1")
    :param index: 写作要点索引 (从 0 开始)
    :param new_text: 替换后的文本
    """
    # 1. 读取 JSON
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 2. 查找目标 section
    for chapter in data:
        for section in chapter["sections"]:
            if section["section_number"] == section_number:
                if 0 <= index < len(section["writing_points"]):
                    point = section["writing_points"][index]

                    # 情况 1：原本是字符串
                    if isinstance(point, str):
                        old_text = point
                        section["writing_points"][index] = new_text

                    # 情况 2：是字典，修改其中的 text 字段
                    elif isinstance(point, dict) and "text" in point:
                        old_text = point["text"]
                        section["writing_points"][index]["text"] = new_text

                    else:
                        print(f"⚠️ 第 {index} 条写作要点格式异常: {point}")
                        return

                    print(f"✅ 已修改: [{section_number}] 第{index}条\n 旧: {old_text}\n 新: {new_text}")
                else:
                    print(f"❌ 索引 {index} 超出范围 (共 {len(section['writing_points'])} 条)")

    # 3. 保存回文件
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

#outline.json格式转换,去掉"images"键值对
def convert_outline(in_path, out_path):
    # 读取原始 JSON
    with open(in_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    def simplify_points(points):
        result = []
        for p in points:
            if isinstance(p, dict) and "text" in p:
                result.append(p["text"])
            elif isinstance(p, str):
                result.append(p)
        return result

    # 遍历章节，替换 writing_points
    for chapter in data:
        for section in chapter.get("sections", []):
            section["writing_points"] = simplify_points(section.get("writing_points", []))

    # 保存到新文件
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"✅ 转换完成，结果已保存到 {out_path}")


#markdown转json version1
def md_to_json(md_path, json_path="outline.json"):
    """
    将 Markdown 提纲转成 JSON 格式
    """
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    data = []
    current_chapter = None
    current_section = None

    for line in lines:
        line = line.strip()

        # 匹配章节和小节
        chapter_match = re.match(r"^#\s*(.+)", line)
        section_match = re.match(r"^##+\s+(\d+(\.\d+)+)\s+(.+)", line)

        if chapter_match and not line.startswith("##"):
            current_chapter = chapter_match.group(1)
            data.append({
                "chapter": current_chapter,
                "sections": []
            })

        elif section_match:
            current_section = {
                "section_number": section_match.group(1),
                "title": section_match.group(3),
                "writing_points": []
            }
            data[-1]["sections"].append(current_section)

        # 匹配写作要点
        elif line.startswith("- 写作要点"):
            point = line.replace("- 写作要点：", "").strip()
            if current_section:
                current_section["writing_points"].append(point)

    # 保存为 JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    return data

#markdown转json version2
def md_to_json2(md_path, json_path="outline.json"):
    """
    将 Markdown 提纲转成 JSON 格式
    - 写作要点存入 "writing_points"
    - 图片存入 "images"
    """
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    data = []
    current_chapter = None
    current_section = None

    for line in lines:
        line = line.strip()

        # 匹配章节
        chapter_match = re.match(r"^#\s*(.+)", line)
        section_match = re.match(r"^##+\s+(\d+(\.\d+)+)\s+(.+)", line)

        if chapter_match and not line.startswith("##"):
            current_chapter = chapter_match.group(1)
            data.append({
                "chapter": current_chapter,
                "sections": []
            })

        elif section_match:
            current_section = {
                "section_number": section_match.group(1),
                "title": section_match.group(3),
                "writing_points": [],
                "images": []
            }
            data[-1]["sections"].append(current_section)

        # 匹配写作要点
        elif line.startswith("- 写作要点"):
            point = line.replace("- 写作要点：", "").strip()
            if current_section:
                current_section["writing_points"].append(point)

        # 匹配 Markdown 图片
        elif line.startswith("![]") or line.startswith("!["):
            img_match = re.match(r"!\[(.*?)\]\((.*?)\)", line)
            if img_match and current_section:
                current_section["images"].append({
                    "legend": img_match.group(1),
                    "path": img_match.group(2)
                })

    # 保存为 JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    return data

def md_to_json3(md_path, json_path="outline.json"):
    """
    将 Markdown 提纲转成 JSON 格式
    - 每个写作要点绑定图片
    """
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    data = []
    current_chapter = None
    current_section = None
    current_point = None  # 用来存储正在处理的写作要点

    for line in lines:
        line = line.strip()

        # 匹配章节
        chapter_match = re.match(r"^#\s*(.+)", line)
        section_match = re.match(r"^##+\s+(\d+(\.\d+)+)\s+(.+)", line)

        if chapter_match and not line.startswith("##"):
            current_chapter = chapter_match.group(1)
            data.append({"chapter": current_chapter, "sections": []})

        elif section_match:
            current_section = {
                "section_number": section_match.group(1),
                "title": section_match.group(3),
                "writing_points": []
            }
            data[-1]["sections"].append(current_section)

        # 匹配写作要点
        elif line.startswith("- 写作要点"):
            point_text = line.replace("- 写作要点：", "").replace("- 写作要点:", "").strip()
            current_point = {"text": point_text, "images": []}
            if current_section:
                current_section["writing_points"].append(current_point)

        # 匹配图片（如果在写作要点之后，就绑到该写作要点）
        elif line.startswith("![]") or line.startswith("!["):
            img_match = re.match(r"!\[(.*?)\]\((.*?)\)", line)
            if img_match:
                img_obj = {"legend": img_match.group(1), "path": img_match.group(2)}
                if current_point:  # 绑定到最近的写作要点
                    current_point["images"].append(img_obj)
                elif current_section:  # 如果没有写作要点，就放到 section 里
                    current_section.setdefault("images", []).append(img_obj)

    # 保存为 JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    return data
# #提取pdf内摘要、目录的页码以及pdf总字数,返回json文件
# def extract_pdf_info(pdf_path, output_json="pdf_info.json"):
#     result = {
#         "abstract_page": None,
#         "toc_page": None,
#         "total_pages": 0
#     }
#
#     # 获取总页数
#     reader = PdfReader(pdf_path)
#     result["total_pages"] = len(reader.pages)
#
#     # 遍历 PDF 每一页
#     with pdfplumber.open(pdf_path) as pdf:
#         for i, page in enumerate(pdf.pages):
#             text = page.extract_text()
#             if not text:
#                 continue
#
#             # 检测摘要
#             if result["abstract_page"] is None and re.search(r"(摘要|Abstract)", text, re.IGNORECASE):
#                 result["abstract_page"] = i + 1  # 页码从1开始
#
#             # 检测目录
#             if result["toc_page"] is None and re.search(r"(目录|Contents)", text, re.IGNORECASE):
#                 result["toc_page"] = i + 1
#
#             # 如果都找到了就可以提前结束
#             if result["abstract_page"] and result["toc_page"]:
#                 break
#     # 保存到 JSON 文件
#     with open(output_json, "w", encoding="utf-8") as f:
#         json.dump(result, f, ensure_ascii=False, indent=4)
#     return result

def extract_text_from_pdf(pdf_path, pages=None):
    """
    从 PDF 提取文本，可以指定页码
    :param pdf_path: PDF 文件路径
    :param pages: None 表示全部页；可以是 [0,2,4] 这样的页码列表；也可以是 (start, end) 的范围（包含 start，不包含 end）
    :return: 提取到的文本字符串
    """
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        if pages is None:
            # 提取所有页
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        elif isinstance(pages, (list, tuple)):
            if all(isinstance(p, int) for p in pages):
                # 页码列表
                for p in pages:
                    if 0 <= p < len(pdf.pages):
                        page_text = pdf.pages[p].extract_text()
                        if page_text:
                            text += page_text + "\n"
            elif len(pages) == 2 and all(isinstance(p, int) for p in pages):
                # 页码范围 (start, end)
                for p in range(pages[0], pages[1]):
                    if 0 <= p < len(pdf.pages):
                        page_text = pdf.pages[p].extract_text()
                        if page_text:
                            text += page_text + "\n"
        else:
            raise ValueError("pages 参数必须是 None、页码列表 [0,2,3] 或页码范围 (start, end)")

    return text.strip()

#提取图片         提取图片             提取图片                     提取图片
def merge_boxes_with_distance(boxes, iou_threshold=0.2, distance_threshold=15):
    merged = []
    used = [False] * len(boxes)
    for i in range(len(boxes)):
        if used[i]:
            continue
        x1, y1, w1, h1 = boxes[i]
        bx1, by1, bx2, by2 = x1, y1, x1 + w1, y1 + h1
        for j in range(i + 1, len(boxes)):
            if used[j]:
                continue
            x2, y2, w2, h2 = boxes[j]
            cx1, cy1, cx2, cy2 = x2, y2, x2 + w2, y2 + h2
            inter_x1, inter_y1 = max(bx1, cx1), max(by1, cy1)
            inter_x2, inter_y2 = min(bx2, cx2), min(by2, cy2)
            inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
            area1 = w1 * h1
            area2 = w2 * h2
            iou = inter_area / float(area1 + area2 - inter_area + 1e-6)
            horizontal_gap = max(0, max(bx1, cx1) - min(bx2, cx2))
            vertical_gap = max(0, max(by1, cy1) - min(by2, cy2))
            if iou > iou_threshold or (horizontal_gap <= distance_threshold and vertical_gap <= distance_threshold):
                bx1, by1 = min(bx1, cx1), min(by1, cy1)
                bx2, by2 = max(bx2, cx2), max(by2, cy2)
                used[j] = True
        merged.append((bx1, by1, bx2 - bx1, by2 - by1))
        used[i] = True
    return merged

def merge_text_blocks(text_blocks, scale=1.0):
    text_blocks_scaled = [
        (int(b[0]*scale), int(b[1]*scale), int(b[2]*scale), int(b[3]*scale), b[4].strip())
        for b in text_blocks if b[4].strip()
    ]
    text_blocks_scaled.sort(key=lambda b: b[1])
    merged = []
    for block in text_blocks_scaled:
        if not merged:
            merged.append(block)
        else:
            last = merged[-1]
            if block[1] <= last[3] + 5:
                mx0 = min(last[0], block[0])
                my0 = min(last[1], block[1])
                mx1 = max(last[2], block[2])
                my1 = max(last[3], block[3])
                mtext = last[4] + " " + block[4]
                merged[-1] = (mx0, my0, mx1, my1, mtext)
            else:
                merged.append(block)
    return merged

def find_caption_for_box_recursive(bbox, caption_boxes, initial_gap_factor=1.5, max_gap_factor=5.0, step=1.5):
    x1, y1, w, h = bbox
    bx1, by1, bx2, by2 = x1, y1, x1 + w, y1 + h
    caption_pattern = re.compile(r'^(图|表)\s*\d+[-\d]*.*', re.IGNORECASE)
    gap_factor = initial_gap_factor
    matched = []
    while gap_factor <= max_gap_factor:
        max_gap = int(gap_factor * h)
        candidates = []
        for (tx0, ty0, tx1, ty1, text) in caption_boxes:
            if tx1 < bx1 or tx0 > bx2:
                continue
            if 0 < ty0 - by2 <= max_gap and caption_pattern.match(text):
                candidates.append((ty0 - by2, (tx0, ty0, tx1, ty1, text)))
            elif 0 < by1 - ty1 <= max_gap and caption_pattern.match(text):
                candidates.append((by1 - ty1, (tx0, ty0, tx1, ty1, text)))
        if candidates:
            candidates.sort(key=lambda x: x[0])
            min_gap = candidates[0][0]
            matched = [c[1] for c in candidates if c[0] <= min_gap + 5]
            break
        else:
            gap_factor += step
    return matched

def extract_figures_with_titles(pdf_path, output_folder, json_output,
                                dpi=200, min_area=5000, max_area_ratio=0.4, max_gap_factor=1.5):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    pdf_doc = fitz.open(pdf_path)
    results = []
    prev_page_bottom_captions = []

    for page_index in range(len(pdf_doc)):
        page = pdf_doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = [cv2.boundingRect(cnt) for cnt in contours if cv2.contourArea(cnt) > min_area]
        merged_boxes = merge_boxes_with_distance(boxes, iou_threshold=0.2, distance_threshold=15)
        page_area = img.shape[0] * img.shape[1]
        filtered_boxes = [(x, y, w, h) for (x, y, w, h) in merged_boxes if w * h < max_area_ratio * page_area]

        scale = dpi / 72.0
        text_blocks = page.get_text("blocks")
        caption_boxes = merge_text_blocks(text_blocks, scale)
        caption_boxes_extended = prev_page_bottom_captions + caption_boxes

        final_boxes = []
        for (x, y, w, h) in filtered_boxes:
            bx1, bx2 = 0, img.shape[1]
            by1, by2 = y, y + h
            matched_caption = find_caption_for_box_recursive((bx1, by1, bx2 - bx1, by2 - by1),
                                                             caption_boxes_extended,
                                                             initial_gap_factor=max_gap_factor)
            caption_texts = []
            if matched_caption:
                ty0 = min(c[1] for c in matched_caption)
                ty1 = max(c[3] for c in matched_caption)
                caption_texts = [c[4] for c in matched_caption]
                by1 = min(by1, ty0)
                by2 = max(by2, ty1)
            final_boxes.append((bx1, by1, bx2 - bx1, by2 - by1, " ".join(caption_texts)))

        prev_page_bottom_captions = [c for c in caption_boxes if c[1] > img.shape[0]*0.7]

        img_count = 0
        for (x, y, w, h, caption_text) in final_boxes:
            roi = img[y:y + h, x:x + w]
            if roi.size == 0:
                continue
            img_filename = f"page_{page_index + 1}_fig_{img_count + 1}.png"
            abs_img_path = os.path.join(output_folder, img_filename)
            cv2.imwrite(abs_img_path, cv2.cvtColor(roi, cv2.COLOR_RGB2BGR))

            # ✅ 使用用户指定 output_folder + 文件名，确保 /root/... 绝对路径
            abs_img_path = os.path.join("pictures_final/", img_filename).replace("\\", "/")

            fig_id, chapter, pure_caption = "", "", caption_text
            m = re.match(r'^(图|表)\s*(\d+)(?:-(\d+))?\s*(.*)', caption_text)
            if m:
                prefix, ch, sec, rest = m.groups()
                if sec:
                    fig_id = f"Fig{ch}-{sec}"
                else:
                    fig_id = f"Fig{ch}"
                chapter = f"第{ch}章"
                pure_caption = rest.strip()

            results.append({
                "id": fig_id,
                "caption": pure_caption,
                "path": abs_img_path,  # Linux绝对路径
                "chapter": chapter
            })
            img_count += 1

    pdf_doc.close()

    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("提取完成（图片 + 标题 + JSON 保存）！")


#统计文本字数
def count_words(text):
    # 匹配中文字符（一个汉字记为一个词）
    chinese = re.findall(r'[\u4e00-\u9fff]', text)

    # 匹配英文单词（连续字母组成一个单词）
    english = re.findall(r'[a-zA-Z]+', text)

    # 匹配数字（如果需要也算作一个“词”）
    numbers = re.findall(r'\d+', text)

    return len(chinese) + len(english) + len(numbers)

#提取字符串内数字
def extract_number(s: str) -> int:
    match = re.search(r"\d+", s)   # 找到第一个连续数字
    if match:
        return int(match.group())  # 返回整数
    return None

#拼接md文件
def merge_md_files(files, output_file="merged.md"):
    merged = ""
    for f in files:
        merged += Path(f).read_text(encoding="utf-8").strip() + "\n\n"
    Path(output_file).write_text(merged.strip(), encoding="utf-8")
    print(f"已合并 {len(files)} 个文件 -> {output_file}")
