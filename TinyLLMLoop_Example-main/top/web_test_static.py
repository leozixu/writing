#!/usr/bin/env python3
# web_test_static.py

import os
import sys
import io
import json
import re
import zipfile
import urllib.parse
import threading
import socketserver
import http.server
from functools import partial
from datetime import datetime

import asyncio
from pywebio import start_server
from pywebio.input import file_upload, textarea
from pywebio.output import put_text, put_markdown, put_scrollable, put_success, put_file, put_error
from pywebio.session import run_async

# 你的工程模块（确保路径可用）
import top.test_syntax
import top.outline_generator
from function import function_leo
from picture_collect.extractor import images_extractor

# =========================
# 静态文件服务器（用于提供图片）
# =========================
SAVE_DIR = "top"
os.makedirs(SAVE_DIR, exist_ok=True)

def start_static_server(directory='top', port=8000):
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    httpd = socketserver.TCPServer(("", port), handler, bind_and_activate=False)
    httpd.allow_reuse_address = True
    httpd.server_bind()
    httpd.server_activate()
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd

STATIC_PORT = 8000
# 如果你希望自动检测公网 IP，可在这里替换为自动检测逻辑；当前使用你的示例 IP
static_host = f"http://47.110.83.157:{STATIC_PORT}"
# 启动静态服务器（目录必须存在）
try:
    start_static_server(directory=SAVE_DIR, port=STATIC_PORT)
except Exception as e:
    # 如果端口被占用，记录到终端（后续日志会输出到网页）
    sys.__stdout__.write(f"[WARN] start_static_server error: {e}\n")


# =========================
# Markdown 图片路径重写（将本地路径改为静态 server 的 URL）
# =========================
def rewrite_image_paths(md_text, static_host=static_host):
    def repl_md(m):
        alt = m.group(1)
        path = m.group(2).strip()
        # 如果已经是 URL，直接返回
        if re.match(r'^https?://', path):
            return m.group(0)
        # 去掉 ./ 或 top/ 前缀
        p = path.lstrip('./')
        if p.startswith('top/'):
            p = p[len('top/'):]
        # url encode 每个路径段
        p_enc = '/'.join([urllib.parse.quote(part) for part in p.split('/')])
        return f'![{alt}]({static_host}/{p_enc})'
    return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', repl_md, md_text)


# =========================
# 日志：网页 + 终端 双输出（使用命名 scope）
# =========================
LOG_SCOPE = 'log_scope'

async def _async_put(msg):
    """在会话上下文里写入日志（协程）"""
    put_text(msg, scope=LOG_SCOPE)

def show_log(msg):
    """调度把 msg 写入网页日志（安全回退到终端）"""
    # 确保字符串，去掉末尾换行（pywebio put_text 会自动换行）
    try:
        run_async(_async_put(msg))
    except Exception:
        try:
            put_text(msg, scope=LOG_SCOPE)
        except Exception:
            sys.__stdout__.write(msg + "\n")

class DualConsole:
    """把 stdout 输出同时写到网页（via callback）和终端"""
    def __init__(self, callback):
        self.callback = callback
        self.terminal = sys.__stdout__

    def write(self, message):
        # message 可能包含多行；逐行处理以保证每行都带时间戳
        if not message:
            return
        # splitlines 保留各行，无论是否以换行结尾
        lines = message.splitlines()
        for line in lines:
            if line.strip() == "":
                continue
            timestamp = datetime.now().strftime("%H:%M:%S")
            msg = f"[{timestamp}] {line}"
            # 尝试写到网页（不要抛出异常）
            try:
                self.callback(msg)
            except Exception:
                pass
            # 写到终端
            self.terminal.write(msg + "\n")

    def flush(self):
        try:
            self.terminal.flush()
        except Exception:
            pass


# =========================
# 启动 PyWebIO 主程序
# =========================
async def main():
    # 页面头部
    put_markdown("# 📄 论文生成网站（PyWebIO 示例）")
    put_markdown("请按步骤上传 PDF，编辑提纲，生成最终论文。下方显示实时运行日志（终端 + 网页）。")

    # 创建日志显示区域（命名 scope）
    put_markdown("## 🧾 实时运行日志")
    put_scrollable('', height=300, keep_bottom=True, scope=LOG_SCOPE)
    put_markdown("---")

    # 用 DualConsole 重定向 sys.stdout（所有 print() 都会来到这里）
    orig_stdout = sys.stdout
    sys.stdout = DualConsole(show_log)

    try:
        print("📄 启动论文生成流程（已重定向 stdout -> 网页 + 终端）")
        save_dir = SAVE_DIR
        os.makedirs(save_dir, exist_ok=True)

        # 0.1 上传 PDF
        print("📥 请上传参考论文 PDF，用于生成提纲...")
        first_pdf = await file_upload("上传参考论文 (PDF 文件)", accept=".pdf")
        first_pdf_path = os.path.join(save_dir, "paper_test.pdf")
        with open(first_pdf_path, 'wb') as f:
            f.write(first_pdf['content'])
        print(f"✅ 参考论文 {first_pdf['filename']} 上传成功 ({len(first_pdf['content'])} bytes)")

        # 0.2 从PDF中提取图片信息
        try:
            print("🖼️ 开始提取 PDF 中的图片（若耗时请耐心等待）...")
            extractor = images_extractor.ImageExtractor()
            report = extractor.mixed_process(first_pdf_path, save_dir)
            with open(os.path.join(save_dir, "image_report.json"), "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=4)
            print("✅ 图片信息提取完成，已保存 top/image_report.json")
        except Exception as e:
            print(f"⚠️ 提取图片时出错（继续流程）：{e}")

        # 0.3 从PDF内提取章节页码信息
        try:
            print("🔎 正在提取 PDF 的章节/页码信息...")
            pdfinfo1 = function_leo.extract_pdf_info(first_pdf_path)
            if not pdfinfo1:
                pdfinfo1 = {"info": "未提取到内容"}
            with open(os.path.join(save_dir, "pdf_info.json"), "w", encoding="utf-8") as f:
                json.dump(pdfinfo1, f, ensure_ascii=False, indent=4)
            print("✅ PDF 信息已保存为 top/pdf_info.json")
        except Exception as e:
            print(f"⚠️ 提取 PDF 信息出错（继续流程）：{e}")
            pdfinfo1 = {"info": "提取异常"}

        # 显示可编辑 JSON 给用户确认
        put_markdown("### 📄 自动提取的 PDF 信息（在下方编辑并提交）")
        try:
            initial_pdfinfo_text = json.dumps(pdfinfo1, ensure_ascii=False, indent=4)
        except Exception:
            initial_pdfinfo_text = str(pdfinfo1)
        new_text = await textarea("pdf_info_editor", value=initial_pdfinfo_text, rows=20,
                                  placeholder="请在此编辑 JSON，然后点击提交")

        # 尝试解析并保存
        try:
            parsed = json.loads(new_text)
            with open(os.path.join(save_dir, "pdf_info.json"), "w", encoding="utf-8") as f:
                json.dump(parsed, f, ensure_ascii=False, indent=4)
            print("✅ 用户确认的 PDF 信息已保存")
        except Exception as e:
            # 保存为原始文本（容错）
            with open(os.path.join(save_dir, "pdf_info.json"), "w", encoding="utf-8") as f:
                f.write(new_text)
            print(f"⚠️ JSON 解析失败，已保存原始文本：{e}")

        # 0.4 生成提纲（调用你的 outline 生成逻辑）
        try:
            print("🧾 正在生成提纲（调用 top.outline_generator.main()）...")
            # 如果 outline_generator.main() 是异步函数则 await；如果不是请根据实际情况改写
            # 这里我们假定它是可 await 的（参照你先前代码）
            await top.outline_generator.main()
            print("✅ 提纲生成完成 (top/outline_for_user_change.md)")
        except Exception as e:
            print(f"❌ 生成提纲出错：{e}")
            put_error(f"生成提纲出错：{e}")
            # 继续执行以免阻塞测试流程

        # 读取并呈现生成的提纲供在线编辑
        outline_initial_path = os.path.join(save_dir, "outline_for_user_change.md")
        if os.path.exists(outline_initial_path):
            with open(outline_initial_path, "r", encoding="utf-8") as f:
                outline_md_content = f.read()
        else:
            outline_md_content = "# 未生成提纲，请检查日志"

        put_markdown("### 📑 自动生成的论文提纲（可在线修改后提交）")

        # 打包图片信息 JSON + 图片目录，提供下载 用于参考修改提纲内容
        try:
            image_json_path = os.path.join(save_dir, "image_report.json")
            image_dir = os.path.join(save_dir, "paper_test_images")
            img_zip_filename = "images_with_report.zip"
            img_memory_file = io.BytesIO()
            with zipfile.ZipFile(img_memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
                if os.path.exists(image_json_path):
                    zf.write(image_json_path, os.path.basename(image_json_path))
                if os.path.exists(image_dir):
                    for root, _, files in os.walk(image_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(image_dir))
                            zf.write(file_path, arcname)
            img_memory_file.seek(0)
            put_file(img_zip_filename, img_memory_file.read(), "下载参考图片及信息（用于修改提纲）")
            print("✅ 已打包图片信息供下载")
        except Exception as e:
            print(f"⚠️ 打包图片失败：{e}")

        # 等待用户编辑提纲并提交
        outline_text = await textarea("outline_editor", value=outline_md_content, rows=25,
                                      placeholder="请在此修改提纲内容，然后点击提交")

        # 保存用户修改的提纲
        try:
            outline_md_path = os.path.join(save_dir, "Outline_initial.md")
            with open(outline_md_path, "w", encoding="utf-8") as f:
                f.write(outline_text)
            print("✅ 提纲已保存：top/Outline_initial.md")
        except Exception as e:
            print(f"❌ 保存提纲失败：{e}")

        # 在网页端显示（将图片路径重写为静态服务器 URL）
        outline_text_web = rewrite_image_paths(outline_text, static_host=static_host)
        put_markdown("### 修改后的提纲预览（图片会指向静态服务器）")
        put_markdown(outline_text_web)

        # 3. 调用黑盒处理程序（生成文件）
        print("🛠️ 开始根据提纲生成最终论文（调用 function_leo.convert_outline 等）...")
        try:
            # 若这些操作较慢且是同步的，会阻塞；若可 async，请改为 await
            function_leo.convert_outline(os.path.join(save_dir, "outline.json"), os.path.join(save_dir, "outline.json"))
            function_leo.json_to_md(os.path.join(save_dir, "outline.json"), os.path.join(save_dir, "Outline_back.md"))
            print("✅ 生成最终论文（Markdown）成功")
        except Exception as e:
            print(f"❌ 生成最终论文失败：{e}")

        # 4. 返回成品论文 页面显示并打包下载
        result_file_path = os.path.join(save_dir, "Outline_back.md")
        image_dir = os.path.join(save_dir, "paper_test_images")
        zip_filename = "paper_with_images.zip"

        if os.path.exists(result_file_path):
            with open(result_file_path, "r", encoding="utf-8") as f:
                result_markdown_raw = f.read()
        else:
            result_markdown_raw = "# 未生成最终论文，请查看日志"

        result_markdown_web = rewrite_image_paths(result_markdown_raw, static_host=static_host)
        put_success("✅ 论文生成成功（如下所示）")
        put_markdown(result_markdown_web)

        # 打包 Markdown + 图片目录到 zip 提供下载
        try:
            memory_file = io.BytesIO()
            with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(os.path.basename(result_file_path), result_markdown_raw)
                if os.path.exists(image_dir):
                    for root, _, files in os.walk(image_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(result_file_path))
                            zf.write(file_path, arcname)
            memory_file.seek(0)
            put_file(zip_filename, memory_file.read(), "下载生成的论文（含图片）")
            print("✅ 论文与图片已打包，可供下载")
        except Exception as e:
            print(f"⚠️ 打包论文失败：{e}")

        print("🎉 全流程完成。")
    except Exception as e_all:
        # 主流程内出现未捕获异常
        try:
            put_error(f"发生未捕获异常：{e_all}")
        except Exception:
            pass
        sys.__stdout__.write(f"[UNHANDLED] {e_all}\n")
    finally:
        # 恢复标准输出，防止影响其它服务或 REPL
        sys.stdout = orig_stdout
        print("[INFO] 后端已恢复标准输出（stdout）")


if __name__ == "__main__":
    # 启动 PyWebIO 服务
    start_server(main, host='0.0.0.0', port=8080, debug=False)






# from pywebio.pin import put_textarea
# from pywebio.session import run_js, run_async

# import top.test_syntax
# import asyncio
# import os
# from pywebio import start_server
# from pywebio.output import put_text, put_markdown, put_success, put_file
# from pywebio.input import file_upload
# from function import function_leo
# import top.outline_generator
# import json
# from pywebio.input import input_group, textarea
# #图片处理
# from picture_collect.extractor import images_extractor

# import threading
# import http.server
# import socketserver
# from functools import partial
# import re
# import urllib.parse
# import zipfile
# import io

# # 启动静态文件服务器
# def start_static_server(directory='top', port=8000):
#     handler = partial(http.server.SimpleHTTPRequestHandler, directory=directory)
#     httpd = socketserver.TCPServer(("", port), handler, bind_and_activate=False)
#     httpd.allow_reuse_address = True
#     httpd.server_bind()
#     httpd.server_activate()
#     thread = threading.Thread(target=httpd.serve_forever, daemon=True)
#     thread.start()
#     return httpd

# # 替换 markdown 里的图片路径
# def rewrite_image_paths(md_text, static_host='http://localhost:8000'):
#     def repl_md(m):
#         alt = m.group(1)
#         path = m.group(2).strip()
#         if re.match(r'^https?://', path):
#             return m.group(0)
#         p = path.lstrip('./')
#         if p.startswith('top/'):
#             p = p[len('top/'):]
#         p_enc = '/'.join([urllib.parse.quote(part) for part in p.split('/')])
#         return f'![{alt}]({static_host}/{p_enc})'
#     return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', repl_md, md_text)



# import threading
# import http.server
# import socketserver
# from functools import partial
# import re
# import urllib.parse


# # 启动静态文件服务器
# STATIC_PORT = 8000
# static_host = f"http://47.110.83.157:{STATIC_PORT}"
# #static_host = f"http://localhost:{STATIC_PORT}"
# start_static_server(directory='top', port=STATIC_PORT)
# # ========== Web 界面 ==========
# async def main():
#     put_text("📄 论文生成网站（PyWebIO 示例）")
#     save_dir = "top"
#     os.makedirs(save_dir, exist_ok=True)

#     # 0.1 上传 PDF
#     put_text("请先上传参考论文 PDF，用于生成提纲")
#     first_pdf = await file_upload("上传参考论文 (PDF 文件)", accept=".pdf")
#     first_pdf_path = os.path.join(save_dir, "paper_test.pdf")
#     with open(first_pdf_path, 'wb') as f:
#         f.write(first_pdf['content'])
#     put_text(f"✅ 参考论文 {first_pdf['filename']} 上传成功,正在操作,请稍等......")

#     #0.2 从PDF中提取图片信息
#     input_path_picture = "./top/paper_test.pdf"
#     output_path_picture = "./top"
#     extractor = images_extractor.ImageExtractor()
#     report = extractor.mixed_process(input_path_picture, output_path_picture)
#     with open("./top/image_report.json", "w", encoding="utf-8") as f:
#         json.dump(report, f, ensure_ascii=False, indent=4)



#     #0.3 从PDF内提取章节页码信息
#     pdfinfo1 = function_leo.extract_pdf_info("top/paper_test.pdf")
#     if not pdfinfo1:
#         pdfinfo1 = {"info": "未提取到内容"}
#     with open("top/pdf_info.json", "w", encoding="utf-8") as f:
#         json.dump(pdfinfo1, f, ensure_ascii=False, indent=4)
#     with open("top/pdf_info.json", "r", encoding="utf-8") as f:
#         pdfinfo_text = f.read()


#     # 显示可编辑 JSON
#     put_markdown("### 📄 自动提取的 PDF 信息 (在下面编辑并点击提交以确认)")
#     new_text = await textarea(
#         "pdf_info_editor",
#         value=json.dumps(pdfinfo1, ensure_ascii=False, indent=4),
#         rows=20,
#         placeholder="请在此编辑 JSON，然后点击提交"
#     )
#     # 尝试解析 JSON
#     try:
#         parsed = json.loads(new_text)
#     except Exception as e:
#         put_text(f"⚠️ JSON 解析失败（将保存为原始文本）：{e}")
#         parsed = None

#     out_path = os.path.join(save_dir, "pdf_info.json")
#     if isinstance(parsed, (dict, list)):
#         with open(out_path, "w", encoding="utf-8") as f:
#             json.dump(parsed, f, ensure_ascii=False, indent=4)
#     else:
#         with open(out_path, "w", encoding="utf-8") as f:
#             f.write(new_text)
#     put_text("✅ PDF 信息已保存，开始生成提纲...")


#             #此处需要添加从pdf中提取图片并生成json文件的函数

#     #0.4 生成提纲
#     put_text("正在生成提纲，请稍候...")
#     await top.outline_generator.main() #运行提纲生成函数


#     # 提供下载给用户修改
#     outline_initial_path = "top/outline_for_user_change.md"
#     with open(outline_initial_path, "r", encoding="utf-8") as f:
#         outline_md_content = f.read()
#     #在线编辑版本
#     put_markdown("### 📑 自动生成的论文提纲（可在线修改后提交,当前为版本1,请不要更改提纲的格式,只能更改写作要点的内容,或者增添、删除同格式的写作要点,如 -写作要点:......）")
#     # ===== 打包 图片信息 JSON + 图片目录，提供下载 用于参考修改提纲内容=====
#     image_json_path = "top/image_report.json"
#     image_dir = "top/paper_test_images"
#     img_zip_filename = "images_with_report.zip"
#     img_memory_file = io.BytesIO()
#     with zipfile.ZipFile(img_memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
#         # 添加图片 JSON
#         if os.path.exists(image_json_path):
#             zf.write(image_json_path, os.path.basename(image_json_path))
#         # 添加图片目录
#         if os.path.exists(image_dir):
#             for root, _, files in os.walk(image_dir):
#                 for file in files:
#                     file_path = os.path.join(root, file)
#                     arcname = os.path.relpath(file_path, os.path.dirname(image_dir))  # 保持相对路径
#                     zf.write(file_path, arcname)
#     img_memory_file.seek(0)
#     put_file(img_zip_filename, img_memory_file.read(), "下载参考图片及信息（用于修改提纲）")

#     #等待用户确认提交
#     outline_text = await textarea(
#         "outline_editor",
#         value=outline_md_content,
#         rows=25,
#         placeholder="请在此修改提纲内容，然后点击提交"
#     )



#     # 保存用户修改的提纲
#     outline_md_path = os.path.join(save_dir, "Outline_initial.md")
#     with open(outline_md_path, "w", encoding="utf-8") as f:
#         f.write(outline_text)
#     put_success("✅ 提纲已保存，后续步骤将基于修改后的提纲进行")
#     put_markdown("### 修改后的提纲预览")
#     outline_text = rewrite_image_paths(outline_text, static_host=static_host)
#     put_markdown(outline_text)

#     # 2. 上传参考论文 (PDF 文件)
#     # reference_pdf = await file_upload("请上传参考论文 (PDF 文件)", accept=".pdf")
#     # reference_pdf_path = os.path.join(save_dir, "paper_test.pdf")
#     # with open(reference_pdf_path, 'wb') as f:
#     #     f.write(reference_pdf['content'])
#     # put_text(f"✅ 参考论文 {reference_pdf['filename']} 上传成功")


#     # 3. 调用黑盒处理程序（生成文件）
#     put_text("正在生成成品论文，请稍候...")
#     print("111111")
#     #await top.test_syntax.concurrent_test() #运行扩写函数
#     print("222222")
#     function_leo.convert_outline("top/outline.json","top/outline.json")

#     function_leo.json_to_md("top/outline.json","top/Outline_back.md")

#     result_file_path = "top/Outline_back.md"
#     image_dir = "top/paper_test_images"  # 假设你的图片都在这个目录里
#     zip_filename = "paper_with_images.zip"

#     # 读取文件内容
#     with open(result_file_path, "r", encoding="utf-8") as f:
#         result_markdown_raw = f.read()

#     # 4. 返回成品论文 页面显示
#     put_success("✅ 论文生成成功！")
#     result_markdown_web = rewrite_image_paths(result_markdown_raw, static_host=static_host)
#     put_markdown(result_markdown_web)

#     # ===== 打包 Markdown 和图片目录到 zip =====
#     memory_file = io.BytesIO()
#     with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
#         # 添加 Markdown 文件
#         zf.writestr(os.path.basename(result_file_path), result_markdown_raw)

#         # 添加图片目录
#         if os.path.exists(image_dir):
#             for root, _, files in os.walk(image_dir):
#                 for file in files:
#                     file_path = os.path.join(root, file)
#                     arcname = os.path.relpath(file_path, os.path.dirname(result_file_path))  # 保持相对路径
#                     zf.write(file_path, arcname)

#     memory_file.seek(0)

#     # 提供下载 zip
#     put_file(zip_filename, memory_file.read(), "下载生成的论文（含图片）")

#     # # 提供下载功能
#     # put_file(os.path.basename(result_file_path), result_markdown.encode("utf-8"), "下载生成的论文")


# if __name__ == "__main__":
#     start_server(main, host='0.0.0.0', port=8080, debug=False)
#     #start_server(main, port=8080, debug=True)
