# Examples

Three downloadable examples use cases from the
[project page](https://zju3dv.github.io/InfiniSplat2/).
The examples retain the larger input sets used by the corresponding visualization
and demo cases. Calibrated examples include matching cameras.
See [data sources and terms](NOTICE.md).
The original 114 PNG images, two camera files and frame manifest are available
as a **90.4 MB** [sample archive](https://huggingface.co/Edisoneh/InfiniSplat-v2/resolve/main/examples-png.zip).
Image dimensions and pixel values are preserved; no JPEG conversion is used.

From `InfiniSplat_v2/`, download and extract once before running the examples:

```bash
hf download Edisoneh/InfiniSplat-v2 examples-png.zip --local-dir .
python -m zipfile -e examples-png.zip .
```

The images are downloaded separately to keep the code repository small.

| Example | Scene | Views | Camera mode |
| --- | --- | --- | --- |
| `hypersim_provided` | Hypersim `ai_004_009` | 50 | Supplied cameras |
| `dtu_provided` | DTU scan 24 | 32 | Supplied cameras |
| `hypersim_da3_pose` | Hypersim `ai_006_001` | 32 | DA3-estimated camera prior |

From `InfiniSplat_v2/`, after installing and preparing `weights/da3`:

```bash
infinisplat --model weights/da3 --images-dir examples/data/hypersim_provided/images --cameras examples/data/hypersim_provided/cameras.npz --max-views 50 --output result_hypersim --no-html
```

```bash
infinisplat --model weights/da3 --images-dir examples/data/dtu_provided/images --cameras examples/data/dtu_provided/cameras.npz --output result_dtu --no-html
```

```bash
infinisplat --model weights/da3 --images-dir examples/data/hypersim_da3_pose/images --pose-mode da3-pose --output result_hypersim_da3 --no-html
```

Use `--long-side 224` for a smaller initial check. To generate a standalone viewer,
install the optional converter and omit `--no-html`. Run each command with a new
output directory. The 50-view Hypersim example requires `--max-views 50`; the
other examples fit the CLI default of 32 views. Lower `--long-side` if GPU memory
is limited; this preserves the full input-view set.

## Your own images

Run from `InfiniSplat_v2/` after [installation](../INSTALL.md). Put 2–8 overlapping
images of one static scene directly in `images/` to start. Filenames determine the
view order; supported extensions are JPG/JPEG, PNG and WebP, case-insensitively.
Use a new output directory for every command.

## 1. Images without supplied cameras

By default, DA3 predicts cameras first and uses that prior to condition reconstruction:

```bash
infinisplat --model weights/da3 --images-dir images --output result_prior --no-html
```

This is equivalent to explicitly passing `--pose-mode da3-pose`. To skip the
camera prepass, select `pose-free` explicitly:

```bash
infinisplat --model weights/da3 --images-dir images --pose-mode pose-free --output result_rgb --no-html
```

Both routes produce `scene.ply`, `cameras.npz` and `result.json`; the default
`da3-pose` route also produces `camera_prior.npz`. Quality depends on image
overlap and camera estimates.

## 2. COLMAP cameras

```bash
python scripts/prepare_colmap.py --images images --output prepared
infinisplat --model weights/da3 --images-dir prepared/undistorted/images --colmap prepared/undistorted/sparse_txt --output result_colmap --no-html
```

Read the [COLMAP guide](../docs/colmap.md) for existing models, missing registrations
and disconnected components.

## 3. Calibrated cameras and the Python API

For original-image pixel intrinsics and OpenCV camera-to-world poses, save:

```python
import numpy as np

# Obtain these arrays from your calibration; this does not estimate cameras.
# camera_to_world: [N, 4, 4]; pixel_intrinsics: [N, 3, 3].
# Both must follow the filename-sorted order of images/.
np.savez('cameras.npz', c2w=camera_to_world, intrinsics=pixel_intrinsics)
```

Then run the complete Python API example:

```bash
python examples/reconstruct.py --model weights/da3 --images-dir images --pose-mode provided --cameras cameras.npz --output result_api
```

The script uses the same defaults as the CLI: `da3-pose` without cameras and
`provided` with cameras. It also accepts `--pose-mode pose-free`, `--pose-mode da3-pose`, or
`--pose-mode provided --colmap prepared/undistorted/sparse_txt`.

## View results

Install the optional converter from [INSTALL.md](../INSTALL.md). Omit `--no-html`
in CLI recipes or pass `--html` to the Python example to create `scene.html`.
Open it locally for the standalone SH0 viewer; its PLY sidecar is not required.

Start with `--long-side 224` if GPU memory is limited. These examples reconstruct
a scene and export its native Gaussians; they do not run per-scene optimization.
