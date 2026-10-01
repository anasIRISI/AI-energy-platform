from pathlib import Path
from PIL import Image, ImageDraw

pages = sorted(Path(r"C:\Users\hp\Documents\AI-energy-platform\rapport_qa_pages").glob("page-*.png"))
out = Path(r"C:\Users\hp\Documents\AI-energy-platform\rapport_qa_sheets")
out.mkdir(exist_ok=True)

for start in range(0, len(pages), 4):
    sheet = Image.new("RGB", (1700, 2250), "#d9d9d9")
    draw = ImageDraw.Draw(sheet)
    for offset, page in enumerate(pages[start:start + 4]):
        image = Image.open(page).convert("RGB")
        image.thumbnail((780, 1040))
        x = 35 + (offset % 2) * 835
        y = 45 + (offset // 2) * 1100
        sheet.paste(image, (x, y + 30))
        draw.text((x, y), f"Page {start + offset + 1}", fill="black")
    sheet.save(out / f"sheet-{start // 4 + 1:02d}.png")
