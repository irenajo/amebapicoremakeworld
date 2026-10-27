# Ameba Pico room prototype

A dependency-free browser prototype using the supplied Ameba Pico references.

Open `index.html` in a browser, click a valid floor position to walk, and click the orange arrow above the avatar to rotate 90 degrees. The **Closet** button opens an original-style wardrobe where clothing can be previewed, equipped, removed, and saved.

The avatar renderer composites assets in this order:

1. Base character
2. Tops and dresses
3. Bottoms
4. Shoes
5. One or more accessories

Processed game images are kept under `assets/generated-game-assets` and organized by character slot. They were extracted from the supplied reference sheets rather than generated with an image model.

Run `python tools/extract_clothing_assets.py`, then `python tools/extract_tops_from_video.py`, and finally `python tools/generate_directional_assets.py` to rebuild the source assets, video-derived brunette base and tops, and four-direction approximations.

Only the video-derived tops are enabled in the closet currently. The blonde montage-derived bottoms, shoes, and accessories are retained as generated references but are disabled because they do not align cleanly with the brunette video character. Matching videos for those categories can be processed with the same approach.

Front-left is mirrored from front-right, and back-left is mirrored from an asset-derived back-right approximation. The rear base and top shading are reconstructed from the supplied Pico front/back and diagonal references; they are not authentic recovered game sprites.
