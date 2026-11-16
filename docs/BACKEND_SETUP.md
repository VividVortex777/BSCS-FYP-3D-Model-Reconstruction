# Backend setup (FastAPI + MiDaS DPT-Hybrid on the GPU)

Phase 0 result: the real DPT-Hybrid-384 model loads through
`backend/depth/midas_processor.py` and runs on the RTX 4050. This file
describes how to recreate that environment.

## Tested configuration (2026-11-16)

| Item | Version |
|---|---|
| OS | Ubuntu 26.04.1, ROS 2 Lyrical (not touched) |
| GPU / driver | RTX 4050 Laptop 6 GB, NVIDIA driver 595.99.02 |
| Python | 3.14.4 (system interpreter, used only to create the venv) |
| torch / torchvision | 2.15.0+cu132 / 0.29.2+cu132 |
| CUDA runtime / cuDNN | 13.2 / 9.26 (bundled in the pip wheels) |
| timm | 0.6.13 |
| fastapi / uvicorn | 0.163.1 / 0.54.0 |
| opencv-python-headless / numpy | 5.0.0.93 / 2.5.5 |

The full list of exact versions is in `backend/requirements.lock.txt`.
That lock file was resolved and tested for **Linux x86_64 with Python
3.14** only. Several of its packages (torch, numpy, opencv, the
`nvidia-*` CUDA libraries) are built separately for each Python version
and platform. For a different setup, install from `requirements.txt`
and record a new lock file with `venv/bin/pip freeze`.

The pip wheels include the CUDA and cuDNN libraries, so no system CUDA
toolkit is needed. The NVIDIA driver must be version 580 or newer for
CUDA 13.x.

## 1. Create the virtual environment

The environment is isolated from system Python and from the ROS Python
packages. `venv/` is listed in `.gitignore`.

```bash
cd ~/Projects/fyp-smartphone-robot-navigation
python3 -m venv venv
venv/bin/pip install -r backend/requirements.txt
# or, to reproduce the exact tested set:
venv/bin/pip install -r backend/requirements.lock.txt
```

The download is about 3 GB, mostly CUDA libraries, and the installed venv
is about 5.7 GB.

**On a slow or unreliable network:** pip loses its partial downloads when
it is interrupted. Instead, use `scripts/fetch_wheels.sh`. It works in
two stages:

1. It asks pip which packages the lock file needs. This fetches only
   package information, not the packages themselves. The result is a
   list of URLs and SHA-256 hashes, saved as `urls.tsv`.
2. It downloads each package with `curl`, resuming any partial file, and
   checks each file against its hash.

Packages are saved to `~/FYP-data/wheels/`, outside Git. You can change
that folder with `WHEELS_DIR`. The script is safe to re-run at any time;
it skips files that are already verified. After it finishes, install
offline:

```bash
python3 -m venv venv     # the script uses the venv's pip for stage 1
mkdir -p ~/FYP-data/wheels
setsid nohup bash scripts/fetch_wheels.sh >> ~/FYP-data/wheels/fetch.log 2>&1 < /dev/null &
tail -f ~/FYP-data/wheels/fetch.log          # wait for ALL-WHEELS-READY
venv/bin/pip install --no-index --find-links ~/FYP-data/wheels -r backend/requirements.lock.txt
```

`setsid nohup` keeps the download running after the terminal or the
Claude/IDE session closes. If the PC shuts down, run the same command
again and it resumes.

## 2. MiDaS code and weights (kept out of Git)

```bash
git clone --depth 1 https://github.com/isl-org/MiDaS MiDaS     # gitignored
mkdir -p ~/FYP-data/midas_weights MiDaS/weights
curl -L -C - -o ~/FYP-data/midas_weights/dpt_hybrid_384.pt \
  https://github.com/isl-org/MiDaS/releases/download/v3/dpt_hybrid_384.pt
ln -s ~/FYP-data/midas_weights/dpt_hybrid_384.pt MiDaS/weights/dpt_hybrid_384.pt
sha256sum ~/FYP-data/midas_weights/dpt_hybrid_384.pt
# expected: 501f0c75b3bca7daec6b3682c5054c09b366765aef6fa3a09d03a5cb4b230853
```

The weights file is 492,757,791 bytes.

## 3. Verify the GPU

```bash
venv/bin/python scripts/smoke_test_midas_gpu.py          # FP32
venv/bin/python scripts/smoke_test_midas_gpu.py --fp16   # FP32, then FP16
```

The test exits with code 0 and prints `RESULT: PASS` when every check
passes. It checks the following:

- CUDA is available.
- The model is on the GPU.
- The output size matches the input.
- The values are finite and not constant.
- The backend's `predict()` matches a direct forward pass.

It also reports timing and GPU memory.

Measured on a 640×480 image (model only, median of 10 runs, two separate
sessions on 2026-11-16):

| Precision | Time | Throughput | Peak GPU memory |
|---|---|---|---|
| FP32 | 39.5–43.7 ms | 23–25 fps | 604 MiB |
| FP16 (autocast) | 23.5–26.0 ms | 38–43 fps | 868 MiB |

Timings vary by about 10% between runs, because a laptop GPU's clock
speed changes with temperature and power state. Treat these as
approximate figures, not exact benchmarks. Memory use was identical in
both runs.

In FP16 the depth differs from FP32 by at most 0.16% of the depth range.
The backend itself still runs in FP32.

## 4. Run the backend and simulate the phone

```bash
./run_backend.sh                                   # http://0.0.0.0:8000
curl http://127.0.0.1:8000/health                  # expect "device":"cuda"
venv/bin/python scripts/test_backend_pipeline.py   # streams video_frames/*.jpg
```

## Known issues

- On import, timm 0.6.13 prints a `torch.jit.script is not supported in
  Python 3.14+` FutureWarning. Inference is unaffected and every test
  passed. A future PyTorch release may turn this warning into an error;
  if that happens, the fix is to move to a newer timm and check that
  MiDaS still works with it.
- The official compatibility matrix has not been checked for the exact
  torch 2.15.0 + torchvision 0.29.2 pairing. pip accepted it
  (torchvision requires `torch>=2.14`), and it works in practice.
- `scripts/test_backend_pipeline.py` reads test frames from
  `video_frames/`, which is not committed. Put any JPEG images in that
  folder before running it.
