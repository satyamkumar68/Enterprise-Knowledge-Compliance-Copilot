
import sys
from pathlib import Path

# Ensure project root is in sys.path when script is executed directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.generation.answer import generate_answer


PRINCIPAL_ID = "employee-001"

QUESTIONS = [
    "What permission do I need to access the production database?",
    "How often must production database passwords be rotated?",
]


def main():
    for question in QUESTIONS:
        print("\n" + "=" * 65)
        print("QUESTION:", question)

        result = generate_answer(
            question=question,
            principal_id=PRINCIPAL_ID,
        )

        print("\nANSWER:")
        print(result["answer"])

        if result.get("clean_answer"):
            print("\nCLEAN ANSWER (NO TAGS):")
            print(result["clean_answer"])

        if result.get("confidence_score") is not None:
            print(f"\nCONFIDENCE SCORE: {result['confidence_score']:.2%} (avg distance: {result.get('average_distance')})")

        print("\nABSTAINED:", result["abstained"])
        print("SOURCES:")

        for source in result["sources"]:
            print(
                f"[Source {source['source_id']}] "
                f"{source['filename']} | "
                f"Document ID: {source['document_id']} | "
                f"Chunk: {source['chunk_index']}"
            )
            print("Content:", source["content"])


if __name__ == "__main__":
    main()

