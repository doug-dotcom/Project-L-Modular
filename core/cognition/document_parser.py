"""Parse untrusted uploads in a separate, time/memory bounded process."""
import base64
from io import BytesIO
import json
import sys


def parse(data, mime):
    if mime == 'application/pdf':
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ValueError('Password-protected PDFs are not supported.')
        if not 1 <= len(reader.pages) <= 30:
            raise ValueError('Choose a PDF with 1–30 pages.')
        pages = []
        for n, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ''
            pages.append({'page': n, 'text': text[:20000], 'truncated': len(text) > 20000,
                          'kind': 'pdf_text' if text.strip() else 'no_text'})
        return pages
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 16000000
    with Image.open(BytesIO(data)) as image:
        expected = {'image/png':'PNG', 'image/jpeg':'JPEG', 'image/webp':'WEBP'}
        if expected.get(mime) != image.format or image.width * image.height > 16000000:
            raise ValueError('Choose a supported image under 16 megapixels.')
        if getattr(image, 'n_frames', 1) != 1:
            raise ValueError('Choose a still image, not an animation.')
        image.verify()
    return [{'page': 1, 'text': '', 'truncated': False, 'kind': 'image'}]


if __name__ == '__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    try:
        request = json.loads(sys.stdin.buffer.read(8 * 1024 * 1024))
        pages = parse(base64.b64decode(request['data'], validate=True), request['mime'])
        print(json.dumps({'pages': pages}))
    except Exception:
        print(json.dumps({'error': 'This file could not be safely read. Use a text PDF (up to 30 pages) or a still JPEG, PNG or WebP.'}))
        sys.exit(1)
