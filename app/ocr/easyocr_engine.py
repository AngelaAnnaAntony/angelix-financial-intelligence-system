def extract_text(path, languages=None):
    import easyocr
    reader=easyocr.Reader(languages or ["en"], gpu=False)
    result=reader.readtext(str(path), detail=0)
    return "\n".join(result)
