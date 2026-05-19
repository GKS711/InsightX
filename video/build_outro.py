"""Build OUTRO video frames. Style mirrors intro for bookend feel."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import shutil

W, H = 1920, 1080
FPS = 30

BLACK   = (13, 15, 14)
INK_3   = (138, 147, 142)
INK_4   = (176, 182, 179)
CORAL   = (214, 90, 58)
WHITE   = (255, 255, 255)

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
F_SERIF_BOLD = f"{FONT_DIR}/DejaVuSerif-Bold.ttf"
F_SANS = f"{FONT_DIR}/DejaVuSans.ttf"
F_MONO = f"{FONT_DIR}/DejaVuSansMono-Bold.ttf"

OUT = Path("/sessions/kind-affectionate-pascal/mnt/Claude實作--InsightX/video/outro_frames")
if OUT.exists(): shutil.rmtree(OUT)
OUT.mkdir(parents=True)

def make_frame(t):
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)

    # Persistent top mono header (always visible after t=0.2)
    if t >= 0.2:
        ph = min(1.0, (t - 0.2) / 0.4)
        try:
            f = ImageFont.truetype(F_MONO, 14)
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.text((90, 60), "INSIGHTX  V 4 . 0 . 0", font=f, fill=(*INK_4, int(180 * ph)))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            d = ImageDraw.Draw(img)
        except: pass

    # Big "Try it now." (0.6s onwards) — 2-stage: scale-in + hold
    if t >= 0.6:
        p1 = min(1.0, (t - 0.6) / 0.5)
        p1 = 1 - (1 - p1) ** 3
        try:
            f = ImageFont.truetype(F_SERIF_BOLD, 128)
            txt = "Try it now."
            alpha = int(255 * p1)
            y_offset = int((1 - p1) * 30)
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.text((90, 280 + y_offset), txt, font=f, fill=(*WHITE, alpha))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            d = ImageDraw.Draw(img)
        except: pass

    # Sub-tagline
    if t >= 1.5:
        p2 = min(1.0, (t - 1.5) / 0.4)
        try:
            f = ImageFont.truetype(F_SANS, 24)
            txt = "Open-source. MIT. No signup. Run with sample data — you'll see a brief in 30s."
            alpha = int(180 * p2)
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.text((90, 480), txt, font=f, fill=(*INK_4, alpha))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            d = ImageDraw.Draw(img)
        except: pass

    # CTA pill (coral background) with github URL
    if t >= 2.2:
        p3 = min(1.0, (t - 2.2) / 0.4)
        try:
            f = ImageFont.truetype(F_MONO, 22)
            txt = "github.com/GKS711/InsightX"
            bbox = d.textbbox((0, 0), txt, font=f)
            tw = bbox[2] - bbox[0]
            pill_w = tw + 80
            pill_h = 70
            pill_x = 90
            pill_y = 600
            # animate width grow
            grown = int(pill_w * p3)
            d.rounded_rectangle((pill_x, pill_y, pill_x + grown, pill_y + pill_h), radius=4, fill=CORAL)
            if p3 > 0.7:
                ta = int(255 * (p3 - 0.7) / 0.3)
                overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                od = ImageDraw.Draw(overlay)
                od.text((pill_x + 40, pill_y + 18), txt, font=f, fill=(*WHITE, ta))
                img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
                d = ImageDraw.Draw(img)
        except: pass

    # Side meta after CTA
    if t >= 2.8:
        p4 = min(1.0, (t - 2.8) / 0.4)
        try:
            f = ImageFont.truetype(F_SANS, 20)
            txt = "MIT License  ·  Zero browser dependency  ·  Dual platform"
            alpha = int(180 * p4)
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.text((780, 618), txt, font=f, fill=(*INK_3, alpha))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            d = ImageDraw.Draw(img)
        except: pass

    # Bottom rule + footer mono
    if t >= 3.4:
        p5 = min(1.0, (t - 3.4) / 0.4)
        line_w = int((W - 180) * p5)
        d.rectangle((90, 950, 90 + line_w, 953), fill=(68, 77, 73))
        if p5 > 0.7:
            try:
                f = ImageFont.truetype(F_MONO, 14)
                d.text((90, 980), "InsightX  ·  Built with FastAPI + React 18 + Gemini  ·  Audit-friendly, evidence-backed",
                       font=f, fill=INK_4)
            except: pass

    # Final hold (4.0-5.0s) — slight breathing glow on CTA pill
    if t >= 4.0 and t < 4.5:
        glow = (t - 4.0) / 0.5
        # subtle coral glow underneath CTA
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle((85, 595, 85 + 600, 675), radius=6,
                             fill=(*CORAL, int(40 * glow)))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    return img


def main():
    duration = 5.0
    n = int(duration * FPS)
    print(f"Rendering outro {n} frames @ {FPS}fps × {duration}s")
    for i in range(n):
        t = i / FPS
        img = make_frame(t)
        img.save(OUT / f"f{i:04d}.png", optimize=False, compress_level=1)
        if i % 30 == 0: print(f"  frame {i}/{n} (t={t:.2f}s)")
    print(f"✓ Done. Frames in {OUT}")

if __name__ == "__main__":
    main()
