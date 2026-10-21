
import sys
from pathlib import Path

# Ensure project root is in sys.path when script is executed directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.retrieval.retriever import retrieve_chunks


PRINCIPAL_ID = "employee-001"

question = (
    "What permission do I need to access "
    "the production database?"
)


def main():
    results = retrieve_chunks(
        question=question,
        principal_id=PRINCIPAL_ID,
        top_k=5,
    )

    if not results:
        print("No authorized chunks found.")
        return

    for rank, result in enumerate(results, start=1):
        print(f"\nRank: {rank}")
        print("Document ID:", result["document_id"])
        print("Content:", result["content"])
        print("Metadata:", result["metadata"])
        print(f"Cosine distance: {result['distance']:.4f}")


if __name__ == "__main__":
    main()
