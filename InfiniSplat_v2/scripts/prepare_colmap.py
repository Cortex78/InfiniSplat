"""Estimate sparse cameras and prepare undistorted inputs for InfiniSplat v2."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess


def run(executable, command, **options):
    argv = [executable, command]
    for name, value in options.items():
        argv.extend(['--' + name, str(value)])
    try:
        subprocess.run(argv, check=True)
    except subprocess.CalledProcessError as error:
        raise SystemExit(f'COLMAP {command} failed (exit {error.returncode}); inspect its messages above.') from None


def sift_options(executable, command, threads, cpu):
    """Support both legacy Sift* options and current Feature* option names."""
    result = subprocess.run([executable, command, '-h'], check=True,
                            capture_output=True, text=True)
    help_text = result.stdout + result.stderr
    prefixes = ('FeatureExtraction', 'SiftExtraction') if command == 'feature_extractor' else ('FeatureMatching', 'SiftMatching')
    options = {}
    for suffix, value in [('num_threads', threads), ('use_gpu', 0 if cpu else 1)]:
        name = next((prefix + '.' + suffix for prefix in prefixes
                     if '--' + prefix + '.' + suffix in help_text), None)
        if name is None:
            raise SystemExit(f'Cannot determine COLMAP {command} option for {suffix}; check your COLMAP installation.')
        options[name] = value
    return options


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images', type=Path, required=True, help='Original images used by COLMAP')
    parser.add_argument('--output', type=Path, required=True, help='New preparation directory')
    parser.add_argument('--sparse-model', type=Path, help='Existing sparse model; skip feature extraction and mapping')
    parser.add_argument('--model-index', type=int, help='Choose one model when mapping produces multiple components')
    parser.add_argument('--cpu', action='store_true', help='Use CPU feature extraction and matching (automatic on headless machines)')
    parser.add_argument('--threads', type=int, default=4, help='COLMAP CPU threads; default 4')
    args = parser.parse_args()
    executable = shutil.which('colmap')
    if executable is None:
        parser.error('Install COLMAP and make colmap available on PATH')
    if not args.images.is_dir():
        parser.error('--images must be an existing directory')
    if args.output.exists():
        parser.error('--output must be a new directory')
    if args.sparse_model is not None and not args.sparse_model.is_dir():
        parser.error('--sparse-model must be an existing model directory')
    if args.model_index is not None and (args.model_index < 0 or args.sparse_model is not None):
        parser.error('--model-index must be nonnegative and is only used for new mapping')
    if args.threads < 1:
        parser.error('--threads must be positive')
    args.output.mkdir(parents=True, exist_ok=False)
    model = args.sparse_model
    if model is None:
        database = args.output / 'database.db'
        sparse = args.output / 'sparse'
        sparse.mkdir()
        headless = os.name != 'nt' and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))
        cpu = args.cpu or headless
        if cpu:
            print('Using CPU feature extraction and matching.', flush=True)
        run(executable, 'feature_extractor', database_path=database, image_path=args.images,
            **sift_options(executable, 'feature_extractor', args.threads, cpu))
        run(executable, 'exhaustive_matcher', database_path=database,
            **sift_options(executable, 'exhaustive_matcher', args.threads, cpu))
        run(executable, 'mapper', database_path=database, image_path=args.images, output_path=sparse,
            **{'Mapper.num_threads': args.threads})
        models = sorted(p for p in sparse.iterdir() if p.is_dir() and
                        ((p / 'images.bin').is_file() or (p / 'images.txt').is_file()))
        if args.model_index is not None:
            model = sparse / str(args.model_index)
            if model not in models:
                parser.error('Requested model was not reconstructed; inspect output/sparse and choose an existing component')
        elif len(models) == 1:
            model = models[0]
        else:
            parser.error('Expected one connected model; inspect output/sparse, then rerun with --sparse-model and a new --output')
    undistorted = args.output / 'undistorted'
    run(executable, 'image_undistorter', image_path=args.images, input_path=model,
        output_path=undistorted, output_type='COLMAP')
    text_model = undistorted / 'sparse_txt'
    text_model.mkdir()
    run(executable, 'model_converter', input_path=undistorted / 'sparse',
        output_path=text_model, output_type='TXT')
    print('Undistorted images:', undistorted / 'images')
    print('Camera model:', text_model)
    print('Use 2–32 registered images from this component; use --max-views to raise the limit.')


if __name__ == '__main__':
    main()
