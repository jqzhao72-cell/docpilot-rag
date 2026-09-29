import fitz

from .schemas import TableData, TextBlock


def find_table_caption(
    table_bbox,
    blocks: list[TextBlock]
) -> str:
    """
    根据表格的位置，寻找表格上方最近的 Table Caption。

    参数：
        table_bbox:
            表格坐标，格式一般为：
            (x0, y0, x1, y1)

        blocks:
            当前页面所有 TextBlock

    返回：
        str:
            找到的表格标题
            如果没有找到，则返回空字符串
    """

    tx0, ty0, tx1, ty1 = table_bbox

    candidates = []

    for block in blocks:

        # 只看之前 Layout 阶段
        # 已经识别成 table_caption 的文本块
        if block.block_type != "table_caption":
            continue

        # 计算 Caption 底部
        # 到表格顶部之间的垂直距离
        distance = ty0 - block.y1

        # Caption必须在表格上方，
        # 而且距离不能太远
        if 0 <= distance < 120:

            candidates.append(
                (
                    distance,
                    block.text
                )
            )

    # 一个候选都没有
    if not candidates:
        return ""

    # 按距离从小到大排序
    candidates.sort(
        key=lambda item: item[0]
    )

    # 返回距离表格最近的 Caption
    return candidates[0][1]


def clean_table_rows(
    rows
):
    """
    对 PyMuPDF 提取出来的表格进行简单清洗。

    主要做：
    1. None 保留
    2. 字符串去掉首尾空格
    3. 空字符串统一处理
    """

    cleaned_rows = []

    for row in rows:

        cleaned_row = []

        for cell in row:

            if cell is None:
                cleaned_row.append(
                    None
                )

                continue

            cell_text = str(
                cell
            ).strip()

            cleaned_row.append(
                cell_text
            )

        cleaned_rows.append(
            cleaned_row
        )

    return cleaned_rows


def extract_tables(
    page: fitz.Page,
    page_number: int,
    blocks: list[TextBlock]
) -> list[TableData]:
    """
    从一个PDF页面中检测并提取表格。

    参数：
        page:
            PyMuPDF Page对象

        page_number:
            当前页码

        blocks:
            当前页面已经解析出的 TextBlock

    返回：
        List[TableData]
    """

    tables_result = []

    try:

        table_finder = (
            page.find_tables()
        )

    except Exception as e:

        print(
            f"[Table] 第 {page_number} 页 "
            f"表格检测失败: {e}"
        )

        return tables_result


    # PyMuPDF检测到的所有表格
    detected_tables = (
        table_finder.tables
    )


    for table_id, table in enumerate(
        detected_tables
    ):

        # ==========================================
        # 1. 获取表格bbox
        # ==========================================

        bbox = [
            float(value)
            for value in table.bbox
        ]


        # ==========================================
        # 2. 提取行列数据
        # ==========================================

        try:

            rows = table.extract()

        except Exception as e:

            print(
                f"[Table] 第 {page_number} 页 "
                f"表格 {table_id} 提取失败: {e}"
            )

            rows = []


        # ==========================================
        # 3. 清洗表格内容
        # ==========================================

        rows = clean_table_rows(
            rows
        )


        # ==========================================
        # 4. 找表格Caption
        # ==========================================

        caption = find_table_caption(
            table_bbox=table.bbox,
            blocks=blocks
        )


        # ==========================================
        # 5. 封装TableData
        # ==========================================

        table_data = TableData(
            table_id=table_id,

            page=page_number,

            bbox=bbox,

            rows=rows,

            caption=caption
        )


        tables_result.append(
            table_data
        )


    return tables_result