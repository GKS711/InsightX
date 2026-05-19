"""
Build demo segments from v4 screenshots with Ken Burns motion + English captions.
Each screenshot -> 6 sec segment with smooth zoom/pan + caption overlay.
Output: video/demo_segments/seg_NN.mp4
"""
import subprocess, shutil, os
from pathlib import Path

ROOT = Path("/sessions/kind-affectionate-pascal/mnt/Claude實作--InsightX/video")
SRC = ROOT.parent / "docs" / "screenshots" / "v4"
OUT = ROOT / "demo_segments"
if OUT.exists(): shutil.rmtree(OUT)
OUT.mkdir(parents=True)

W, H = 1280, 720
FPS = 24
DUR = 6  # seconds per segment
N_FRAMES = DUR * FPS  # 180

# (filename, caption_text_2_lines, motion_type, kicker)
# motion: 'zoom_in', 'zoom_out', 'pan_left', 'pan_right', 'pan_down', 'pan_up'
SEGMENTS = [
    ("01-landing.png",
     ("§01  THE FRONT DOOR", "Paste a URL. Hit start.", "zoom_in_center"),
     "Landing — pick a platform, paste a URL, get an audit-grade report."),
    ("02-platforms.png",
     ("§02  TWO SOURCES", "Google Maps + YouTube.", "zoom_out"),
     "Two sources, one advisor. Restaurants and creators alike."),
    ("03-analyzing.png",
     ("§03  PIPELINE LIVE", "Scrape → analyze → generate.", "pan_down"),
     "Real-time SSE: each step streams to the UI as it happens."),
    ("04-hero.png",
     ("§04  HERO  ·  AT-A-GLANCE", "Rating, trend, sentiment — instantly.", "zoom_in_left"),
     "Current rating, 90-day trend, sentiment donut — all above the fold."),
    ("05-themes.png",
     ("§05  WHAT THEY'RE SAYING", "Top positive + negative themes.", "pan_down"),
     "What customers actually talk about — not what you assumed."),
    ("06-swot.png",
     ("§06  SWOT  ·  EVIDENCE-BACKED", "Each conclusion cites the source.", "zoom_in_center"),
     "SWOT four-quadrant — every claim links back to the original review."),
    ("07-reviews.png",
     ("§07  RAW MATERIAL", "Up to 50 sample reviews on view.", "pan_down"),
     "Original reviews stay visible — never hidden behind the AI."),
    ("08-week-plan.png",
     ("§08  TURN INSIGHT INTO ACTION", "7-day plan, owners, expected wins.", "zoom_in_center"),
     "Five generators take you from insight to action you can ship today."),
    ("09-replies.png",
     ("§09  REPLY DRAFTS", "Per-complaint, with self-audit panel.", "zoom_in_center"),
     "AI-drafted replies with self-critique — review, edit, send."),
    ("10-ai-advisor.png",
     ("§10  AI ADVISOR", "Context = your data only.", "zoom_in_center"),
     "Ask anything — the advisor reads your shop, not the whole web."),
]

def build_kenburns_filter(motion, dur_frames):
    """Build ffmpeg zoompan filter for Ken Burns motion."""
    # Source images are 2560x1422; we render to 1920x1080
    # zoompan z formula: z='1.0+0.0011*on'  (on = current frame, d = total frames)
    # Use 1.04 → 1.18 over duration for subtle zoom
    if motion == "zoom_in_center":
        return (f"zoompan=z='1.04+0.14*on/{dur_frames}':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={dur_frames}:s={W}x{H}:fps={FPS}")
    elif motion == "zoom_out":
        return (f"zoompan=z='1.20-0.16*on/{dur_frames}':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={dur_frames}:s={W}x{H}:fps={FPS}")
    elif motion == "zoom_in_left":
        return (f"zoompan=z='1.04+0.14*on/{dur_frames}':"
                f"x='iw*0.30':y='ih/2-(ih/zoom/2)':"
                f"d={dur_frames}:s={W}x{H}:fps={FPS}")
    elif motion == "pan_down":
        # zoom mostly fixed at 1.10, pan y from top to bottom
        return (f"zoompan=z='1.10':"
                f"x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*on/{dur_frames}':"
                f"d={dur_frames}:s={W}x{H}:fps={FPS}")
    elif motion == "pan_up":
        return (f"zoompan=z='1.10':"
                f"x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/{dur_frames})':"
                f"d={dur_frames}:s={W}x{H}:fps={FPS}")
    elif motion == "pan_left":
        return (f"zoompan=z='1.10':"
                f"x='(iw-iw/zoom)*(1-on/{dur_frames})':y='ih/2-(ih/zoom/2)':"
                f"d={dur_frames}:s={W}x{H}:fps={FPS}")
    elif motion == "pan_right":
        return (f"zoompan=z='1.10':"
                f"x='(iw-iw/zoom)*on/{dur_frames}':y='ih/2-(ih/zoom/2)':"
                f"d={dur_frames}:s={W}x{H}:fps={FPS}")
    return f"scale={W}:{H}"


def build_caption_image(kicker, line1, line2, idx):
    """Build a transparent PNG with caption text overlay."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Bottom-left lower-third box (semi-transparent)
    box_h = 240
    box_y = H - box_h - 60
    # subtle dark gradient bar
    for i in range(box_h):
        a = int(180 * (1 - i / box_h * 0.3))  # 180→126
        d.line([(0, box_y + i), (W // 2 + 200, box_y + i)], fill=(13, 15, 14, a))
    # Coral kicker
    f_kicker = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 22)
    d.text((90, box_y + 30), kicker, font=f_kicker, fill=(214, 90, 58, 230))
    # Big serif line 1
    f_l1 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 56)
    d.text((90, box_y + 70), line1, font=f_l1, fill=(255, 255, 255, 255))
    # Sans line 2 (subtitle)
    f_l2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
    d.text((90, box_y + 150), line2, font=f_l2, fill=(176, 182, 179, 230))
    # Top-right segment number (mono)
    f_num = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 18)
    num_txt = f"{idx:02d} / 10"
    bbox = d.textbbox((0, 0), num_txt, font=f_num)
    d.text((W - bbox[2] - 60, 50), num_txt, font=f_num, fill=(176, 182, 179, 200))
    return img


def main():
    for idx, (filename, caption_tuple, sub_text) in enumerate(SEGMENTS, start=1):
        kicker, line1, motion = caption_tuple
        line2 = sub_text
        src_path = SRC / filename
        out_path = OUT / f"seg_{idx:02d}.mp4"
        print(f"[{idx:02d}/10] {filename} → {out_path.name}  (motion={motion})")

        # Build caption overlay PNG
        cap_img = build_caption_image(kicker, line1, line2, idx)
        cap_path = OUT / f"cap_{idx:02d}.png"
        cap_img.save(cap_path)

        # Run ffmpeg with zoompan + caption overlay
        kb = build_kenburns_filter(motion, N_FRAMES)
        # filter graph: scale source padded → zoompan → overlay caption with fade
        # caption fade: 0-0.5s fade in, 5.5-6.0s fade out
        fade_in = "fade=in:0:15"  # 15 frames = 0.5s
        fade_out = f"fade=out:{N_FRAMES - 15}:15"
        # First scale source up if needed (zoompan needs source >= output for clean zoom)
        # 2560x1422 is bigger than 1920x1080, good
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-framerate", str(FPS), "-t", str(DUR), "-i", str(src_path),
            "-loop", "1", "-framerate", str(FPS), "-t", str(DUR), "-i", str(cap_path),
            "-filter_complex",
            f"[0:v]scale=2560:1422,{kb},setsar=1[bg];"
            f"[1:v]format=rgba,fade=in:0:12,fade=out:{N_FRAMES - 12}:12[cap];"
            f"[bg][cap]overlay=0:0,format=yuv420p[v]",
            "-map", "[v]",
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "fastdecode", "-crf", "26",
            "-r", str(FPS), "-t", str(DUR),
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr[-500:]}")
        else:
            size_kb = out_path.stat().st_size / 1024
            print(f"  ✓ {size_kb:.0f}KB")


if __name__ == "__main__":
    main()
