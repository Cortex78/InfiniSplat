"""Run one scene through the pose-free, DA3-prior or calibrated-camera Python API."""
import argparse
from pathlib import Path

from infinisplat import Pipeline, export_ply
from infinisplat.cameras import add_camera_arguments, resolve_camera_arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--images-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    add_camera_arguments(parser)
    parser.add_argument('--html', action='store_true', help='Also create a standalone SH0 viewer')
    parser.add_argument('--long-side', type=int, default=518)
    parser.add_argument('--max-views', type=int, default=32, choices=range(2, 51), metavar='2..50')
    args = parser.parse_args()
    if not 112 <= args.long_side <= 2044:
        parser.error('--long-side must be between 112 and 2044')
    if not args.images_dir.is_dir():
        parser.error('--images-dir must exist')
    images = sorted((p for p in args.images_dir.iterdir() if p.is_file() and
                     p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}), key=lambda p: p.name)
    if not 2 <= len(images) <= args.max_views:
        parser.error(f'Select 2–{args.max_views} images in filename order')
    if args.output.exists():
        parser.error('--output must be a new directory')
    args.images = images
    mode, cameras = resolve_camera_arguments(args, parser)
    if args.html:
        from infinisplat.viewer import require_html_converter
        require_html_converter()
    pipeline = Pipeline.from_pretrained(args.model)
    scene = pipeline.reconstruct(images, cameras=cameras, pose_mode=mode,
                                 long_side=args.long_side, max_views=args.max_views)
    print(export_ply(scene, args.output, html=args.html))


if __name__ == '__main__':
    main()
