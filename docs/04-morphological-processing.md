# Morphological Processing

## Objective

Clean up enhanced CT slices so that candidate tumor regions become more
clearly separable from noise and surrounding structures, as a bridge
between enhancement and segmentation.

## Why This Step Was Needed

Enhancement improves contrast but can also amplify small noise artifacts.
Morphological operations (which act on the shape/structure of bright or
dark regions in an image) help suppress small irrelevant noise while
preserving larger, meaningful structures like tumor regions. This makes
subsequent segmentation more reliable.

## Method Progression

### 1. Morphological Opening
- **What:** Erosion followed by dilation, using a structuring element
  (SE), applied to remove small bright noise spots while preserving
  larger structures.
- **Why:** Chosen as a simple first attempt at noise suppression before
  moving to more complex approaches; a color-filter approach was kept as
  a fallback if opening did not work well.
- **SE sizes tested:** 3×3, 5×5, 7×7.

### Clarifying Where to Apply Opening
A key question arose: should opening be applied to the **original**
images or the **enhanced** images from the previous stage?

**Decision:** Opening must be applied to the enhanced images. Applying it
to the original, unenhanced images would make the enhancement step
pointless — the whole reason for enhancing first is so that subsequent
processing operates on higher-contrast, more separable input.

### 2. Diamond-Shaped Structuring Element
- Instead of a standard square SE, a **small diamond-shaped SE** was
  recommended. Diamond-shaped elements can better preserve the rounded,
  irregular boundaries typical of anatomical/tumor structures compared to
  square elements, while still suppressing small noise.

### 3. Opening by Reconstruction
- **What:** A refinement of standard opening where, after an initial
  erosion, the image is reconstructed by repeated dilation constrained by
  the original image. This better preserves the shape and boundary of
  larger regions (like a tumor) compared to plain opening, which can
  distort object boundaries.
- **Why:** Standard opening can still degrade the shape of the regions of
  interest; opening by reconstruction is a more shape-preserving
  alternative, which matters since accurate tumor boundary shape affects
  downstream volumetric/3D accuracy.
- **Parameters used:**
  - CLAHE clip limit: **1.5**
  - CLAHE tile grid size: **8×8**
  - Structuring element: **3×3 diamond**

## Verification Step

Before results were shared onward, a verification step was introduced:
processed regions had to be **visually confirmed as clearly separable to
the human eye** first. This was checked by:
1. Comparing consecutive processed slices against the dataset's ground
   truth tumor annotations.
2. Confirming that visible bright regions in the processed CT images
   correspond spatially to the annotated tumor regions in the ground
   truth.

This qualitative check passed — tumor regions were visibly distinguishable
and consistent with ground-truth annotations across consecutive slices.

## Outcome

- Opening by reconstruction (diamond SE, applied post-enhancement) was
  confirmed as an effective preprocessing step: tumor regions became
  visibly more separable than in the original images.
- This visual confirmation justified moving on to formal segmentation
  rather than further morphological tuning.

## Next Step

Proceed to [Segmentation Methods](05-segmentation-methods.md) — mean
shift segmentation and U-Net segmentation, applied to the morphologically
processed images.
