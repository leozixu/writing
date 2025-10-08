from picture_collect.extractor import images_extractor
import os
import json

# input_path = "TinyLLMLoop_Example-main/top/paper_test.pdf"
# output_path = "TinyLLMLoop_Example-main/top/picture_bank"
# # 调用示例
# extractor = images_extractor.ImageExtractor()
# report = extractor.mixed_process(input_path, output_path)
#
# #save_path = os.path.join("top", "image_report.json")
# with open("TinyLLMLoop_Example-main/top/image_report.json", "w", encoding="utf-8") as f:
#     json.dump(report, f, ensure_ascii=False, indent=4)
#
# print(report)


if __name__ == '__main__':
    input_path = "./top/paper_test.pdf"
    output_path = "./top"

    extractor = images_extractor.ImageExtractor()
    report = extractor.mixed_process(input_path, output_path)
    with open("./top/image_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=4)

    print(report)