from pathlib import Path

from PIL import Image, ImageDraw


directory = Path(r"C:\Users\hp\Documents\AI-energy-platform\chapitre_ia_work\final-ia-detail-pages")
pages = sorted(directory.glob("page-*.png"))
for sheet in directory.glob("sheet-*.png"):
    sheet.unlink()

for start in range(0, len(pages), 6):
    images = [Image.open(page).convert("RGB") for page in pages[start : start + 6]]
    width, height = images[0].size
    output = Image.new("RGB", (width * 2, height * 3), (230, 230, 230))
    draw = ImageDraw.Draw(output)
    for index, image in enumerate(images):
        x = (index % 2) * width
        y = (index // 2) * height
        output.paste(image, (x, y))
        draw.rectangle((x + 8, y + 8, x + 150, y + 46), fill=(255, 255, 255))
        draw.text((x + 18, y + 18), f"Page {start + index + 1}", fill=(0, 0, 0))
    output.save(directory / f"sheet-{start // 6 + 1}.png")
