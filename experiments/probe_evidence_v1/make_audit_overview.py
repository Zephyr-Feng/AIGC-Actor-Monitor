from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).parent / "visual_audit"
sheets = sorted((root / "qualitative_contact_sheets").glob("*.png"))
thumb_size = (400, 152)
columns = 5
rows = (len(sheets) + columns - 1) // columns
canvas = Image.new("RGB", (columns * thumb_size[0], rows * (thumb_size[1] + 24)), "white")
draw = ImageDraw.Draw(canvas)
for index, path in enumerate(sheets):
    image = Image.open(path).convert("RGB")
    image.thumbnail(thumb_size)
    x = (index % columns) * thumb_size[0]
    y = (index // columns) * (thumb_size[1] + 24)
    canvas.paste(image, (x, y + 24))
    draw.text((x + 4, y + 4), path.stem, fill="black")
canvas.save(root / "overview_30.png")

failures = sorted((root / "probe_failures").glob("*_contact_sheet.png"))
failure_canvas = Image.new("RGB", (1320, 1000), "white")
failure_draw = ImageDraw.Draw(failure_canvas)
for index, path in enumerate(failures):
    image = Image.open(path).convert("RGB")
    image.thumbnail((650, 470))
    x = (index % 2) * 660
    y = (index // 2) * 500
    failure_draw.text((x + 4, y + 4), path.stem, fill="black")
    failure_canvas.paste(image, (x, y + 24))
failure_canvas.save(root / "overview_probe_errors.png")
