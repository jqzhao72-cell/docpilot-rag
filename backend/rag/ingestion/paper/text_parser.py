import re
#按规则匹配和替换字符串”
import fitz
#导入读取pdf

def clean_text(text: str) -> str:
    """
    对PDF提取出来的文本做基础清洗。

    主要处理：
    1. soft hyphen
    2. 多余空格
    3. 多余Tab
    4. 连续过多换行
    """

    if not text:
        return ""

    # 删除PDF中常见的soft hyphen
    text = text.replace("\u00ad", "")

    # 连续多个空格或Tab统一成一个空格
    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    # 连续3个及以上换行，压缩成2个换行
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


def extract_raw_text(
    page: fitz.Page
) -> str:
    """
    提取单个PDF页面的原始文本。

    参数：
        page:
            PyMuPDF中的Page对象

    返回：
        str:
            清洗后的页面文本
    """

    raw_text = page.get_text(
        "text"
    )

    cleaned_text = clean_text(
        raw_text
    )

    return cleaned_text