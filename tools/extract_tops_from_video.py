from pathlib import Path
import json

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
VIDEO_PATH = ROOT / "assets" / "sprites" / "tops-part-1.mp4"
CHARACTER_DIRECTORY = ROOT / "assets" / "generated-game-assets" / "characters"
TOPS_DIRECTORY = CHARACTER_DIRECTORY / "clothing" / "tops"
CATALOG_PATH = CHARACTER_DIRECTORY / "clothing-catalog.json"
BASE_PATH = CHARACTER_DIRECTORY / "base" / "brunette-character-base.png"
CANVAS_WIDTH = 160
CANVAS_HEIGHT = 180
AVATAR_CROP = (25, 170, 235, 412)


def read_frame(capture, fps, seconds):
    capture.set(cv2.CAP_PROP_POS_FRAMES, round(seconds * fps))
    success, frame = capture.read()
    if not success:
        raise RuntimeError(f"Could not read video frame at {seconds:.2f}s")
    return frame


def crop_avatar(frame):
    x0, y0, x1, y1 = AVATAR_CROP
    return frame[y0:y1, x0:x1]


def foreground_alpha(image):
    distance = np.max(255 - image.astype(np.int16), axis=2)
    return np.clip((distance - 5) * 18, 0, 255).astype(np.uint8)


def median_state(capture, fps, start, end):
    margin = min(0.16, max(0.04, (end - start) * 0.2))
    sample_times = np.linspace(start + margin, end - margin, max(5, round((end - start) * 12)))
    frames = [crop_avatar(read_frame(capture, fps, float(seconds))) for seconds in sample_times]
    return np.median(np.stack(frames), axis=0).astype(np.uint8)


def find_base_state(capture, fps):
    frames = [
        crop_avatar(read_frame(capture, fps, float(seconds)))
        for seconds in np.arange(2.8, 6.2, 0.12)
    ]
    return np.median(np.stack(frames), axis=0).astype(np.uint8)


def calculate_transform(base):
    alpha = foreground_alpha(base)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        np.where(alpha > 18, 255, 0).astype(np.uint8),
        8,
    )
    if count <= 1:
        raise RuntimeError("Could not locate the base character in the video")
    component = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    ys, xs = np.where(labels == component)
    x0, x1 = xs.min(), xs.max() + 1
    y0, y1 = ys.min(), ys.max() + 1
    target_height = 154
    scale = target_height / (y1 - y0)
    target_width = round((x1 - x0) * scale)
    target_x = (CANVAS_WIDTH - target_width) // 2
    target_y = CANVAS_HEIGHT - target_height - 4
    matrix = np.array(
        [
            [scale, 0, target_x - x0 * scale],
            [0, scale, target_y - y0 * scale],
        ],
        dtype=np.float32,
    )
    return matrix


def normalize(image, matrix):
    return cv2.warpAffine(
        image,
        matrix,
        (CANVAS_WIDTH, CANVAS_HEIGHT),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )


def closet_is_visible(frame):
    region = frame[115:500, 10:290]
    brightness = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    return float((brightness > 220).mean()) > 0.4


def detect_dressed_segments(capture, fps, duration, base):
    base_region = cv2.GaussianBlur(base[60:235, 30:205], (3, 3), 0).astype(np.int16)
    samples = []
    for seconds in np.arange(0, duration, 0.1):
        frame = read_frame(capture, fps, float(seconds))
        if not closet_is_visible(frame):
            samples.append((float(seconds), False))
            continue
        avatar = crop_avatar(frame)
        region = cv2.GaussianBlur(avatar[60:235, 30:205], (3, 3), 0).astype(np.int16)
        difference = np.max(np.abs(region - base_region), axis=2)
        dressed = float((difference > 40).mean()) > 0.025
        samples.append((float(seconds), dressed))

    segments = []
    start = None
    for seconds, dressed in samples:
        if dressed and start is None:
            start = seconds
        if not dressed and start is not None:
            if seconds - start >= 0.35:
                segments.append((start, seconds))
            start = None
    if start is not None and duration - start >= 0.35:
        segments.append((start, duration))
    return segments


def filter_components(mask):
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    clean = np.zeros_like(mask)
    core = (48, 103, 112, 162)
    for component in range(1, count):
        x = stats[component, cv2.CC_STAT_LEFT]
        y = stats[component, cv2.CC_STAT_TOP]
        width = stats[component, cv2.CC_STAT_WIDTH]
        height = stats[component, cv2.CC_STAT_HEIGHT]
        area = stats[component, cv2.CC_STAT_AREA]
        if area < 8:
            continue
        intersects_core = not (
            x + width < core[0]
            or x > core[2]
            or y + height < core[1]
            or y > core[3]
        )
        if intersects_core:
            clean[labels == component] = 255
    return clean


def create_top_layer(base, dressed):
    difference = np.max(
        np.abs(dressed.astype(np.int16) - base.astype(np.int16)),
        axis=2,
    ).astype(np.uint8)
    difference = cv2.GaussianBlur(difference, (3, 3), 0)
    mask = np.where(difference > 24, 255, 0).astype(np.uint8)
    allowed = np.zeros_like(mask)
    allowed[103:164, 24:136] = 255
    mask = cv2.bitwise_and(mask, allowed)

    hsv = cv2.cvtColor(dressed, cv2.COLOR_BGR2HSV)
    skin = (
        (hsv[:, :, 0] < 18)
        & (hsv[:, :, 1] > 22)
        & (hsv[:, :, 1] < 130)
        & (hsv[:, :, 2] > 155)
    )
    mask[skin] = 0
    mask = filter_components(mask)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)

    layer = cv2.cvtColor(dressed, cv2.COLOR_BGR2BGRA)
    layer[:, :, 3] = np.minimum(foreground_alpha(dressed), mask)
    return layer


def write_base(base):
    BASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    for existing in BASE_PATH.parent.glob("*.png"):
        existing.unlink()
    output = cv2.cvtColor(base, cv2.COLOR_BGR2BGRA)
    output[:, :, 3] = foreground_alpha(base)
    cv2.imwrite(str(BASE_PATH), output)


def main():
    capture = cv2.VideoCapture(str(VIDEO_PATH))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = capture.get(cv2.CAP_PROP_FPS)
    if frame_count <= 0 or fps <= 0:
        raise RuntimeError(f"Could not decode {VIDEO_PATH}")
    duration = frame_count / fps

    raw_base = find_base_state(capture, fps)
    transform = calculate_transform(raw_base)
    base = normalize(raw_base, transform)
    segments = detect_dressed_segments(capture, fps, duration, raw_base)
    segments = [
        segment
        for segment in segments
        if segment[0] >= 2.0 and not 29.8 <= segment[0] < 40.0
    ]
    if not segments:
        raise RuntimeError("No dressed intervals were detected")

    TOPS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for existing in TOPS_DIRECTORY.glob("*.png"):
        existing.unlink()

    items = []
    for index, (start, end) in enumerate(segments, start=1):
        dressed = normalize(median_state(capture, fps, start, end), transform)
        layer = create_top_layer(base, dressed)
        item_id = f"top-{index:02d}"
        path = TOPS_DIRECTORY / f"{item_id}.png"
        cv2.imwrite(str(path), layer)
        items.append(
            {
                "id": item_id,
                "name": f"Top {index:02d}",
                "source": path.relative_to(ROOT).as_posix(),
                "video_start": round(start, 2),
                "video_end": round(end, 2),
            }
        )

    capture.release()
    write_base(base)

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    catalog["base"] = BASE_PATH.relative_to(ROOT).as_posix()
    catalog["categories"]["tops"] = items
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Extracted {len(items)} tops from {VIDEO_PATH.name}")


if __name__ == "__main__":
    main()
