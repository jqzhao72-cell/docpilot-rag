from rag.ingestion.loader import load_document
from rag.ingestion.splitter import split_text



file_path = "data/documents/test.txt"



text = load_document(
    file_path
)



chunks = split_text(
    text
)



print("================")
print("Chunk数量")
print("================")


print(
    len(chunks)
)



for i, chunk in enumerate(chunks):

    print("----------------")

    print(
        f"Chunk {i}"
    )

    print(chunk)