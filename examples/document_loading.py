from rag.ingestion.loader import load_document



file_path = "data/documents/test.txt"



text = load_document(
    file_path
)


print("================")
print("读取结果")
print("================")


print(text)