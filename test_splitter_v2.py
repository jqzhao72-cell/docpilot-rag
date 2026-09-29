from rag.ingestion.splitter import split_text


text = """
Abstract

This study investigates triple-negative breast cancer.

Introduction

Triple-negative breast cancer is a highly aggressive subtype of breast cancer.
Paclitaxel resistance remains an important clinical challenge.

Materials and methods

The dataset was downloaded from GEO.
The Seurat package was used for preprocessing.

Results

The AKR1C3-positive cell subset increased after paclitaxel treatment.

Conclusion

These findings suggest that AKR1C3 may be associated with paclitaxel resistance.
"""


chunks = split_text(text)


for chunk in chunks:

    print("=" * 60)

    print(
        "Section:",
        chunk["metadata"]["section"]
    )

    print(
        "Chunk Index:",
        chunk["metadata"]["chunk_index"]
    )

    print()

    print(
        chunk["text"]
    )