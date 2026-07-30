import re

from langchain_text_splitters import RecursiveCharacterTextSplitter



def split_by_section(text):
    """
    按章节和小标题切分
    """


    pattern = r"(第[一二三四五六七八九十]+章.*|\d+\.\s.*)"


    parts = re.split(
        pattern,
        text
    )


    sections = []


    current_title = ""


    for part in parts:

        part = part.strip()


        if not part:
            continue


        # 如果是标题

        if re.match(
            pattern,
            part
        ):

            current_title = part


        else:

            sections.append(
                {
                    "title": current_title,

                    "content": part
                }
            )


    return sections





def split_text(text):


    sections = split_by_section(
        text
    )


    splitter = RecursiveCharacterTextSplitter(

        chunk_size=300,

        chunk_overlap=50,

        separators=[
            "\n\n",
            "\n",
            "。",
            "！",
            "？"
        ]
    )


    final_chunks = []


    for section in sections:


        content = (

            section["title"]

            +

            "\n"

            +

            section["content"]

        )


        chunks = splitter.split_text(
            content
        )


        final_chunks.extend(
            chunks
        )


    return final_chunks