"""A stand-in for stable-diffusion.cpp's sd-cli in the tests: same flags, prints step progress the
way sd-cli does and writes a plain PNG. FAKE_SD_SLEEP=<s> makes each step slow (pause tests),
FAKE_SD_FAIL=oom fails like a graphics card that ran out of memory."""

import argparse
import os
import sys
import time

from PIL import Image

ap = argparse.ArgumentParser()
for flag in ("--diffusion-model", "--vae", "--llm", "-p", "--cfg-scale", "--steps", "-W", "-H", "--seed", "-o", "-t"):
    ap.add_argument(flag)
ap.add_argument("-b", type=int, default=1)
for flag in ("--offload-to-cpu", "--diffusion-fa", "--vae-tiling"):
    ap.add_argument(flag, action="store_true")
a = ap.parse_args()
log = os.environ.get("FAKE_SD_LOG")
if log:
    with open(log, "a", encoding="utf-8") as f:
        f.write(" ".join(sys.argv[1:]) + "\n")
if os.environ.get("FAKE_SD_FAIL") == "oom":
    print("ggml_vulkan: Device memory allocation failed: ErrorOutOfDeviceMemory: out of memory", flush=True)
    sys.exit(1)
steps = int(a.steps)
for _k in range(a.b):  # a batch: one picture after the other, seeds seed, seed+1, ...
    for i in range(1, steps + 1):
        time.sleep(float(os.environ.get("FAKE_SD_SLEEP") or 0))
        sys.stdout.write(f"\r  |{'=' * i}{' ' * (steps - i)}| {i}/{steps} - 0.10s/it")
        sys.stdout.flush()
base, ext = os.path.splitext(a.o)
for k in range(a.b):  # saved at the end: img.png, or img_0.png ... for a batch
    seed = int(a.seed) + k
    out = a.o if a.b == 1 else f"{base}_{k}{ext}"
    Image.new("RGB", (int(a.W), int(a.H)), ((seed * 37) % 255, (seed * 91) % 255, (seed * 13) % 255)).save(out)
    print("\nsave result image to", out, flush=True)
