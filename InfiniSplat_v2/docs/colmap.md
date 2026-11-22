# Reconstruct with COLMAP cameras

Use overlapping photos of one static scene. Avoid moving objects, strong blur and
large exposure changes. Bake EXIF orientation into the photos before calibration;
do not rotate or resize calibrated images afterward.

COLMAP estimates the cameras. InfiniSplat then uses the registered, undistorted
images and their matching cameras for pose-conditioned Gaussian reconstruction.

## Prepare your own photos

After [installation](../INSTALL.md), place your photos in `images/` and run:

```bash
python scripts/prepare_colmap.py --images images --output prepared
```

This runs feature extraction, exhaustive matching, sparse mapping, image
undistortion, and conversion of the undistorted camera model to TXT. It does not
run dense stereo reconstruction. Exhaustive matching is intended for small photo
sets; for large collections, prepare a sparse model with your preferred COLMAP
workflow instead.

On headless servers the script automatically uses CPU feature extraction and
matching, avoiding an OpenGL display requirement. Pass `--cpu` to force that mode
on other machines. `--threads 4` is the default CPU limit; increase it if appropriate.
The script detects both the legacy `SiftExtraction`/`SiftMatching` options and the
newer `FeatureExtraction`/`FeatureMatching` options from your COLMAP installation.

The relevant output is:

```text
prepared/
├── database.db
├── sparse/                 # One or more original reconstruction components
└── undistorted/
    ├── images/             # Registered, undistorted input images
    ├── sparse/             # Corresponding camera model
    └── sparse_txt/
        ├── cameras.txt
        ├── images.txt
        └── points3D.txt
```

Then reconstruct:

```bash
infinisplat --model weights/da3 --images-dir prepared/undistorted/images --colmap prepared/undistorted/sparse_txt --output result_colmap --no-html
```

Use 2–32 registered images by default. For a subset, pass explicit `--images`
paths instead of `--images-dir`. Use `--max-views N` for more views when memory
permits. More images are never silently truncated.

## Video input

Extract overlapping frames with FFmpeg, then use the same COLMAP workflow.
For the [living-room video](https://huggingface.co/spaces/Edisoneh/InfiniSplat-v2-demo/resolve/main/examples/pexels_3769951/input.mp4)
from the hosted demo (10 seconds), these commands select 24 frames:

```bash
hf download Edisoneh/InfiniSplat-v2-demo examples/pexels_3769951/input.mp4 --repo-type space --local-dir video_example
mkdir images_video
ffmpeg -i video_example/examples/pexels_3769951/input.mp4 -vf fps=2.4 -frames:v 24 images_video/%03d.png
python scripts/prepare_colmap.py --images images_video --output prepared_video
infinisplat --model weights/da3 --images-dir prepared_video/undistorted/images --colmap prepared_video/undistorted/sparse_txt --output result_video --no-html
```

Install FFmpeg separately. For another video, adjust the sampling rate to retain
2–32 overlapping frames. Select one static scene rather than a video with cuts.
To export a viewer, install the [HTML converter](../INSTALL.md#optional-html-viewer)
and omit `--no-html`.

## Existing reconstruction or disconnected models

To use an existing sparse model and prepare a fresh set of undistorted inputs:

```bash
python scripts/prepare_colmap.py --images images --sparse-model workspace/sparse/0 --output prepared
```

If new mapping produces multiple disconnected components, the script stops before
undistortion. Inspect `prepared/sparse/`, choose one coherent model, then rerun with
`--sparse-model prepared/sparse/0` and a **new** `--output prepared_selected`.
Alternatively pass `--model-index 0` during new mapping to explicitly select that
component. Do not combine camera models with unrelated coordinate frames.

Images that were not registered in the selected component cannot be used with its
cameras. If too few images register, improve photo overlap or camera calibration
and rerun COLMAP. Choose filenames explicitly when your folder contains extra files.

## TXT and BIN inputs

The loader accepts `PINHOLE` and `SIMPLE_PINHOLE` cameras from an undistorted TXT
model. It also accepts a BIN model when COLMAP is installed; conversion happens in
a temporary directory and the original model is left untouched:

```bash
infinisplat --model weights/da3 --images-dir prepared/undistorted/images --colmap prepared/undistorted/sparse --output result_binary --no-html
```

Binary conversion requires `cameras.bin`, `images.bin` and `points3D.bin` (the points
file can describe an empty point set). To convert manually:

```bash
mkdir -p camera_model_txt
colmap model_converter --input_path prepared/undistorted/sparse --output_path camera_model_txt --output_type TXT
```

Distorted camera models are rejected. A BIN file does not make an original,
distorted model suitable for Gaussian inference: undistort first.

## Camera and output conventions

The loader matches image names, converts COLMAP world-to-camera transforms to
OpenCV camera-to-world matrices, and preserves the selected image order. Image
dimensions must match the model and EXIF rotation must be absent. Crop/resize
adjustment happens inside InfiniSplat, using the corresponding pixel intrinsics.

COLMAP camera centers are scale-aligned into native RDNorm reconstruction space.
The resulting PLY is not automatically in metric COLMAP world coordinates.
Output `cameras.npz` has processed-image intrinsics; it is not a replacement for
the original input camera model.

Refer to the official [COLMAP command-line guide](https://colmap.github.io/cli.html)
and [model format](https://colmap.github.io/format.html).
