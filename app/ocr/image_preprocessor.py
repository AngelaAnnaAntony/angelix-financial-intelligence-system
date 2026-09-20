def preprocess_image(path):
    from PIL import Image, ImageOps, ImageFilter
    img=Image.open(path).convert("L")
    img=ImageOps.autocontrast(img)
    return img.filter(ImageFilter.SHARPEN)
