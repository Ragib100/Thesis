# How image enhancement is done

Script: [`src/enhance_images.py`](../src/enhance_images.py)

## Goal

Given the tumor slices produced by `extract_tumor_slices.py`, improve their
visual contrast/clarity in two different ways — **global** and **local**
enhancement — and compare them, while keeping every output traceable 1:1
back to its original input (same filenames, same folder structure).

## Global enhancement

**Method:** global histogram equalization (`cv2.equalizeHist`).

One transformation is computed from the **entire image's** histogram and
applied uniformly to every pixel. It redistributes intensity values so the
full 0–255 range is used more evenly, which increases overall contrast.

**Tradeoff:** because a single transform is derived from the whole image,
regions that already span a wide intensity range (e.g. bone next to air)
dominate the histogram, while low-contrast structures embedded in more
uniform tissue (like a tumor nodule surrounded by lung tissue) may not
improve much — or the image can look harshly over-contrasted overall.

## Local enhancement

**Method:** scikit-image's adaptive histogram equalization
(`skimage.exposure.equalize_adapthist`), optionally preceded by a light
denoise pass (`cv2.fastNlMeansDenoising`).

Unlike the global method, the image is divided into small tiles, and a
histogram equalization transform is computed **per tile** — then tile
transforms are smoothly interpolated across tile boundaries. This means
contrast is boosted based on *local* structure, so a faint tumor edge against
lung tissue can be enhanced without being washed out by unrelated regions
elsewhere in the image (e.g. bone, external air).

### Why not plain OpenCV CLAHE?

An earlier version used `cv2.createCLAHE` directly. Testing showed it works,
but:
- OpenCV's CLAHE blends tiles with minimal interpolation, which can look
  blocky at tile boundaries.
- It amplifies pixel-level noise along with real contrast, since there's no
  denoising step beforehand.

Switching to `skimage.exposure.equalize_adapthist` (which interpolates
between tiles more smoothly) plus a light denoise pre-pass measurably
improved results in testing — both entropy (a proxy for how many distinct
gray levels are being usefully spread out) and visual cleanliness improved:

| Variant | std | entropy | Notes |
|---|---|---|---|
| Original (no enhancement) | ~12 | ~5.5 | Low contrast baseline |
| OpenCV CLAHE | ~18 | ~6.2 | Blocky, noise amplified |
| Denoise + tuned OpenCV CLAHE | ~11 | ~5.4 | Over-smoothed, lost contrast |
| **scikit-image adaptive** | ~39 | ~7.3 | Cleaner, smoother tile blending |
| **Denoise + scikit-image adaptive** | ~50 | ~7.4 | Best of the tested options |

(Numbers from a synthetic test image used during development — see repo
history/PR discussion for the comparison image. Real CT slices will produce
different absolute numbers, but the same relative ordering is expected.)

This is why `enhance_images.py`'s `local_enhance()` uses denoise +
scikit-image adaptive equalization rather than raw CLAHE.

## Step by step (what the script actually does)

1. Walk every `.png` under `INPUT_DIR` (the `tumor_slices/` output from the
   extraction script), recursively — so it picks up every
   `LUNG1-XXX/image_N/{axial,coronal,sagittal}.png`.
2. For each image:
   - **Global**: `cv2.equalizeHist(img)`
   - **Local**: optionally denoise (`cv2.fastNlMeansDenoising`), then
     `skimage.exposure.equalize_adapthist(img, clip_limit=CLAHE_CLIP_LIMIT)`
3. Save both results into folder trees that **exactly mirror** the input
   structure and filenames, so nothing needs to be renamed or manually
   matched up:
   ```
   tumor_slices_global/LUNG1-001/image_01/axial.png
   tumor_slices_local/LUNG1-001/image_01/axial.png
   ```
4. Compute and print contrast (`std`) and entropy for the original, global,
   and local version of every image, so differences can be checked
   quantitatively, not just by eye.
5. Save a labeled side-by-side comparison image for **every** input file
   (not just a sample), again mirrored into the same folder structure:
   ```
   enhancement_comparisons/LUNG1-001/image_01/axial.png
   ```
   Each comparison image has three panels, left to right: **GLOBAL — INPUT —
   LOCAL**, each with a text label baked into the image so there's no
   ambiguity when reviewing or sharing.

## Tunable parameters

Set at the top of `enhance_images.py`:

| Setting | Meaning | Typical range |
|---|---|---|
| `DENOISE_BEFORE_LOCAL` | whether to denoise before local enhancement | `True`/`False` |
| `DENOISE_STRENGTH` | denoise filter strength (`h` param) | 4 (light) – 10 (strong) |
| `CLAHE_CLIP_LIMIT` | local contrast boost strength | 0.005 (subtle) – 0.03 (strong) |

Stronger `CLAHE_CLIP_LIMIT` values increase local contrast further but can
start amplifying noise again — worth tuning per dataset rather than assuming
one value works everywhere.

## How to judge results

- **Visually**: open the comparison images and check whether the tumor
  boundary is easier to distinguish from surrounding tissue in the LOCAL
  panel vs. GLOBAL, without introducing distracting noise/artifacts.
- **Quantitatively**: higher entropy generally means more of the available
  gray levels are being meaningfully used (more distinguishable detail), but
  it isn't a proxy for "clinically better" — always sanity-check visually.
- **std (standard deviation)** reflects overall contrast spread, but a very
  high std isn't automatically "better" if it's driven by amplified noise
  rather than real structure — this is exactly why global equalization can
  show a high std while looking harsh/over-contrasted.