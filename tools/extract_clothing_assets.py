from pathlib import Path
import json
import shutil

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = ROOT / "assets" / "sprites"
OUTPUT_DIRECTORY = ROOT / "assets" / "generated-game-assets" / "characters"
CANVAS_WIDTH = 160
CANVAS_HEIGHT = 180


SHEETS = {
    "accessories": {
        "path": SOURCE_DIRECTORY / "156506_orig.jpg",
        "columns": 10,
        "rows": 2,
        "indices": range(1, 15),
        "prefix": "Accessory",
        "filename_prefix": "accessory",
    },
    "bottoms": {
        "path": SOURCE_DIRECTORY / "2278360_orig.jpg",
        "columns": 10,
        "rows": 1,
        "indices": range(9),
        "prefix": "Bottom",
        "filename_prefix": "bottom",
    },
    "shoes": {
        "path": SOURCE_DIRECTORY / "6532314_orig.jpg",
        "columns": 10,
        "rows": 3,
        "indices": range(21),
        "prefix": "Shoes",
        "filename_prefix": "shoes",
    },
}


def read_sheet(path):
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(f"Could not read sprite sheet: {path}")
    return image


def extract_cell(sheet, columns, rows, index):
    row, column = divmod(index, columns)
    x0 = round(column * sheet.shape[1] / columns)
    x1 = round((column + 1) * sheet.shape[1] / columns)
    y0 = round(row * sheet.shape[0] / rows)
    y1 = round((row + 1) * sheet.shape[0] / rows)
    return sheet[y0:y1, x0:x1]


def normalize_cell(cell):
    height, width = cell.shape[:2]
    scale = CANVAS_HEIGHT / height
    resized_width = round(width * scale)
    resized = cv2.resize(
        cell,
        (resized_width, CANVAS_HEIGHT),
        interpolation=cv2.INTER_CUBIC,
    )
    canvas = np.full(
        (CANVAS_HEIGHT, CANVAS_WIDTH, 3),
        255,
        dtype=np.uint8,
    )
    x = (CANVAS_WIDTH - resized_width) // 2
    canvas[:, x : x + resized_width] = resized
    return canvas


def background_alpha(image):
    distance_from_white = np.max(255 - image.astype(np.int16), axis=2)
    return np.clip((distance_from_white - 4) * 16, 0, 255).astype(np.uint8)


def filter_components(mask, minimum_area=6, core=None, horizontal_limits=None):
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    clean = np.zeros_like(mask)
    for component in range(1, component_count):
        x = stats[component, cv2.CC_STAT_LEFT]
        y = stats[component, cv2.CC_STAT_TOP]
        width = stats[component, cv2.CC_STAT_WIDTH]
        height = stats[component, cv2.CC_STAT_HEIGHT]
        if stats[component, cv2.CC_STAT_AREA] < minimum_area:
            continue
        if horizontal_limits is not None:
            left_limit, right_limit = horizontal_limits
            if x + width < left_limit or x > right_limit:
                continue
        if core is not None:
            core_x0, core_y0, core_x1, core_y1 = core
            intersects_core = not (
                x + width < core_x0
                or x > core_x1
                or y + height < core_y0
                or y > core_y1
            )
            if not intersects_core:
                continue
        clean[labels == component] = 255
    return clean


def make_layer(base, source, category):
    difference = np.max(
        np.abs(source.astype(np.int16) - base.astype(np.int16)),
        axis=2,
    ).astype(np.uint8)
    difference = cv2.GaussianBlur(difference, (3, 3), 0)
    threshold = 30 if category == "accessories" else 38
    mask = np.where(difference > threshold, 255, 0).astype(np.uint8)

    if category == "bottoms":
        mask[:90] = 0
        mask = filter_components(
            mask,
            core=(44, 94, 116, 174),
        )
    elif category == "shoes":
        mask[:128] = 0
        mask = filter_components(
            mask,
            core=(38, 132, 122, 178),
        )
    else:
        mask = filter_components(
            mask,
            horizontal_limits=(26, 134),
        )

    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    alpha = np.minimum(background_alpha(source), mask)
    layer = cv2.cvtColor(source, cv2.COLOR_BGR2BGRA)
    layer[:, :, 3] = alpha
    return layer


def write_base(base):
    output = cv2.cvtColor(base, cv2.COLOR_BGR2BGRA)
    output[:, :, 3] = background_alpha(base)
    base_directory = OUTPUT_DIRECTORY / "base"
    base_directory.mkdir(parents=True, exist_ok=True)
    path = base_directory / "blonde-character-base.png"
    cv2.imwrite(str(path), output)
    return path


def write_category(base, category, configuration):
    sheet = read_sheet(configuration["path"])
    directory = OUTPUT_DIRECTORY / "clothing" / category
    directory.mkdir(parents=True, exist_ok=True)
    items = []

    for display_index, sheet_index in enumerate(configuration["indices"], start=1):
        source = normalize_cell(
            extract_cell(
                sheet,
                configuration["columns"],
                configuration["rows"],
                sheet_index,
            )
        )
        layer = make_layer(base, source, category)
        item_id = f"{configuration['filename_prefix']}-{display_index:02d}"
        filename = f"{item_id}.png"
        path = directory / filename
        cv2.imwrite(str(path), layer)
        items.append(
            {
                "id": item_id,
                "name": f"{configuration['prefix']} {display_index:02d}",
                "source": path.relative_to(ROOT).as_posix(),
            }
        )

    return items


def main():
    if OUTPUT_DIRECTORY.exists():
        shutil.rmtree(OUTPUT_DIRECTORY)
    OUTPUT_DIRECTORY.mkdir(parents=True)

    accessory_sheet = read_sheet(SHEETS["accessories"]["path"])
    base = normalize_cell(
        extract_cell(
            accessory_sheet,
            SHEETS["accessories"]["columns"],
            SHEETS["accessories"]["rows"],
            0,
        )
    )
    base_path = write_base(base)

    catalog = {
        "base": base_path.relative_to(ROOT).as_posix(),
        "categories": {},
    }
    for category, configuration in SHEETS.items():
        catalog["categories"][category] = write_category(
            base,
            category,
            configuration,
        )

    catalog_path = OUTPUT_DIRECTORY / "clothing-catalog.json"
    catalog_path.write_text(
        json.dumps(catalog, indent=2),
        encoding="utf-8",
    )

    total = sum(len(items) for items in catalog["categories"].values())
    print(f"Generated base and {total} clothing layers in {OUTPUT_DIRECTORY}")


if __name__ == "__main__":
    main()
