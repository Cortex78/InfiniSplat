"""Camera inputs for context images; COLMAP input must already be undistorted."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import numpy as np


def validate_intrinsics(intrinsics, views):
    K = np.asarray(intrinsics, dtype=np.float32)
    if K.shape != (views, 3, 3) or not np.isfinite(K).all():
        raise ValueError('Intrinsics must be finite with shape [views,3,3]')
    if not np.allclose(K[:, 2], [0, 0, 1], rtol=0, atol=1e-6):
        raise ValueError('Intrinsics must have bottom row [0,0,1]')
    if np.any(np.abs(K[:, 0, 1]) > 1e-6) or np.any(np.abs(K[:, 1, 0]) > 1e-6):
        raise ValueError('Intrinsics must have zero skew')
    if np.any(K[:, 0, 0] <= 0) or np.any(K[:, 1, 1] <= 0):
        raise ValueError('Focal lengths must be positive')
    return K


def validate_cameras(cameras, images):
    try:
        c2w = np.asarray(cameras['c2w'], dtype=np.float32)
        K = validate_intrinsics(cameras['intrinsics'], len(images))
    except KeyError as error:
        raise ValueError('Camera input requires c2w and intrinsics arrays') from error
    if c2w.shape != (len(images), 4, 4) or not np.isfinite(c2w).all():
        raise ValueError('OpenCV c2w must be finite with shape [views,4,4]')
    if not np.allclose(c2w[:, 3], [0, 0, 0, 1], rtol=0, atol=1e-6):
        raise ValueError('Invalid homogeneous camera row')
    rotation = c2w[:, :3, :3]
    if np.any(np.linalg.det(rotation) <= 0):
        raise ValueError('Camera rotations must be right-handed')
    if not np.allclose(rotation.transpose(0, 2, 1) @ rotation, np.eye(3), atol=1e-4):
        raise ValueError('Camera rotations must be orthonormal')
    from PIL import Image
    for path in images:
        with Image.open(path) as image:
            if image.getexif().get(274, 1) != 1:
                raise ValueError('Provided cameras require images without EXIF rotation; rotate images and update calibration first')
    return dict(c2w=c2w, intrinsics=K)


def load_colmap(directory, images):
    directory = Path(directory)
    if not all((directory / name).is_file() for name in ('cameras.txt', 'images.txt')):
        if not all((directory / name).is_file() for name in ('cameras.bin', 'images.bin', 'points3D.bin')):
            raise ValueError('COLMAP model requires cameras.txt/images.txt or cameras.bin/images.bin/points3D.bin')
        executable = shutil.which('colmap')
        if executable is None:
            raise ValueError('Binary COLMAP input requires the colmap executable; alternatively export a TXT model')
        with tempfile.TemporaryDirectory(prefix='infinisplat-colmap-') as temporary:
            try:
                subprocess.run([executable, 'model_converter', '--input_path', str(directory),
                                '--output_path', temporary, '--output_type', 'TXT'],
                               check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as error:
                raise ValueError('COLMAP model conversion failed: ' + (error.stderr or error.stdout)[-2000:]) from error
            return load_colmap(temporary, images)
    cameras = {}
    for line in (directory / 'cameras.txt').read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        cid, model, width, height, *params = line.split()
        params = list(map(float, params))
        if model == 'PINHOLE' and len(params) == 4:
            fx, fy, cx, cy = params
        elif model == 'SIMPLE_PINHOLE' and len(params) == 3:
            fx, cx, cy = params
            fy = fx
        else:
            raise ValueError('Use COLMAP image_undistorter and a PINHOLE text model')
        cameras[int(cid)] = (np.array([[fx,0,cx],[0,fy,cy],[0,0,1]], dtype=np.float32),
                             (int(width), int(height)))
    records = {}
    lines = iter((directory / 'images.txt').read_text().splitlines())
    for line in lines:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        parts = line.split(maxsplit=9)
        if len(parts) != 10:
            raise ValueError('Invalid COLMAP images.txt image record')
        _, qw, qx, qy, qz, tx, ty, tz, cid, name = parts
        q = np.array([qw,qx,qy,qz], dtype=np.float64)
        if not np.isfinite(q).all() or np.linalg.norm(q) < 1e-8:
            raise ValueError('Invalid COLMAP quaternion')
        w,x,y,z = q / np.linalg.norm(q)
        R = np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                      [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                      [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
        c2w = np.eye(4, dtype=np.float32)
        c2w[:3,:3] = R.T
        c2w[:3,3] = -R.T @ np.array([tx,ty,tz], dtype=np.float64)
        if name in records:
            raise ValueError('Duplicate COLMAP image name: ' + name)
        records[name] = (c2w, *cameras[int(cid)])
        if next(lines, None) is None:
            raise ValueError('Missing COLMAP points2D record')
    selected = []
    from PIL import Image
    for image in images:
        path = Path(image)
        matches = [v for name,v in records.items()
                   if path.as_posix() == name or path.as_posix().endswith('/' + name)]
        if len(matches) != 1:
            raise ValueError('Image must match exactly one registered COLMAP name: ' + str(path))
        pose, K, size = matches[0]
        with Image.open(path) as im:
            if im.size != size or im.getexif().get(274, 1) != 1:
                raise ValueError('Use matching undistorted images without EXIF rotation')
        selected.append((pose,K))
    return dict(c2w=np.stack([v[0] for v in selected]),
                intrinsics=np.stack([v[1] for v in selected]))


def add_camera_arguments(parser):
    parser.add_argument('--pose-mode', choices=['provided','da3-pose','pose-free'],
                        help='Default: provided with camera input, otherwise da3-pose')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--cameras', help='NPZ: OpenCV c2w [N,4,4], original pixel intrinsics [N,3,3], in --images order')
    group.add_argument('--colmap', help='Undistorted COLMAP TXT or BIN model directory')


def resolve_camera_arguments(args, parser):
    provided = bool(args.cameras or args.colmap)
    mode = args.pose_mode or ('provided' if provided else 'da3-pose')
    if (mode == 'provided') != provided:
        parser.error('provided requires --cameras or --colmap; other modes accept neither')
    cameras = None
    try:
        if args.cameras:
            with np.load(args.cameras, allow_pickle=False) as data:
                cameras = {key:data[key] for key in ('c2w','intrinsics')}
        elif args.colmap:
            cameras = load_colmap(args.colmap, args.images)
        if cameras is not None:
            cameras = validate_cameras(cameras, args.images)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    return mode, cameras


def save_camera_prior(scene, output):
    if 'camera_prior' in scene:
        np.savez(Path(output) / 'camera_prior.npz',
                 **{k:v.cpu().numpy() for k,v in scene['camera_prior'].items()})
