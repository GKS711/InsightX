"""
Build INTRO video frames for InsightX.
Renders ~60 PNG frames @ 30fps × 2sec each phase using PIL.
Style: black bg / coral accent / serif typography / minimalist editorial
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math, os, shutil

W, H = 1920, 1080
FPS = 30

# Colors (matching v4 UI palette)
BLACK   = (13, 15, 14)
INK     = (26, 31, 28)
INK_3   = (138, 147, 142)
INK_4   = (176, 182, 179)
CORAL   = (214, 90, 58)
WHITE   = (255, 255, 255)
PAPER   = (250, 247, 242)

# Fonts (DejaVu - sandbox available)
FONT_DIR = "/usr/share/fonts/truetype/dejavu"
F_SERIF_BOLD = f"{FONT_DIR}/DejaVuSerif-Bold.ttf"
F_SERIF      = f"{FONT_DIR}/DejaVuSerif.ttf"
F_SANS_BOLD  = f"{FONT_DIR}/DejaVuSans-Bold.ttf"
F_SANS       = f"{FONT_DIR}/DejaVuSans.ttf"
F_MONO       = f"{FONT_DIR}/DejaVuSansMono-Bold.ttf"

OUT = Path("/sessions/kind-affectionate-pascal/mnt/Claude實作--InsightX/video/intro_frames")
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

def make_frame(t):
    """t in seconds. Returns PIL Image."""
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)

    # Phase A (0-1.0s): coral dot scales in from center, "i" letter appears
    # Phase B (1.0-1.8s): "insightx" wordmark slides in from right of dot
    # Phase C (1.8-3.5s): "AI · SHOP / CHANNEL INTELLIGENCE" mono kicker fades in,
    #                     then big serif tagline two lines
    # Phase D (3.5-5.0s): hold + bottom rule + footer mono text fade in, then everything starts to fade out near end

    # Top-left logo dot (always present after t=0.2)
    if t >= 0.2:
        # scale based on time
        scale = min(1.0, (t - 0.2) / 0.8)
        scale = 1 - (1 - scale) ** 3  # ease out cubic
        dot_size = int(50 * scale)
        cx, cy = 70, 70
        d.ellipse((cx - dot_size // 2, cy - dot_size // 2,
                   cx + dot_size // 2, cy + dot_size // 2), fill=CORAL)
        # "i" letter inside dot
        if scale > 0.6:
            try:
                f = ImageFont.truetype(F_SERIF_BOLD, int(28 * scale))
                bbox = d.textbbox((0, 0), "i", font=f)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                d.text((cx - tw // 2 - 1, cy - th // 2 - 6), "i", font=f, fill=WHITE)
            except: pass

    # "insightx" wordmark slides in from right of dot (1.0s onwards)
    if t >= 1.0:
        wm_progress = min(1.0, (t - 1.0) / 0.6)
        wm_progress = 1 - (1 - wm_progress) ** 3
        try:
            f = ImageFont.truetype(F_SERIF_BOLD, 32)
            wm_x = int(110 + (1 - wm_progress) * -20)
            opacity_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(opacity_overlay)
            alpha = int(255 * wm_progress)
            od.text((wm_x, 50), "insightx", font=f, fill=(*WHITE, alpha))
            img = Image.alpha_composite(img.convert("RGBA"), opacity_overlay).convert("RGB")
            d = ImageDraw.Draw(img)
        except: pass

    # Top-right version pill
    if t >= 1.5:
        pill_progress = min(1.0, (t - 1.5) / 0.4)
        try:
            f = ImageFont.truetype(F_MONO, 14)
            txt = "V 4 . 0 . 0   ·   L I V E"
            bbox = d.textbbox((0, 0), txt, font=f)
            tw = bbox[2] - bbox[0]
            alpha = int(180 * pill_progress)
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.text((W - tw - 80, 60), txt, font=f, fill=(*INK_3, alpha))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            d = ImageDraw.Draw(img)
        except: pass

    # Mono kicker: "AI · SHOP / CHANNEL INTELLIGENCE"
    if t >= 1.8:
        k_progress = min(1.0, (t - 1.8) / 0.4)
        try:
            f = ImageFont.truetype(F_MONO, 16)
            txt = "AI · SHOP / CHANNEL INTELLIGENCE"
            alpha = int(255 * k_progress)
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.text((90, 380), txt, font=f, fill=(*CORAL, alpha))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            d = ImageDraw.Draw(img)
        except: pass

    # Big tagline line 1: "Read every word"
    if t >= 2.2:
        l1_progress = min(1.0, (t - 2.2) / 0.5)
        l1_progress = 1 - (1 - l1_progress) ** 3
        try:
            f = ImageFont.truetype(F_SERIF_BOLD, 96)
            txt = "Read every word."
            alpha = int(255 * l1_progress)
            y_offset = int((1 - l1_progress) * 25)
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.text((90, 440 + y_offset), txt, font=f, fill=(*WHITE, alpha))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            d = ImageDraw.Draw(img)
        except: pass

    # Big tagline line 2: "Brief the boss."
    if t >= 2.6:
        l2_progress = min(1.0, (t - 2.6) / 0.5)
        l2_progress = 1 - (1 - l2_progress) ** 3
        try:
            f = ImageFont.truetype(F_SERIF_BOLD, 96)
            txt = "Brief the boss."
            alpha = int(255 * l2_progress)
            y_offset = int((1 - l2_progress) * 25)
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.text((90, 580 + y_offset), txt, font=f, fill=(*WHITE, alpha))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            d = ImageDraw.Draw(img)
        except: pass

    # Sub-text: "AI customer-feedback intelligence — Google Maps + YouTube"
    if t >= 3.2:
        s_progress = min(1.0, (t - 3.2) / 0.5)
        try:
            f = ImageFont.truetype(F_SANS, 22)
            txt = "AI customer-feedback intelligence — Google Maps + YouTube"
            alpha = int(180 * s_progress)
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.text((90, 760), txt, font=f, fill=(*INK_4, alpha))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            d = ImageDraw.Draw(img)
        except: pass

    # Bottom rule + footer mono
    if t >= 3.6:
        f_progress = min(1.0, (t - 3.6) / 0.4)
        line_w = int((W - 180) * f_progress)
        d.rectangle((90, 950, 90 + line_w, 953), fill=(68, 77, 73))
        if f_progress > 0.7:
            try:
                f = ImageFont.truetype(F_MONO, 14)
                d.text((90, 980), "INSIGHTX  ·  AI ADVISOR REPORT  ·  MIT", font=f, fill=INK_4)
                txt2 = "github.com/GKS711/InsightX"
                bbox = d.textbbox((0, 0), txt2, font=f)
                tw2 = bbox[2] - bbox[0]
                d.text((W - tw2 - 90, 980), txt2, font=f, fill=INK_4)
            except: pass

    # Final fade out (4.6-5.0s)
    if t >= 4.6:
        fade = (t - 4.6) / 0.4
        fade = min(1.0, fade)
        # darken everything
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, int(255 * fade)))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    return img


def main():
    duration = 5.0  # seconds
    n_frames = int(duration * FPS)
    print(f"Rendering {n_frames} frames at {FPS}fps × {duration}s ...")
    for i in range(n_frames):
        t = i / FPS
        img = make_frame(t)
        img.save(OUT / f"f{i:04d}.png", optimize=False, compress_level=1)
        if i % 30 == 0:
            print(f"  frame {i}/{n_frames} (t={t:.2f}s)")
    print(f"✓ Done. Frames in {OUT}")

if __name__ == "__main__":
    main()
