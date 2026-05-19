"""
v3 composite — intro + 6 demos + outro with crossfades.
Adds simple ambient pad audio synthesized via ffmpeg.
"""
import subprocess
from pathlib import Path

ROOT = Path("/sessions/kind-affectionate-pascal/mnt/Claude實作--InsightX/video")

SEGMENTS = [
    (ROOT / "intro_1080.mp4", 5.0),
    (ROOT / "demo_segments_v2/seg_01.mp4", 7.0),
    (ROOT / "demo_segments_v2/seg_02.mp4", 7.0),
    (ROOT / "demo_segments_v2/seg_03.mp4", 7.0),
    (ROOT / "demo_segments_v2/seg_04.mp4", 7.0),
    (ROOT / "demo_segments_v2/seg_05.mp4", 7.0),
    (ROOT / "demo_segments_v2/seg_06.mp4", 7.0),
    (ROOT / "outro_1080.mp4", 5.0),
]
XFADE = 0.4
inputs = []
for p, _ in SEGMENTS:
    inputs.extend(["-i", str(p)])
filter_parts = []
prev_label = "[0:v]"
cumulative_offset = 0.0
for i in range(1, len(SEGMENTS)):
    new_label = f"[v{i:02d}]"
    seg_dur = SEGMENTS[i - 1][1]
    cumulative_offset += seg_dur - XFADE
    filter_parts.append(
        f"{prev_label}[{i}:v]xfade=transition=fade:duration={XFADE}:offset={cumulative_offset}{new_label}"
    )
    prev_label = new_label
filter_complex = ";".join(filter_parts)

cmd = [
    "ffmpeg", "-y", "-loglevel", "error",
    *inputs,
    "-filter_complex", filter_complex,
    "-map", prev_label,
    "-c:v", "libx264", "-preset", "medium", "-crf", "22",
    "-pix_fmt", "yuv420p", "-r", "24",
    str(ROOT / "output" / "InsightX_v4_v3_silent.mp4"),
]
total_dur = sum(d for _, d in SEGMENTS) - (len(SEGMENTS) - 1) * XFADE
print(f"Compositing {len(SEGMENTS)} segments, expected {total_dur:.1f}s ...")
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(f"ERROR: {result.stderr[-1500:]}")
else:
    print(f"✓ silent video done")
