import re


def _clean_heading(heading: str) -> str:
    """Strip markdown hashes and whitespace from heading."""
    return re.sub(r"^#{1,6}\s+", "", heading).strip()


def _format_context_header(document_title: str | None, heading: str | None) -> str:
    """Format contextual header prepended to chunk."""
    clean_h = _clean_heading(heading) if heading else ""
    if document_title and clean_h:
        return f"[Document: {document_title} | Section: {clean_h}]\n"
    elif document_title:
        return f"[Document: {document_title}]\n"
    elif heading:
        return f"{heading}\n"
    return ""


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 75,
    document_title: str | None = None,
) -> list[str]:
    """Chunk text into sliding-window segments preserving boundaries, headings, and context headers."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap must be non-negative and smaller than chunk_size."
        )

    if not text or not text.strip():
        return []

    chunks: list[str] = []
    paragraphs = re.split(r"\n\s*\n", text.strip())

    current_heading = ""
    current_sentences: list[str] = []

    def flush_chunk(heading: str, sentences: list[str]) -> None:
        if not sentences:
            return
        header = _format_context_header(document_title, heading)
        chunk_str = f"{header}{' '.join(sentences)}".strip()
        if chunk_str and (not chunks or chunks[-1] != chunk_str):
            chunks.append(chunk_str)

    def compute_overlap_sentences(sentences: list[str], max_overlap: int) -> list[str]:
        if max_overlap <= 0 or not sentences:
            return []
        overlap_sentences: list[str] = []
        overlap_len = 0
        for sent in reversed(sentences):
            added = len(sent) + (1 if overlap_sentences else 0)
            if overlap_len + added <= max_overlap:
                overlap_sentences.insert(0, sent)
                overlap_len += added
            else:
                # If even the last sentence exceeds max_overlap, take trailing words
                if not overlap_sentences:
                    words = sent.split()
                    tail_words: list[str] = []
                    tail_len = 0
                    for w in reversed(words):
                        w_len = len(w) + (1 if tail_words else 0)
                        if tail_len + w_len <= max_overlap:
                            tail_words.insert(0, w)
                            tail_len += w_len
                        else:
                            break
                    if tail_words:
                        overlap_sentences = [" ".join(tail_words)]
                break
        return overlap_sentences

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if re.match(r"^#{1,6}\s+", paragraph):
            lines = paragraph.splitlines()
            first_line = lines[0].strip()
            # When section heading changes, flush existing chunk under previous heading
            if current_sentences:
                flush_chunk(current_heading, current_sentences)
                current_sentences = []
            current_heading = first_line

            remaining = "\n".join(lines[1:]).strip()
            if not remaining:
                continue
            paragraph = remaining

        header = _format_context_header(document_title, current_heading)
        effective_limit = max(50, chunk_size - len(header))

        # Split paragraph at sentence boundaries
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", paragraph)
            if s.strip()
        ]

        for sentence in sentences:
            # Handle exceptionally long sentences that exceed effective_limit
            while len(sentence) > effective_limit:
                split_at = effective_limit
                space_pos = sentence[:split_at].rfind(" ")
                if space_pos > 20:
                    split_at = space_pos
                part = sentence[:split_at].strip()
                sentence = sentence[split_at:].strip()

                if part:
                    current_sentences.append(part)
                    flush_chunk(current_heading, current_sentences)
                    current_sentences = compute_overlap_sentences(
                        current_sentences, overlap
                    )

            added_len = len(sentence) + (1 if current_sentences else 0)
            current_total = (
                len(header)
                + sum(len(s) for s in current_sentences)
                + (len(current_sentences) - 1 if current_sentences else 0)
            )

            if current_total + added_len <= chunk_size:
                current_sentences.append(sentence)
            else:
                if current_sentences:
                    flush_chunk(current_heading, current_sentences)
                    current_sentences = compute_overlap_sentences(
                        current_sentences, overlap
                    )
                current_sentences.append(sentence)

    if current_sentences:
        flush_chunk(current_heading, current_sentences)

    return chunks




