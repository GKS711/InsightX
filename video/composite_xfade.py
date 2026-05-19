"""
Composite intro + 10 demos + outro with xfade transitions.
Produces output/InsightX_v4_intro_v3_xfade.mp4
"""
import subprocess
from pathlib import Path

ROOT = Path("/sessions/kind-affectionate-pascal/mnt/Claude實作--InsightX/video")

# (path, duration_sec)
SEGMENTS = [
    (ROOT / "intro_720.mp4", 5.0),
    (ROOT / "demo_segments/seg_01.mp4", 6.0),
    (ROOT / "demo_segments/seg_02.mp4", 6.0),
    (ROOT / "demo_segments/seg_03.mp4", 6.0),
    (ROOT / "demo_segments/seg_04.mp4", 6.0),
    (ROOT / "demo_segments/seg_05.mp4", 6.0),
    (ROOT / "demo_segments/seg_06.mp4", 6.0),
    (ROOT / "demo_segments/seg_07.mp4", 6.0),
    (ROOT / "demo_segments/seg_08.mp4", 6.0),
    (ROOT / "demo_segments/seg_09.mp4", 6.0),
    (ROOT / "demo_segments/seg_10.mp4", 6.0),
    (ROOT / "outro_720.mp4", 5.0),
]
XFADE = 0.5  # seconds of crossfade

# Build xfade chain
inputs = []
for p, _ in SEGMENTS:
    inputs.extend(["-i", str(p)])

# Build filter chain
# [0:v][1:v]xfade=transition=fade:duration=0.5:offset=4.5[v01]
# [v01][2:v]xfade=...:offset=10[v02]
# ...
filter_parts = []
prev_label = "[0:v]"
cumulative_offset = 0.0
for i in range(1, len(SEGMENTS)):
    new_label = f"[v{i:02d}]"
    seg_dur = SEGMENTS[i - 1][1]
    cumulative_offset += seg_dur - XFADE  # offset = end of prev segment minus xfade
    transition = "fade"  # could vary: 'wipeleft', 'slideup', 'circleopen'
    filter_parts.append(
        f"{prev_label}[{i}:v]xfade=transition={transition}:duration={XFADE}:offset={cumulative_offset}{new_label}"
    )
    prev_label = new_label

filter_complex = ";".join(filter_parts)
final_label = prev_label

cmd = [
    "ffmpeg", "-y", "-loglevel", "error",
    *inputs,
    "-filter_complex", filter_complex,
    "-map", final_label,
    "-c:v", "libx264", "-preset", "medium", "-crf", "22",
    "-pix_fmt", "yuv420p", "-r", "24",
    str(ROOT / "output" / "InsightX_v4_intro_v3_xfade.mp4"),
]

print("Running xfade composite...")
print(f"  segments: {len(SEGMENTS)}")
print(f"  xfade: {XFADE}s")
print(f"  expected duration: {sum(d for _, d in SEGMENTS) - (len(SEGMENTS) - 1) * XFADE:.1f}s")
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(f"ERROR:\n{result.stderr[-1500:]}")
else:
    print(f"✓ done")
