def chunk_page(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    chunks, buf, n = [], [], 0
    for line in text.split("\n"):
        if n + len(line) > size and buf:
            chunks.append("\n".join(buf).strip())
            keep, c = [], 0                       
            for prev in reversed(buf):
                if c >= overlap:
                    break
                keep.insert(0, prev)
                c += len(prev) + 1
            buf, n = keep, c
        buf.append(line)
        n += len(line) + 1
    if buf:
        chunks.append("\n".join(buf).strip())
    return [c for c in chunks if c]