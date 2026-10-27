from pathlib import Path
import json

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CHARACTER_DIRECTORY = ROOT / "assets" / "generated-game-assets" / "characters"
CATALOG_PATH = CHARACTER_DIRECTORY / "clothing-catalog.json"
DIRECTION_DIRECTORY = CHARACTER_DIRECTORY / "directions"
DIRECTIONS = ("front-right", "front-left", "back-right", "back-left")


def mirror(image):
    return cv2.flip(image, 1)


def hair_palette(front):
    hsv = cv2.cvtColor(front[:, :, :3], cv2.COLOR_BGR2HSV)
    region = np.zeros(hsv.shape[:2], dtype=bool)
    region[18:106, 25:137] = True
    hair = (
        region
        & (front[:, :, 3] > 30)
        & (hsv[:, :, 0] < 25)
        & (hsv[:, :, 1] > 75)
        & (hsv[:, :, 2] < 155)
    )
    pixels = front[:, :, :3][hair]
    if len(pixels) == 0:
        return np.array([35, 45, 75], dtype=np.uint8)
    return np.median(pixels, axis=0).astype(np.uint8)


def generate_back_base(front):
    back = front.copy()
    base_color = hair_palette(front).astype(np.float32)
    height, width = front.shape[:2]
    yy, xx = np.ogrid[:height, :width]
    hair_region = ((xx - 80) / 38) ** 2 + ((yy - 75) / 46) ** 2 <= 1
    hair_alpha = cv2.GaussianBlur(
        np.where(hair_region, 255, 0).astype(np.uint8),
        (5, 5),
        0,
    )
    back[:, :, 3] = np.maximum(back[:, :, 3], hair_alpha)

    texture_source = front[20:58, 44:116, :3]
    texture_hsv = cv2.cvtColor(texture_source, cv2.COLOR_BGR2HSV)
    texture_hair = (
        (texture_hsv[:, :, 0] < 25)
        & (texture_hsv[:, :, 1] > 70)
        & (texture_hsv[:, :, 2] < 175)
    )
    cleaned_texture = np.full_like(texture_source, base_color.astype(np.uint8))
    cleaned_texture[texture_hair] = texture_source[texture_hair]
    texture = cv2.resize(cleaned_texture, (74, 84), interpolation=cv2.INTER_CUBIC)
    texture_canvas = np.zeros_like(front[:, :, :3])
    texture_canvas[36:120, 43:117] = texture
    vertical = np.clip((yy - 34) / 88, 0, 1)
    shade = 0.88 + vertical * 0.08
    fill = np.clip(
        texture_canvas.astype(np.float32) * 0.72
        + base_color[None, None, :] * shade[:, :, None] * 0.28,
        0,
        255,
    ).astype(np.uint8)
    back[:, :, :3][hair_region] = fill[hair_region]

    strokes = np.zeros_like(back[:, :, :3])
    light = tuple(int(value) for value in np.clip(base_color * 1.16, 0, 255))
    dark = tuple(int(value) for value in np.clip(base_color * 0.86, 0, 255))
    paths = [
        ([(56, 48), (59, 70), (61, 103)], light),
        ([(68, 42), (70, 68), (70, 111)], dark),
        ([(80, 40), (80, 70), (79, 115)], light),
        ([(92, 43), (90, 72), (89, 111)], dark),
        ([(104, 49), (101, 75), (98, 104)], light),
    ]
    for points, color in paths:
        cv2.polylines(
            strokes,
            [np.array(points, dtype=np.int32)],
            False,
            color,
            1,
            cv2.LINE_AA,
        )
    stroke_mask = np.any(strokes > 0, axis=2) & hair_region
    back[:, :, :3][stroke_mask] = (
        back[:, :, :3][stroke_mask].astype(np.float32) * 0.65
        + strokes[stroke_mask].astype(np.float32) * 0.35
    ).astype(np.uint8)

    skin = cv2.cvtColor(back[:, :, :3], cv2.COLOR_BGR2HSV)
    neck_mask = (
        (skin[:, :, 0] < 18)
        & (skin[:, :, 1] > 20)
        & (skin[:, :, 1] < 130)
        & (skin[:, :, 2] > 150)
    )
    neck_region = np.zeros_like(neck_mask)
    neck_region[94:119, 60:101] = True
    back[:, :, :3][neck_mask & neck_region] = np.clip(base_color * 0.82, 0, 255).astype(np.uint8)
    return back


def generate_back_clothing(front):
    back = front.copy()
    alpha = front[:, :, 3]
    if not np.any(alpha):
        return back
    blurred = cv2.bilateralFilter(front[:, :, :3], 9, 55, 55)
    back[:, :, :3] = np.where(
        (alpha > 0)[:, :, None],
        np.clip(blurred.astype(np.float32) * 0.88, 0, 255).astype(np.uint8),
        0,
    )
    return back


def write_directions(directory, front):
    directory.mkdir(parents=True, exist_ok=True)
    back = generate_back_base(front) if directory.name == "base" else generate_back_clothing(front)
    images = {
        "front-right": front,
        "front-left": mirror(front),
        "back-right": back,
        "back-left": mirror(back),
    }
    for direction, image in images.items():
        cv2.imwrite(str(directory / f"{direction}.png"), image)


def main():
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    base = cv2.imread(str(ROOT / catalog["base"]), cv2.IMREAD_UNCHANGED)
    if base is None:
        raise FileNotFoundError(catalog["base"])

    write_directions(DIRECTION_DIRECTORY / "base", base)

    tops_directory = DIRECTION_DIRECTORY / "tops"
    for item in catalog["categories"]["tops"]:
        front = cv2.imread(str(ROOT / item["source"]), cv2.IMREAD_UNCHANGED)
        if front is None:
            raise FileNotFoundError(item["source"])
        write_directions(tops_directory / item["id"], front)

    manifest = {
        "directions": list(DIRECTIONS),
        "base": {
            direction: (DIRECTION_DIRECTORY / "base" / f"{direction}.png")
            .relative_to(ROOT)
            .as_posix()
            for direction in DIRECTIONS
        },
        "tops": {
            item["id"]: {
                direction: (
                    tops_directory / item["id"] / f"{direction}.png"
                ).relative_to(ROOT).as_posix()
                for direction in DIRECTIONS
            }
            for item in catalog["categories"]["tops"]
        },
    }
    (DIRECTION_DIRECTORY / "direction-manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print(f"Generated four directions for the base and {len(manifest['tops'])} tops")


if __name__ == "__main__":
    main()
