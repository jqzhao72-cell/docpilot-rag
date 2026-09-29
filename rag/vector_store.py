import chromadb
import uuid



class ChromaVectorStore:


    def __init__(self):

        self.client = chromadb.PersistentClient(
            path="./chroma_db"
        )


        self.collection = self.client.get_or_create_collection(

            name="company_docs",

            metadata={
                "hnsw:space":"cosine"
            }
        )



    def add_documents(
        self,
        chunks,
        embeddings,
        metadatas
    ):


        self.collection.add(

            ids=[
                str(uuid.uuid4())
                for _ in chunks
            ],


            documents=chunks,


            embeddings=[
                e.tolist()
                for e in embeddings
            ],


            metadatas=metadatas

        )


        print(
            f"成功保存 {len(chunks)} 个文本块"
        )