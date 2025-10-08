import fitz
import json
import logging
import os
import pdfplumber
import sys
import math
import re

from collections import Counter
from collections import defaultdict
from tqdm import tqdm

# === 日志配置 ===
logging.basicConfig(
	level=logging.INFO,
	format="[%(levelname)s] %(message)s %(asctime)s ",
	handlers=[
		logging.StreamHandler(sys.stdout),
	]
)
logger = logging.getLogger(__name__)
# 关闭 pdfminer 的警告日志
logging.getLogger("pdfminer").setLevel(logging.ERROR)
logging.getLogger("pdfplumber").setLevel(logging.ERROR)

class ImageExtractor:
	"""
	图片提取
	"""
	def __init__(self, config_path=None):
		# ===配置文件===
		project_root = os.path.dirname(os.path.dirname(__file__))
		self.config_path = config_path or os.path.join(project_root, "config", "config.json")
		self.config: dict = json.load(open(self.config_path, "r", encoding="utf-8"))
		
		# 初始话属性信息
		self.watermark_dict = {}  # 水印
		self.header_footer_dict = {}  # 页眉页脚页码
		self.image_legend_dict = {}  # 图例
		self.table_legend_dict = {}  # 表例
		self.normal_dict = {}  # 正文
		
	# ===文本分类===
	def _first_parse_pdf(self, pdf_path, threshold=0.8, margin_ratio=0.2):
		"""
		调用 extract_pdf_textblocks 处理 PDF，并把结果存到类属性
		"""
		(self.watermark_dict,
		 self.header_footer_dict,
		 self.image_legend_dict,
		 self.table_legend_dict,
		 self.normal_dict) = self._extract_pdf_textblocks(
			pdf_path, threshold, margin_ratio
		)
	
	@staticmethod
	def _uppercase_ratio(text: str) -> float:
		"""
		计算一段话中大写英文字母占所有字符的比例
		:param text: str，一段话（比如 PDF 的一个 block 里的内容）
		:return: float，大写字母比例（0~1）
		"""
		if not text:
			return 0.0
		clean_text = re.sub(r"[\s0-9]+", "", text)
		# logger.info(clean_text)
		uppercase = re.findall(r"[A-Z]", text)  # 大写字母
		return len(uppercase) / len(clean_text)
	
	@staticmethod
	def _get_block_angle(block):
		"""
		根据 block 中第一行的 dir 向量计算倾角
		返回角度，单位：度
		"""
		if not block.get("lines"):
			return 0.0
		
		dx, dy = block["lines"][0]["dir"]
		angle = math.degrees(math.atan2(dy, dx))
		return round(angle, 2)
	
	def _is_probable_page_number(self, line: str) -> bool:
		"""
		判断一行文本是否可能是页码
		:param line: 文本行
		:return: bool类型，判断结果
		"""
		patterns = self.config["page_num"]["pattern"]
		return any(re.fullmatch(pat, line.strip(), re.IGNORECASE) for pat in patterns)
	
	def _is_probable_header_footer(self, line: str) -> bool:
		"""判断一行是否可能是页眉或页脚"""
		if not (5 <= len(line) <= 60):
			return False
		
		patterns = self.config["header_footer"]["pattern"]
		return any(re.search(p, line, re.IGNORECASE) for p in patterns)
	
	def _extract_pdf_textblocks(self, pdf_path: str, wtr_thd: float = 0.9, hf_thd: float = 0.8, cluster_thd=5):
		doc = fitz.open(pdf_path)
		
		# ----------- 结果容器 -----------
		watermark_dict = defaultdict(list)
		header_footer_dict = defaultdict(list)
		# candidate_normal_dict = defaultdict(list)  # 临时容器
		normal_dict = defaultdict(list)
		image_legend_dict = defaultdict(list)
		table_legend_dict = defaultdict(list)
		
		# 记录每个块的出现情况: key = (rounded rect, text), value = 出现页集合
		block_occurrences = defaultdict(set)
		all_blocks = defaultdict(list)
		
		# 一次遍历，信息收集
		for page_num, page in enumerate(doc, start=0):
			page_dict = page.get_text("dict")
			for block in page_dict["blocks"]:
				if block["type"] != 0:  # 非文本块
					continue
				x0, y0, x1, y1 = block["bbox"]
				angle = self._get_block_angle(block)  # 角度
				
				# 文字拼接
				text_parts = []
				for line in block.get("lines", []):
					for span in line.get("spans", []):
						text_parts.append(span["text"])
				text = "\n".join(text_parts).strip()
				if not text:
					continue
				
				# 位置取整，避免浮点误差
				rect_key = (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
				key = (rect_key, text)
				
				block_occurrences[key].add(page_num)
				all_blocks[page_num].append((x0, y0, x1, y1, text, angle))
		
		total_pages = len(doc)
		image_pattern = re.compile(self.config["image_legend"]["pattern"], re.IGNORECASE)
		table_pattern = re.compile(self.config["table_legend"]["pattern"], re.IGNORECASE)
		
		# 正式过滤
		for page_num, blocks in all_blocks.items():
			top_block = min(blocks, key=lambda b: b[1])  # y0 min
			bottom_block = max(blocks, key=lambda b: b[3])  # y1 max
			usd_blocks = set()  # 聚类记录
			
			for block in blocks:
				if block in usd_blocks:
					continue
				
				x0, y0, x1, y1, text, angle = block
				rect_key = (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
				key = (rect_key, text)
				
				# 判断是否是水印：(1)出现比例 >= 阈值 (2)角度接近45度
				occur_ratio = len(block_occurrences[key]) / total_pages
				if occur_ratio >= wtr_thd and abs(abs(angle) - 45) < 20:
					watermark_dict[page_num].append(block)
					continue
				
				# 判断页眉页脚
				if block in (top_block, bottom_block):
					if self._is_probable_header_footer(" ".join(text.split())) or self._is_probable_page_number(
							" ".join(text.split())):
						header_footer_dict[page_num].append(block)
						continue
					occur_ratio = len(block_occurrences[key]) / total_pages
					if occur_ratio >= hf_thd:
						header_footer_dict[page_num].append(block)
						continue
					if self._uppercase_ratio(" ".join(text.split())) >= 0.4:  # 大写字母占比
						header_footer_dict[page_num].append(block)
						continue
				
				# 判断图例表例并进行聚类
				text_clean = text.strip()
				if image_pattern.match(text_clean) and 5 < len(text_clean) < 180:
					# 聚类
					cluster = [block]
					for other in blocks:
						if other == block:
							continue
						ox0, oy0, ox1, oy1, otext, _ = other
						if abs(oy0 - y1) <= cluster_thd:
							cluster.append(other)
							usd_blocks.add(other)
					cluster_text = " ".join([blk[4] for blk in cluster])  # blk[4] 是文本
					x0 = min(blk[0] for blk in cluster)
					y0 = min(blk[1] for blk in cluster)
					x1 = max(blk[2] for blk in cluster)
					y1 = max(blk[3] for blk in cluster)
					cluster_rect = fitz.Rect(x0, y0, x1, y1)
					image_legend_dict[page_num].append({
						"rect": cluster_rect,
						"text": cluster_text
					})
				
				elif table_pattern.match(text_clean) and 5 < len(text_clean) < 180:
					block_width = x1 - x0  # 当前块的宽度
					if block_width > 300:
						# 聚类启动
						cluster = [block]
						for other in blocks:
							if other == block:
								continue
							ox0, oy0, ox1, oy1, otext, _ = other
							if abs(oy0 - y1) <= cluster_thd:
								cluster.append(other)
								usd_blocks.add(other)
						cluster_text = " ".join([blk[4] for blk in cluster])  # blk[4] 是文本
						x0 = min(blk[0] for blk in cluster)
						y0 = min(blk[1] for blk in cluster)
						x1 = max(blk[2] for blk in cluster)
						y1 = max(blk[3] for blk in cluster)
						cluster_rect = fitz.Rect(x0, y0, x1, y1)
						table_legend_dict[page_num].append({
							"rect": cluster_rect,
							"text": cluster_text
						})
					else:
						# 宽度小于等于 300，直接放进 table_legend_dict
						table_legend_dict[page_num].append({
							"rect": fitz.Rect(x0, y0, x1, y1),
							"text": text_clean
						})
				else:
					normal_dict[page_num].append(block)
		
		doc.close()
		return (
			dict(watermark_dict),
			dict(header_footer_dict),
			dict(image_legend_dict),
			dict(table_legend_dict),
			dict(normal_dict)
		)
	
	# ===图片提取===
	@staticmethod
	def _normalize_rect(rect, decimals=1):
		"""把rect四舍五入，避免浮点差异导致判定不同"""
		return tuple(round(v, decimals) for v in (rect.x0, rect.y0, rect.x1, rect.y1))
	
	def _collect_all_drawings(self, pdf_path):
		"""收集所有页的矢量图位置"""
		doc = fitz.open(pdf_path)
		rect_positions = []
		for page_num, page in enumerate(doc, start=1):
			for d in page.get_drawings():
				rect = fitz.Rect(d["rect"])
				rect_positions.append(self._normalize_rect(rect))
		doc.close()
		return rect_positions
	
	def _collect_all_images(self, pdf_path):
		"""
		收集PDF中所有位图的矩形区域（bbox），用于重复性检测
		:return：list[tuple]，每个元素是标准化后的矩形 (x0,y0,x1,y1)
		"""
		doc = fitz.open(pdf_path)
		all_imgs = []
		
		for page in doc:
			for img in page.get_images(full=True):
				try:
					bbox = page.get_image_bbox(img)
				except IndexError:
					continue  # 没有就跳过
				rect_norm = self._normalize_rect(bbox)  # 归一化，避免浮点误差
				all_imgs.append(rect_norm)
		
		doc.close()
		return all_imgs
	
	def _filter_tables_by_text_overlap(self, tables_info, ratio_threshold=0.3):
		"""
		根据文本框所占的比例判定表格是否合理
		:param tables_info: 利用pdfplumber提取出的初始表格范围信息
		:param normal_dict: 正文文本框信息（图/表）
		:param ratio_threshold: 面积阈值
		:return: 过滤之后地表格位置信息
		"""
		filtered_tables = {}
		
		for page_num, tables in tables_info.items():
			# 安全获取文本块列表
			page_texts = self.normal_dict.get(page_num, [])
			kept_tables = []
			
			# 遍历该页所有表格候选框（即使为空列表也安全）
			for table_bbox in tables_info.get(page_num, []):
				x0, y0, x1, y1 = table_bbox
				area_table = (x1 - x0) * (y1 - y0)
				sum_area_texts = 0
				
				for bx0, by0, bx1, by1, text, angle in page_texts:
					# 计算交集面积
					ix0, iy0 = max(x0, bx0), max(y0, by0)
					ix1, iy1 = min(x1, bx1), min(y1, by1)
					if ix1 > ix0 and iy1 > iy0:
						sum_area_texts += (ix1 - ix0) * (iy1 - iy0)
				
				# 比例判断
				ratio = sum_area_texts / area_table if area_table > 0 else 0
				if ratio >= ratio_threshold:
					kept_tables.append(table_bbox)
			
			# 只有保留下来的表格才加入结果
			if kept_tables:
				filtered_tables[page_num] = kept_tables
		
		return filtered_tables
	
	@staticmethod
	def _rect_area(bbox):
		"""
		计算矩形区域面积
		bbox: (x0, y0, x1, y1)
		"""
		x0, y0, x1, y1 = bbox
		return max(0, x1 - x0) * max(0, y1 - y0)
	
	@staticmethod
	def _rect_iou(r1, r2):
		"""
		计算两个矩形的 IOU (交并比)，判断相似度
		r = (x0, y0, x1, y1)
		"""
		x0 = max(r1[0], r2[0])
		y0 = max(r1[1], r2[1])
		x1 = min(r1[2], r2[2])
		y1 = min(r1[3], r2[3])
		
		inter_w = max(0, x1 - x0)
		inter_h = max(0, y1 - y0)
		inter_area = inter_w * inter_h
		
		area1 = (r1[2] - r1[0]) * (r1[3] - r1[1])
		area2 = (r2[2] - r2[0]) * (r2[3] - r2[1])
		union_area = area1 + area2 - inter_area
		
		return inter_area / union_area if union_area > 0 else 0
	
	@staticmethod
	def _group_rects(rects_dict, y_threshold=15):
		"""
		一次合并：如果矩形的y范围有重叠 / 接近，就合并成一个组
		"""
		if not rects_dict:
			return []
		
		# 拆分为矢量和位图
		vectors = [r for r in rects_dict if r.get("type") == "vector"]
		images = [r for r in rects_dict if r.get("type") == "image"]
		groups = []
		
		# === 矢量分组逻辑 ===
		if vectors:
			rects = sorted(vectors, key=lambda r: r["rect"].y0)
			current_group = [rects[0]]
			
			for rect in rects[1:]:
				last = current_group[-1]
				if rect["rect"].y0 <= last["rect"].y1 + y_threshold:
					current_group.append(rect)
				else:
					groups.append(current_group)
					current_group = [rect]
			groups.append(current_group)
		
		# === 位图单独成组 ===
		for img in images:
			groups.append([img])  # 每个图片独立为一组
		
		return groups
	
	def _group_rects_again(self, groups, y_gap=10, min_height=20, min_width=40):
		"""
		二次合并：合并重叠或间距小于 y_gap 的橙色矩形框
		"""
		if not groups:
			return []
		
		# 计算每个 group 的整体橙框（bounding box）
		group_boxes = []
		for g in groups:
			y_top = max(r["rect"].y1 for r in g)  # 最高点（y1 越大越下）
			y_bottom = min(r["rect"].y0 for r in g)  # 最低点（y0 越小越上）
			# 去掉高度很小的橙框
			if y_top - y_bottom < min_height:
				continue
			x0 = min(r["rect"].x0 for r in g)
			x1 = max(r["rect"].x1 for r in g)
			# 去掉宽度很小的橙色框
			if x1 - x0 < min_width:
				continue
			group_boxes.append({
				"rect": (x0, y_bottom, x1, y_top),
				"members": g
			})
		
		if not group_boxes:  # 仍然为空
			return []
		
		# 按 y_bottom 排序，方便逐行合并
		group_boxes.sort(key=lambda b: b["rect"][1])
		
		merged = []
		current = group_boxes[0]["members"]
		current_rect = group_boxes[0]["rect"]
		
		for gb in group_boxes[1:]:
			y0, y1 = gb["rect"][1], gb["rect"][3]  # gb 的上下
			# 判断是否接近 / 重叠
			if y0 <= current_rect[3] + y_gap:
				current.extend(gb["members"])
				# 更新 current_rect（扩大范围）
				current_rect = (
					min(current_rect[0], gb["rect"][0]),
					min(current_rect[1], gb["rect"][1]),
					max(current_rect[2], gb["rect"][2]),
					max(current_rect[3], gb["rect"][3]),
				)
			else:
				merged.append(current)
				current = gb["members"]
				current_rect = gb["rect"]
		
		merged.append(current)
		return merged
	
	@staticmethod
	def _cluster_text_blocks(merged_groups, rects_dict, mode="h",
							 x_tol=20, y_tol=5, x_threshold=20, y_threshold=5):
		"""
		文本聚类：根据 mode 控制左右 or 上下聚类
		- merged_groups: 二次聚类完成的分组 (list[list[dict]])，只含非文本元素
		- rects_dict: 页面所有元素 (list[dict])，含文本/图片/矢量
		- mode: "horizontal" 左右聚类，"vertical" 上下聚类
		- x_tol, y_tol: 容差
		- x_threshold, y_threshold: 判定距离

		:return: 新的 groups (list[list[dict]])
		"""
		new_groups = []
		text_blocks = [r for r in rects_dict if r["type"] == "text_block"]
		
		for group in merged_groups:
			# 计算该组的外接矩形
			gx0 = min(r["rect"].x0 for r in group)
			gy0 = min(r["rect"].y0 for r in group)
			gx1 = max(r["rect"].x1 for r in group)
			gy1 = max(r["rect"].y1 for r in group)
			
			candidate_texts = []
			for tb in text_blocks:
				tx0, tx1, ty0, ty1 = tb["rect"].x0, tb["rect"].x1, tb["rect"].y0, tb["rect"].y1
				
				if mode == "h":  # 横向聚类
					# y 方向重叠 + x 距离判定
					if (ty0 >= gy0 - y_tol) and (ty1 <= gy1 + y_tol):
						if tx1 < gx0 and (tx1 > gx0 - x_threshold):
							candidate_texts.append(tb)
						elif gx0 < tx1 < gx1:
							candidate_texts.append(tb)
						elif gx1 < tx1 and tx0 < gx1 + x_threshold:
							candidate_texts.append(tb)
				
				elif mode == "v":  # 纵向聚类
					# x 方向重叠 + y 距离判定
					if (tx0 >= gx0 - x_tol) and (tx1 <= gx1 + x_tol):
						if ty1 < gy0 and (ty1 > gy0 - y_threshold):
							candidate_texts.append(tb)
						elif gy0 < ty1 < gy1:
							candidate_texts.append(tb)
						elif gy1 < ty1 and (ty0 < gy1 + y_threshold):
							candidate_texts.append(tb)
			
			if candidate_texts:
				new_groups.append(group + candidate_texts)
			else:
				new_groups.append(group)
		
		return new_groups
	
	@staticmethod
	def _rect_edges(rect):
		"""返回矩形四条边 ((x0,y0),(x1,y1)) 格式"""
		return [
			((rect.x0, rect.y0), (rect.x1, rect.y0)),  # top
			((rect.x0, rect.y1), (rect.x1, rect.y1)),  # bottom
			((rect.x0, rect.y0), (rect.x0, rect.y1)),  # left
			((rect.x1, rect.y0), (rect.x1, rect.y1)),  # right
		]
	
	@staticmethod
	def _edge_overlap(edge1, edge2, min_overlap_ratio=0.2, max_dist=5):
		"""
		判断两条边是否接近重合
		- edge1, edge2: ((x0, y0), (x1, y1)) 格式
		- tolerance: 判断平行的容差（角度/坐标误差）
		- min_overlap_ratio: 最小重合比例（相对短边长度）
		- max_dist: 两条边之间的最大距离限制
		"""
		# 判断水平边
		if abs(edge1[0][1] - edge1[1][1]) < 1e-3 and abs(edge2[0][1] - edge2[1][1]) < 1e-3:
			y_dist = abs(edge1[0][1] - edge2[0][1])
			if y_dist <= max_dist:  # 限制垂直距离
				x1_min, x1_max = min(edge1[0][0], edge1[1][0]), max(edge1[0][0], edge1[1][0])
				x2_min, x2_max = min(edge2[0][0], edge2[1][0]), max(edge2[0][0], edge2[1][0])
				overlap = max(0, min(x1_max, x2_max) - max(x1_min, x2_min))
				min_len = min(x1_max - x1_min, x2_max - x2_min)
				return overlap >= min_overlap_ratio * min_len
		# 判断垂直边
		elif abs(edge1[0][0] - edge1[1][0]) < 1e-3 and abs(edge2[0][0] - edge2[1][0]) < 1e-3:
			x_dist = abs(edge1[0][0] - edge2[0][0])
			if x_dist <= max_dist:  # 限制水平距离
				y1_min, y1_max = min(edge1[0][1], edge1[1][1]), max(edge1[0][1], edge1[1][1])
				y2_min, y2_max = min(edge2[0][1], edge2[1][1]), max(edge2[0][1], edge2[1][1])
				overlap = max(0, min(y1_max, y2_max) - max(y1_min, y2_min))
				min_len = min(y1_max - y1_min, y2_max - y2_min)
				return overlap >= min_overlap_ratio * min_len
		return False
	
	def _filter_groups(self, page_num, merged_groups, tables_info=None, re_thd=0.8, area_thd=0.5):
		"""
		表格过滤器
		- threshold: 矩形比例阈值
		- tables_info: dict[page_num] = [bbox1, bbox2,...]  表格边界框
		"""
		new_groups = []
		high_re_groups = []
		page_texts = self.normal_dict.get(page_num, [])  # 该页文本框信息
		
		for group in merged_groups:
			# 计算该组外接矩形
			x0 = round(min(r["rect"].x0 for r in group), 3)
			y0 = round(min(r["rect"].y0 for r in group), 3)
			x1 = round(max(r["rect"].x1 for r in group), 3)
			y1 = round(max(r["rect"].y1 for r in group), 3)
			
			area_grp = (x1 - x0) * (y1 - y0)
			sum_area_texts = 0
			
			for bx0, by0, bx1, by1, text, angle in page_texts:
				# 计算交集面积
				ix0, iy0 = max(x0, bx0), max(y0, by0)
				ix1, iy1 = min(x1, bx1), min(y1, by1)
				if ix1 > ix0 and iy1 > iy0:
					sum_area_texts += (ix1 - ix0) * (iy1 - iy0)  # 面积和
			
			# 比例判断
			area_ratio = sum_area_texts / area_grp if area_grp > 0 else 0
			
			# --- "re"判断 ---
			total_items = 0
			re_items = 0
			for d in group:
				for item in d["items"]:
					total_items += 1
					if item[0] == "re":
						re_items += 1
			ratio = re_items / total_items if total_items > 0 else 0
			ratio = round(ratio, 2)
			
			# "re"比例和文本面积占比
			if ratio > re_thd and area_ratio > area_thd:
				high_re_groups.append(group)
				continue  # 过滤掉
			
			# --- 空间判断 ---
			# 如果提供了表格 bbox，就检查空间重合
			if tables_info is not None:
				group_rect = fitz.Rect(x0, y0, x1, y1)
				group_edges = self._rect_edges(group_rect)
				
				# 遍历该页所有表格
				for table_bbox in tables_info.get(page_num, []):
					table_rect = fitz.Rect(table_bbox)
					table_edges = self._rect_edges(table_rect)
					
					# 判断是否有 >=3 条边重合
					overlap_count = sum(
						self._edge_overlap(e1, e2) for e1 in group_edges for e2 in table_edges
					)
					if overlap_count >= 3:
						# 认为这是表格，丢弃该组
						break
				else:
					# 没触发 break 保留
					new_groups.append(group)
			else:
				new_groups.append(group)
		
		return new_groups, high_re_groups
	
	def _extract_image_groups_from_pdf(self, pdf_path, output_path, repeat_ratio=0.2, legend_margin=40):
		"""提取所有图片信息，并返回报告"""
		# 存储位置
		pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
		images_dir = os.path.join(output_path, f"{pdf_name}_images")
		os.makedirs(images_dir, exist_ok=True)
		
		# 打开文件
		doc = fitz.open(pdf_path)
		total_pages = len(doc)
		image_groups_count = 0
		report = []  # 报告格式
		
		# 1.统计过滤所有重复页
		all_rects = self._collect_all_drawings(pdf_path)
		counts = Counter(all_rects)
		repeat_threshold = int(total_pages * repeat_ratio)
		common_rects = {rect for rect, cnt in counts.items() if cnt >= repeat_threshold}
		
		# 2.统计过滤所有重复位图
		all_imgs = self._collect_all_images(pdf_path)
		img_counts = Counter(all_imgs)
		img_repeat_threshold = int(total_pages * repeat_ratio)
		common_imgs = {rect for rect, cnt in img_counts.items() if cnt >= img_repeat_threshold}
		
		# 3.表格位置提取
		# 第一步：用 pdfplumber 获取表格位置信息
		tables_info = {}
		with pdfplumber.open(pdf_path) as pdf:
			for page_num, page in enumerate(pdf.pages):
				tables = page.find_tables()
				tables_info[page_num] = [t.bbox for t in tables]  # 保存表格bbox
		# raw_tables_position = self._filter_tables_by_text_overlap(tables_info, 0.3)
		all_images_position = defaultdict(list)  # 保存所有图片的位置信息
		
		# 4.逐页提取图片信息
		for page_num, page in enumerate(tqdm(doc, total=total_pages, desc="处理界面", ascii="░█"), start=0):
			items = []  # 最终输出
			rects_dict = []
			# valid_blocks = 0
			# 图例信息
			page_legends = self.image_legend_dict.get(page_num, [])
			
			# 4.0文本信息
			for b, block in enumerate(self.normal_dict.get(page_num, []), start=0):
				x0, y0, x1, y1, text, angle = block  # 解包
				# valid_blocks += 1
				rect = fitz.Rect(x0, y0, x1, y1)
				rects_dict.append({
					"type": "text_block",
					"rect": rect,
					"items": []
				})
			
			# 4.1位图信息
			for img in page.get_images(full=True):
				try:
					bbox = page.get_image_bbox(img)
				except IndexError:
					continue
				if any(self._rect_iou(self._normalize_rect(bbox), ci) > 0.1 for ci in common_imgs) and \
						any(abs(self._rect_area(bbox) - self._rect_area(cj)) < 0.05 * self._rect_area(cj) \
							for cj in common_imgs):
					continue
				x0, y0, x1, y1 = bbox
				if x0 < x1 or y0 < y1:
					continue
				rects_dict.append({
					"type": "image",
					"rect": bbox,
					"items": []
				})
			# items.append((bbox, "img"))
			
			# 4.2.1逐个矢量对象
			for d in page.get_drawings():
				rect = fitz.Rect(d["rect"])
				if self._normalize_rect(rect) in common_rects:
					continue
				rects_dict.append({
					"type": "vector",
					"rect": rect,
					"items": d["items"]
				})
			
			# 4.2.2图组
			if rects_dict:
				groups = self._group_rects(rects_dict)
				merged_groups = self._group_rects_again(groups)
				merged_groups_with_transverse = self._cluster_text_blocks(merged_groups, rects_dict, "h")
				new_merged_groups, high_re_groups = self._filter_groups(page_num, merged_groups_with_transverse,
																		tables_info, 0.8)
				new_new_merged_groups = self._cluster_text_blocks(new_merged_groups, rects_dict, "v")
				# 计算该组的外接矩形
				for group in new_new_merged_groups:
					x0 = min(r["rect"].x0 for r in group)
					y0 = min(r["rect"].y0 for r in group)
					x1 = max(r["rect"].x1 for r in group)
					y1 = max(r["rect"].y1 for r in group)
					group_rect = fitz.Rect(x0, y0, x1, y1)
					items.append((group_rect, "group"))
			
			items.sort(key=lambda x: x[0].y0)  # 排序操作
			all_images_position[page_num].append(items)  # 记录
			
			# 5.图片和图例对应
			matched_items = []
			for img in items:
				img_rect = img[0]
				legend_text = None
				for legend in page_legends:
					distance = legend["rect"].y0 - img_rect.y1
					if abs(distance) <= legend_margin:
						legend_text = legend["text"]
						break
				if legend_text:  # 只保留有图例的图片
					matched_items.append((img_rect, legend_text))
			
			# 6.输出
			for idx, (bbox, legend_text) in enumerate(matched_items, start=1):
				pix = page.get_pixmap(clip=bbox, dpi=200)
				out_path = os.path.join(images_dir, f"page{page_num + 1}_img{idx}.png")
				pix.save(out_path)

				relative_path = os.path.basename(images_dir) + "/" + os.path.basename(out_path)

				report.append({
					"index": image_groups_count,
					"name": f"page{page_num + 1}_img{idx}",
					"legend": legend_text.replace("\n", " "),
					"page": page_num + 1,
					"path": relative_path
				})
				image_groups_count += 1
		
		logger.info(f"✅ 图片信息提取完成，共保存 {image_groups_count} 张图片到 '{images_dir}'")
		doc.close()
		return report
	
	def mixed_process(self, input_dir, output_dir):
		"""
		接口函数
		:param input_dir: pdf输入路径
		:param output_dir: 输出路径
		:return: 图片信息.json
		"""
		# 初始化
		self._first_parse_pdf(input_dir, 0.8, 0.2)
		# 图片处理
		try:
			img_report = self._extract_image_groups_from_pdf(input_dir, output_dir)

			# save_path = os.path.join("picture_collect/exemple", "image_report.json")
			# with open(save_path, "w", encoding="utf-8") as f:
			# 	json.dump(img_report, f, ensure_ascii=False, indent=4)

			return img_report
		except Exception as e:
			logger.error(e)

if __name__ == '__main__':
	input_path = "picture_collect/extractor/paper_test.pdf"
	output_path = "top/picture_bank"
	# 调用示例
	extractor = ImageExtractor()
	report = extractor.mixed_process(input_path, output_path)
	print(report)
	
	