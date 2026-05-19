"""
v2 — Reduced to 6 high-value segments per Codex feedback:
- Caption moved to top-left as 'section label' (not lower-third), to make room for SRT
- Each segment 7 seconds (was 6) for slower pacing on fewer cuts
- Only 6 demo screenshots: landing, hero, themes, swot, week-plan, ai-advisor
"""
import subprocess, shutil
from pathlib import Path

ROOT = Path("/sessions/kind-affectionate-pascal/mnt/Claude實作--InsightX/video")
SRC = ROOT.parent / "docs" / "screenshots" / "v4"
OUT = ROOT / "demo_segments_v2"
if OUT.exists(): shutil.rmtree(OUT)
OUT.mkdir(parents=True)

W, H = 1920, 1080
FPS = 24
DUR = 7  # slower pacing

# 6 chosen segments aligned with Codex narrative arc
SEGMENTS = [
    ("01-landing.png",
     "01 / 06",
     "PASTE A URL",
     "Pick a platform. Paste a URL. Press start.",
     "zoom_in_center"),
    ("04-hero.png",
     "02 / 06",
     "AT-A-GLANCE",
     "Rating, 90-day trend, sentiment — one screen.",
     "zoom_in_left"),
    ("05-themes.png",
     "03 / 06",
     "WHAT THEY SAY",
     "Top positive + negative themes, ranked.",
     "pan_down"),
    ("06-swot.png",
     "04 / 06",
     "STRATEGIC POSTURE",
     "SWOT, every claim cites the original review.",
     "zoom_in_center"),
    ("08-week-plan.png",
     "05 / 06",
     "WHAT TO SHIP",
     "7-day plan: tasks, owners, expected wins.",
     "zoom_in_center"),
    ("10-ai-advisor.png",
     "06 / 06",
     "ASK YOUR DATA",
     "An AI advisor that reads only your shop.",
     "zoom_in_center"),
]


def build_kenburns_filter(motion, dur_frames):
    if motion == "zoom_in_center":
        return (f"zoompan=z='1.04+0.14*on/{dur_frames}':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={dur_frames}:s={W}x{H}:fps={FPS}")
    elif motion == "zoom_in_left":
        return (f"zoompan=z='1.04+0.14*on/{dur_frames}':"
                f"x='iw*0.30':y='ih/2-(ih/zoom/2)':"
                f"d={dur_frames}:s={W}x{H}:fps={FPS}")
    elif motion == "pan_down":
        return (f"zoompan=z='1.10':"
                f"x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*on/{dur_frames}':"
                f"d={dur_frames}:s={W}x{H}:fps={FPS}")
    return f"scale={W}:{H}"


def build_caption_top(num_label, kicker, line1, idx):
    """Section-label style caption: small box top-left + index top-right."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Top-left band: thin pill background
    pad_x = 70
    pad_y = 50
    f_kicker = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 22)
    f_l1 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 38)
    bbox_k = d.textbbox((0, 0), kicker, font=f_kicker)
    bbox_l = d.textbbox((0, 0), line1, font=f_l1)
    box_w = max(bbox_k[2], bbox_l[2]) + 56
    box_h = 86
    box_x = pad_x
    box_y = pad_y
    box_h = 120
    # Coral left rule
    d.rectangle((box_x, box_y, box_x + 6, box_y + box_h), fill=(214, 90, 58, 255))
    # Semi-transparent dark backdrop
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((box_x + 6, box_y, box_x + box_w + 36, box_y + box_h), fill=(13, 15, 14, 200))
    img = Image.alpha_composite(img, overlay)
    d = ImageDraw.Draw(img)
    # Kicker (mono coral) and Line1 (serif white)
    d.text((box_x + 32, box_y + 22), kicker, font=f_kicker, fill=(214, 90, 58, 255))
    d.text((box_x + 32, box_y + 56), line1, font=f_l1, fill=(255, 255, 255, 255))

    # Top-right segment number
    f_num = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 18)
    bbox = d.textbbox((0, 0), num_label, font=f_num)
    d.text((W - bbox[2] - pad_x, pad_y + 8), num_label, font=f_num, fill=(176, 182, 179, 230))

    return img


def main():
    for idx, (filename, num_label, kicker, line1, motion) in enumerate(SEGMENTS, start=1):
        src_path = SRC / filename
        out_path = OUT / f"seg_{idx:02d}.mp4"
        cap_path = OUT / f"cap_{idx:02d}.png"
        print(f"[{idx}/6] {filename} ({motion})")

        cap_img = build_caption_top(num_label, kicker, line1, idx)
        cap_img.save(cap_path)

        n_frames = DUR * FPS  # 168
        kb = build_kenburns_filter(motion, n_frames)
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-framerate", str(FPS), "-t", str(DUR), "-i", str(src_path),
            "-loop", "1", "-framerate", str(FPS), "-t", str(DUR), "-i", str(cap_path),
            "-filter_complex",
            f"[0:v]scale=2560:1422,{kb},setsar=1[bg];"
            f"[1:v]format=rgba,fade=in:0:12,fade=out:{n_frames - 12}:12[cap];"
            f"[bg][cap]overlay=0:0,format=yuv420p[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "fastdecode", "-crf", "26",
            "-r", str(FPS), "-t", str(DUR),
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr[-400:]}")
        else:
            print(f"  ✓ {out_path.stat().st_size // 1024}KB")


if __name__ == "__main__":
    main()
