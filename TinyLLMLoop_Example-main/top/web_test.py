from pywebio.pin import put_textarea
from pywebio.session import run_js, run_async

import top.test_syntax
import asyncio
import os
from pywebio import start_server
from pywebio.output import put_text, put_markdown, put_success, put_file
from pywebio.input import file_upload
from function import function_leo
import top.outline_generator
import json
from pywebio.input import input_group, textarea
#图片处理
from picture_collect.extractor import images_extractor

# ========== Web 界面 ==========
async def main():
    put_text("📄 论文生成网站（PyWebIO 示例）")
    save_dir = "top"
    os.makedirs(save_dir, exist_ok=True)

    # 0.1 上传 PDF
    put_text("请先上传参考论文 PDF，用于生成提纲")
    first_pdf = await file_upload("上传参考论文 (PDF 文件)", accept=".pdf")
    first_pdf_path = os.path.join(save_dir, "paper_test.pdf")
    with open(first_pdf_path, 'wb') as f:
        f.write(first_pdf['content'])
    put_text(f"✅ 参考论文 {first_pdf['filename']} 上传成功")

    #0.2 从PDF中提取图片信息
    input_path_picture = "./top/paper_test.pdf"
    output_path_picture = "./top"
    extractor = images_extractor.ImageExtractor()
    report = extractor.mixed_process(input_path_picture, output_path_picture)
    with open("./top/image_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=4)

    #0.3 从PDF内提取章节页码信息
    pdfinfo1 = function_leo.extract_pdf_info("top/paper_test.pdf")
    if not pdfinfo1:
        pdfinfo1 = {"info": "未提取到内容"}
    with open("top/pdf_info.json", "w", encoding="utf-8") as f:
        json.dump(pdfinfo1, f, ensure_ascii=False, indent=4)
    with open("top/pdf_info.json", "r", encoding="utf-8") as f:
        pdfinfo_text = f.read()


    # 显示可编辑 JSON
    put_markdown("### 📄 自动提取的 PDF 信息 (在下面编辑并点击提交以确认)")
    new_text = await textarea(
        "pdf_info_editor",
        value=json.dumps(pdfinfo1, ensure_ascii=False, indent=4),
        rows=20,
        placeholder="请在此编辑 JSON，然后点击提交"
    )
    # 尝试解析 JSON
    try:
        parsed = json.loads(new_text)
    except Exception as e:
        put_text(f"⚠️ JSON 解析失败（将保存为原始文本）：{e}")
        parsed = None

    out_path = os.path.join(save_dir, "pdf_info.json")
    if isinstance(parsed, (dict, list)):
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=4)
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(new_text)
    put_text("✅ PDF 信息已保存，开始生成提纲...")


            #此处需要添加从pdf中提取图片并生成json文件的函数

    #0.4 生成提纲
    put_text("正在生成提纲，请稍候...")
    #await top.outline_generator.concurrent_test() #运行提纲生成函数


    # 提供下载给用户修改
    outline_initial_path = "top/outline_for_user_change.md"
    with open(outline_initial_path, "r", encoding="utf-8") as f:
        outline_md_content = f.read()
    #在线编辑版本
    put_markdown("### 📑 自动生成的论文提纲（可在线修改后提交,当前为版本1,请不要更改提纲的格式,只能更改写作要点的内容,或者增添、删除同格式的写作要点,如 -写作要点:......）")
    outline_text = await textarea(
        "outline_editor",
        value=outline_md_content,
        rows=25,
        placeholder="请在此修改提纲内容，然后点击提交"
    )
    # 保存用户修改的提纲
    outline_md_path = os.path.join(save_dir, "Outline_initial.md")
    with open(outline_md_path, "w", encoding="utf-8") as f:
        f.write(outline_text)
    put_success("✅ 提纲已保存，后续步骤将基于修改后的提纲进行")
    put_markdown("### 修改后的提纲预览")
    put_markdown(outline_text)

    # 2. 上传参考论文 (PDF 文件)
    reference_pdf = await file_upload("请上传参考论文 (PDF 文件)", accept=".pdf")
    reference_pdf_path = os.path.join(save_dir, "paper_test.pdf")
    with open(reference_pdf_path, 'wb') as f:
        f.write(reference_pdf['content'])
    put_text(f"✅ 参考论文 {reference_pdf['filename']} 上传成功")


    # 3. 调用黑盒处理程序（生成文件）
    put_text("正在生成成品论文，请稍候...")
    print("111111")
    await top.test_syntax.concurrent_test() #运行扩写函数
    print("222222")
    function_leo.convert_outline("top/outline.json","top/outline.json")

    function_leo.json_to_md("top/outline.json","top/Outline_back.md")

    result_file_path = "top/Outline_back.md"
    # 读取文件内容
    with open(result_file_path, "r", encoding="utf-8") as f:
        result_markdown = f.read()

    # 4. 返回成品论文
    put_success("✅ 论文生成成功！")
    put_markdown(result_markdown)

    # 提供下载功能
    put_file(os.path.basename(result_file_path), result_markdown.encode("utf-8"), "下载生成的论文")


if __name__ == "__main__":
    start_server(main, port=8080, debug=True)
