import re
from xml.etree import ElementTree


PATENT_RULE_BASIS = "专利法实施细则第二十一条及《专利审查指南》第一部分第一章4.3"
PAGE_RULE_BASIS = "国家知识产权局申请文件A4规格和留白要求"


def _patent_check(code: str, name: str, status: str, detail: str, basis: str = PATENT_RULE_BASIS) -> dict[str, str]:
    return {"code": code, "name": name, "status": status, "detail": detail, "basis": basis}


def _tag(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _path_points(data: str) -> list[tuple[float, float]]:
    tokens = re.findall(r"[MLHVZmlhvz]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?", data)
    points: list[tuple[float, float]] = []
    command = ""
    x = y = 0.0
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            index += 1
            if command.upper() == "Z":
                continue
        if command.upper() in {"M", "L"} and index + 1 < len(tokens):
            next_x, next_y = float(tokens[index]), float(tokens[index + 1])
            if command.islower():
                x, y = x + next_x, y + next_y
            else:
                x, y = next_x, next_y
            points.append((x, y))
            index += 2
        elif command.upper() == "H":
            value = float(tokens[index])
            x = x + value if command.islower() else value
            points.append((x, y))
            index += 1
        elif command.upper() == "V":
            value = float(tokens[index])
            y = y + value if command.islower() else value
            points.append((x, y))
            index += 1
        else:
            index += 1
    return points


def manual_patent_review_checks() -> list[dict[str, str]]:
    """Return professional judgment items that do not affect automated status."""
    return [
        _patent_check("protected_subject", "产品形状与构造表达", "review", "需人工确认附图是否充分反映要求保护的形状、构造或其结合"),
        _patent_check("reference_consistency", "附图标记与说明书一致性", "review", "当前未取得可靠的完整说明书标记集合，需人工逐项核对"),
        _patent_check("view_adequacy", "视图与技术特征表达充分性", "review", "需人工确认剖视、局部放大和必要文字是否足以说明技术特征"),
    ]


def patent_drawing_precheck(svg: str) -> tuple[str, list[dict[str, str]]]:
    """Run deterministic form checks and expose judgment calls as review items."""
    checks: list[dict[str, str]] = []
    try:
        root = ElementTree.fromstring(svg)
    except (ElementTree.ParseError, TypeError):
        failed = _patent_check("vector_drawing", "矢量制图格式", "fail", "输出不是可解析的 SVG 矢量图")
        return "fail", [failed]

    elements = list(root.iter())
    paths = [item for item in elements if _tag(item) == "path"]
    has_image = any(_tag(item) == "image" for item in elements)
    vector_ok = _tag(root) == "svg" and bool(paths) and not has_image
    checks.append(_patent_check(
        "vector_drawing", "矢量制图格式", "pass" if vector_ok else "fail",
        "检测到制图工具生成的 SVG 路径，未嵌入照片" if vector_ok else "未检测到有效矢量路径，或附图中嵌入了图片",
    ))

    view_box = [float(value) for value in re.findall(r"[-+]?\d+(?:\.\d+)?", root.attrib.get("viewBox", ""))]
    all_points = [point for path in paths for point in _path_points(path.attrib.get("d", ""))]
    geometry_uncertain = any(item.attrib.get("transform") for item in elements) or any(
        re.search(r"[AaCcQqSsTt]", path.attrib.get("d", "")) for path in paths
    )
    layout_ok = False
    a4_ratio_ok = False
    if len(view_box) == 4 and view_box[2] > 0 and view_box[3] > 0 and all_points:
        _, _, width, height = view_box
        a4_ratio_ok = height > width and abs(width / height - 210 / 297) <= 0.015
        left, right = width * 25 / 210, width - width * 15 / 210
        top, bottom = height * 25 / 297, height - height * 15 / 297
        layout_ok = a4_ratio_ok and all(left <= x <= right and top <= y <= bottom for x, y in all_points)
    layout_status = "review" if geometry_uncertain and a4_ratio_ok else "pass" if layout_ok else "fail"
    layout_detail = (
        "检测到当前分析器不能可靠测量的曲线或变换，需人工确认图形留白"
        if layout_status == "review"
        else "页面为 A4 纵向比例，图形位于规定留白范围内"
        if layout_status == "pass"
        else "页面比例或图形留白不符合 A4 纵向自动检查"
    )
    checks.append(_patent_check(
        "page_layout", "A4 版式与留白", layout_status, layout_detail,
        PAGE_RULE_BASIS,
    ))

    colors = {value.lower() for value in re.findall(r"(?:fill|stroke)\s*[:=]\s*[\"']?([^;\"'}\s]+)", svg, re.I)}
    allowed_colors = {"#000", "#000000", "black", "#fff", "#ffffff", "white", "none"}
    background_ok = any(
        _tag(item) == "rect" and item.attrib.get("fill", "").lower() in {"#fff", "#ffffff", "white"}
        for item in elements
    )
    black_white_ok = bool(colors) and colors <= allowed_colors and background_ok
    checks.append(_patent_check(
        "black_white", "黑线白底", "pass" if black_white_ok else "fail",
        "可见线条和文字为黑色，页面背景为白色" if black_white_ok else "检测到非黑色内容或缺少白色背景",
    ))

    stroke_widths = [float(value) for value in re.findall(r"stroke-width\s*:\s*(\d+(?:\.\d+)?)", svg, re.I)]
    line_ok = bool(stroke_widths) and min(stroke_widths) > 0 and max(stroke_widths) / min(stroke_widths) <= 4
    checks.append(_patent_check(
        "line_quality", "线型与线宽", "pass" if line_ok else "fail",
        "轮廓线与辅助线线宽为正且层级一致" if line_ok else "线宽缺失、无效或层级差异过大",
    ))

    framed = any(
        _tag(item) == "rect" and item.attrib.get("stroke", "none").lower() not in {"", "none"}
        for item in elements
    )
    checks.append(_patent_check(
        "unrelated_frame", "无关框线", "fail" if framed else "pass",
        "未检测到附图周围的无关描边框" if not framed else "检测到带描边的矩形框，请确认并移除无关框线",
    ))

    text_items = [("".join(item.itertext()).strip(), item) for item in elements if _tag(item) == "text"]
    figures = [(int(match.group(1)), item) for text, item in text_items if (match := re.fullmatch(r"图(\d+)", text))]
    figure_numbers = [number for number, _ in figures]
    path_bottom = max((point[1] for point in all_points), default=float("inf"))
    figure_position_ok = bool(figures) and all(float(item.attrib.get("y", 0)) > path_bottom for _, item in figures)
    numbering_ok = figure_numbers == list(range(1, len(figure_numbers) + 1)) and len(set(figure_numbers)) == len(figure_numbers)
    figure_ok = bool(figures) and numbering_ok and figure_position_ok
    checks.append(_patent_check(
        "figure_number", "附图编号与位置", "pass" if figure_ok else "fail",
        "图号连续且位于对应图形下方" if figure_ok else "未检测到连续的“图1、图2……”编号，或图号位置不在图形下方",
    ))

    annotations_ok = all(not re.search(r"[A-Za-z]", text) for text, _ in text_items)
    checks.append(_patent_check(
        "annotation_language", "注释与必要文字", "pass" if annotations_ok else "fail",
        "未检测到外文或明显超出允许集合的注释" if annotations_ok else "检测到外文注释；必要文字应使用中文并确认确有必要",
    ))

    page_numbers = [
        (int(text), item) for text, item in text_items
        if re.fullmatch(r"\d+", text) and item.attrib.get("class") == "p"
    ]
    page_ok = len(page_numbers) == 1 and page_numbers[0][0] >= 1 and float(page_numbers[0][1].attrib.get("y", 0)) > path_bottom
    checks.append(_patent_check(
        "page_number", "附图页码", "pass" if page_ok else "fail",
        "检测到与图号分离的阿拉伯数字页码" if page_ok else "未检测到与图号分离的连续阿拉伯数字页码",
    ))

    scaled_ok = line_ok and min(stroke_widths) * (2 / 3) >= 0.7
    checks.append(_patent_check(
        "scaled_legibility", "缩小后可辨识度（自动近似）", "pass" if scaled_ok else "fail",
        "按三分之二缩放估算，最细线条仍达到可辨识阈值" if scaled_ok else "按三分之二缩放估算，最细线条可能难以辨识",
    ))

    statuses = {item["status"] for item in checks}
    overall = "fail" if "fail" in statuses else "review" if "review" in statuses else "pass"
    return overall, checks
