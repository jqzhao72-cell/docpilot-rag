from pathlib import Path

from pypdf import PdfReader
from docx import Document



def load_txt(file_path):

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as f:

        return f.read()



def load_pdf(file_path):

    reader = PdfReader(file_path)

    text = ""

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:

            text += page_text + "\n"


    return text



def load_docx(file_path):

    doc = Document(file_path)

    text = ""

    for paragraph in doc.paragraphs:

        text += paragraph.text + "\n"


    return text



def load_document(file_path):

    """
    根据文件类型自动选择加载方式
    """

    suffix = Path(file_path).suffix.lower()


    if suffix == ".txt":

        return load_txt(file_path)


    elif suffix == ".pdf":

        return load_pdf(file_path)


    elif suffix == ".docx":

        return load_docx(file_path)


    else:

        raise ValueError(
            f"不支持的文件格式: {suffix}"
        )