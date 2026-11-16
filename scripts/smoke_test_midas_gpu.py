"""Phase 0 smoke test: DPT-Hybrid-384 depth inference on the NVIDIA GPU.

Loads the model through the backend's own loader
(backend/depth/midas_processor.py), so a pass here means the real backend
code path works, not just that PyTorch is installed.

Usage (from the repository root):
    venv/bin/python scripts/smoke_test_midas_gpu.py            # FP32
    venv/bin/python scripts/smoke_test_midas_gpu.py --fp16     # FP32, then FP16
    venv/bin/python scripts/smoke_test_midas_gpu.py --image path/to/photo.jpg

Exit code 0 = every check passed, 1 = a check failed.
"""

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

WARMUP_RUNS = 3
TIMED_RUNS = 10


def load_test_image(explicit):
    """Return (bgr_image, description). Falls back to a synthetic image."""
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    else:
        frame_dir = REPO_ROOT / "video_frames"
        candidates += sorted(frame_dir.glob("*.jpg")) + sorted(frame_dir.glob("*.png"))
    for path in candidates:
        image = cv2.imread(str(path))
        if image is not None:
            return image, str(path)
    if explicit:
        raise SystemExit(f"FAIL: could not read image {explicit}")
    # Deterministic synthetic RGB image: smooth gradient plus rectangles.
    rng = np.random.default_rng(0)
    ys, xs = np.mgrid[0:480, 0:640]
    image = np.stack(
        [xs * 255 // 639, ys * 255 // 479, (xs + ys) * 255 // 1118], axis=2
    ).astype(np.uint8)
    for _ in range(6):
        x, y = int(rng.integers(0, 540)), int(rng.integers(0, 380))
        colour = tuple(int(c) for c in rng.integers(0, 255, 3))
        cv2.rectangle(image, (x, y), (x + 100, y + 100), colour, -1)
    return image, "synthetic 640x480 (no test image found)"


def run_inference(model, batch, out_hw, half):
    """One forward pass, resized to the input image size like the backend."""
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16, enabled=half):
        prediction = model(batch)
        prediction = torch.nn.functional.interpolate(
            prediction.unsqueeze(1).float(),
            size=out_hw,
            mode="bicubic",
            align_corners=False,
        ).squeeze()
    return prediction


def benchmark(model, batch, out_hw, half):
    """Time the forward pass with CUDA synchronisation; return stats."""
    label = "FP16 (autocast)" if half else "FP32"
    torch.cuda.reset_peak_memory_stats()
    for _ in range(WARMUP_RUNS):
        run_inference(model, batch, out_hw, half)
    torch.cuda.synchronize()

    times = []
    depth = None
    for _ in range(TIMED_RUNS):
        torch.cuda.synchronize()
        start = time.perf_counter()
        depth = run_inference(model, batch, out_hw, half)
        torch.cuda.synchronize()
        times.append((time.perf_counter() - start) * 1000.0)

    depth_np = depth.cpu().numpy()
    shape_ok = depth_np.shape == tuple(out_hw)
    finite_ok = bool(np.isfinite(depth_np).all())
    varied_ok = float(depth_np.max() - depth_np.min()) > 1e-6

    print(f"\n[{label}]")
    print(f"  output shape      : {depth_np.shape} (expected {tuple(out_hw)})"
          f" -> {'OK' if shape_ok else 'FAIL'}")
    print(f"  all values finite : {finite_ok} -> {'OK' if finite_ok else 'FAIL'}")
    print(f"  depth min / max   : {depth_np.min():.3f} / {depth_np.max():.3f}"
          f" -> {'OK' if varied_ok else 'FAIL (constant output)'}")
    print(f"  inference time    : median {np.median(times):.1f} ms, "
          f"min {min(times):.1f} ms, max {max(times):.1f} ms "
          f"({TIMED_RUNS} runs after {WARMUP_RUNS} warm-up)")
    print(f"  throughput        : {1000.0 / np.median(times):.1f} frames/s (model only)")
    print(f"  GPU memory        : allocated {torch.cuda.memory_allocated() / 2**20:.0f} MiB, "
          f"peak {torch.cuda.max_memory_allocated() / 2**20:.0f} MiB, "
          f"reserved {torch.cuda.memory_reserved() / 2**20:.0f} MiB")
    return shape_ok and finite_ok and varied_ok, depth_np


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--image", help="test image (default: first file in video_frames/)")
    parser.add_argument("--fp16", action="store_true", help="also test FP16 after FP32")
    args = parser.parse_args()

    print("PyTorch version   :", torch.__version__)
    print("CUDA available    :", torch.cuda.is_available())
    if not torch.cuda.is_available():
        print("FAIL: torch.cuda.is_available() is False")
        return 1
    print("CUDA runtime      :", torch.version.cuda)
    print("cuDNN             :", torch.backends.cudnn.version())
    print("GPU               :", torch.cuda.get_device_name(0))
    total = torch.cuda.get_device_properties(0).total_memory / 2**20
    print(f"GPU total memory  : {total:.0f} MiB")

    # The backend's real loader: DPT_Hybrid via torch.hub + dpt_hybrid_384.pt.
    from backend.depth import midas_processor

    print("Weights file      :", midas_processor.WEIGHTS.resolve())
    processor = midas_processor.MiDaSProcessor()
    if processor.device.type != "cuda":
        print("FAIL: backend loader did not select CUDA")
        return 1
    on_gpu = next(processor.model.parameters()).is_cuda
    print("Model on CUDA     :", on_gpu)
    if not on_gpu:
        return 1

    image, source = load_test_image(args.image)
    print("Test image        :", source, f"({image.shape[1]}x{image.shape[0]})")
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    batch = torch.from_numpy(processor.transform({"image": rgb})["image"])
    batch = batch.unsqueeze(0).to(processor.device)
    print("Network input     :", tuple(batch.shape))

    ok, depth32 = benchmark(processor.model, batch, image.shape[:2], half=False)

    # The backend's own predict() must agree with the direct forward pass.
    backend_depth = processor.predict(image)
    same = np.allclose(backend_depth, depth32, rtol=1e-3, atol=1e-2)
    print(f"\nbackend predict() matches direct FP32 pass: {same}")
    ok = ok and same

    if args.fp16:
        ok16, depth16 = benchmark(processor.model, batch, image.shape[:2], half=True)
        scale = float(np.abs(depth32).max()) or 1.0
        diff = float(np.abs(depth16 - depth32).max()) / scale
        print(f"  FP16 vs FP32      : max abs difference {diff * 100:.2f}% of depth range")
        ok = ok and ok16

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
