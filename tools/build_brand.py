"""Export a simple original vector server icon to HA brand PNG sizes."""
from pathlib import Path
from PIL import Image, ImageDraw

brand = Path(__file__).resolve().parents[1] / "custom_components/infra_vcenter/brand"
brand.mkdir(exist_ok=True)
# SVG source keeps this small UI mark editable without a bitmap dependency.
svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">',
       '<rect x="8" y="8" width="240" height="240" rx="52" fill="#102b46"/>',
       '<path d="M128 178v32M62 210h132" fill="none" stroke="#38c8ed" stroke-width="10" stroke-linecap="round"/>']
for y in (40, 88, 136):
    svg += [f'<rect x="48" y="{y}" width="160" height="36" rx="9" fill="#e9f6fc"/>',
            f'<circle cx="68" cy="{y+18}" r="5" fill="#21b59a"/>',
            f'<path d="M92 {y+18}h50M160 {y+18}h24" stroke="#3a6684" stroke-width="5" stroke-linecap="round"/>']
for x in (62, 128, 194):
    svg.append(f'<circle cx="{x}" cy="210" r="9" fill="#38c8ed"/>')
svg.append('</svg>')
(brand / "icon.svg").write_text("\n".join(svg), encoding="utf-8")

scale = 4
image = Image.new("RGBA", (256*scale, 256*scale))
draw = ImageDraw.Draw(image)
def box(coords):
    return tuple(round(v * scale) for v in coords)
draw.rounded_rectangle(box((8, 8, 248, 248)), radius=52*scale, fill="#102b46")
draw.line([box((128, 178)), box((128, 210))], fill="#38c8ed", width=10*scale)
draw.line([box((62, 210)), box((194, 210))], fill="#38c8ed", width=10*scale)
for y in (40, 88, 136):
    draw.rounded_rectangle(box((48, y, 208, y+36)), radius=9*scale, fill="#e9f6fc")
    draw.ellipse(box((63, y+13, 73, y+23)), fill="#21b59a")
    for x1, x2 in ((92, 142), (160, 184)):
        draw.rounded_rectangle(box((x1, y+15.5, x2, y+20.5)), radius=2.5*scale, fill="#3a6684")
for x in (62, 128, 194):
    draw.ellipse(box((x-9, 201, x+9, 219)), fill="#38c8ed")
for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
    image.resize((size, size), Image.Resampling.LANCZOS).save(brand / name)
print(f"Brand icons exported to {brand}")
