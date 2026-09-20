from pathlib import Path


DEFAULT_TESSERACT_PATHS = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)


def _find_tesseract():
    """
    Locate the Tesseract executable.

    ANGELIX first checks the standard Windows installation paths.
    If Tesseract is available through PATH, pytesseract can locate it
    automatically.
    """
    for executable in DEFAULT_TESSERACT_PATHS:
        if executable.is_file():
            return str(executable)

    return None


def extract_text(path, tesseract_cmd=None):
    """
    Extract text from an image using Tesseract OCR.

    Parameters
    ----------
    path : str or pathlib.Path
        Image file to process.

    tesseract_cmd : str, optional
        Explicit path to the Tesseract executable.

    Returns
    -------
    str
        OCR-extracted text.
    """
    image_path = Path(path)

    if not image_path.exists():
        raise FileNotFoundError(
            f"OCR image file not found: {image_path}"
        )

    if not image_path.is_file():
        raise ValueError(
            f"OCR path is not a file: {image_path}"
        )

    try:
        import pytesseract

        executable = tesseract_cmd or _find_tesseract()

        if executable:
            pytesseract.pytesseract.tesseract_cmd = executable

        return pytesseract.image_to_string(str(image_path))

    except ImportError as exc:
        raise RuntimeError(
            "pytesseract is not installed in the active Python environment."
        ) from exc

    except Exception as exc:
        raise RuntimeError(
            f"Tesseract OCR failed: {exc}"
        ) from exc