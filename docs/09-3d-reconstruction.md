# 3D Reconstruction

## Objective

Reconstruct the 2D segmented slices into a 3D volume to visually and
quantitatively assess how well predicted tumor regions match the
ground-truth tumor volume, and to communicate results in a form more
interpretable than slice-by-slice metrics.

## Why This Step Was Needed

Slice-level and patient-level detection metrics (from the classifier
fusion stage) describe *how many* slices were correctly flagged, but not
*how well-shaped or spatially accurate* the reconstructed tumor volume
is compared to the real tumor geometry. 3D reconstruction turns per-slice
predictions into a coherent volumetric object, which is:
- Easier to visually inspect for shape/location plausibility.
- Directly measurable via 3D-specific metrics (e.g., 3D Dice score),
  which are more relevant to the project's overall goal (3D
  reconstruction of tumor regions) than slice-level accuracy alone.

## Method — Iteration 1

- Stacked all classifier-fused predicted tumor masks across slices into a
  3D volume.
- Rendered the predicted tumor volume (in **red**) overlaid on the
  ground-truth tumor volume (in **green**) for direct visual comparison.
- This first version showed **only the tumor regions themselves** in 3D,
  without the surrounding anatomical context.

## Feedback and Correction

The region-only reconstruction was found insufficient because it gave no
sense of where the tumor sits within the full scan, or what the
surrounding tissue looks like — context that matters for judging whether
a detected region is plausible. The reconstruction was corrected to
include the **full image volume** (all CT slices, not just the segmented
tumor voxels), so viewers could see the tumor overlay in its full
anatomical context.

## Method — Iteration 2 (Corrected)

- Full CT slice volume reconstructed in 3D.
- Predicted tumor mask (red) and ground-truth tumor mask (green) both
  overlaid on the full volume for spatial context.

## Accuracy Evaluation

Once the corrected full-volume reconstruction was available, the key
evaluation question became: **is the detected 3D region accurate enough
to be acceptable?**

- **Acceptability threshold used:** ≥95% accuracy, unless existing
  published work on the same dataset already reports something better —
  in which case matching or approaching the published benchmark would
  also be acceptable.
- **Result:** accuracy came out **below 95%** on the NSCLC-Radiomics
  dataset.
- **Benchmark context:** a review of recent (2026) literature found the
  highest reported **3D Dice score of 0.70** on this same dataset,
  meaning even published state-of-the-art results fall short of a strict
  95% threshold — reframing what "acceptable" should mean for this
  specific dataset and task.

## Interpretation

- The below-95% result is not necessarily a failure of the pipeline in
  isolation — it needs to be read against the fact that recent published
  work on the same dataset also has not exceeded a 3D Dice of ~0.70.
- This raised the open question of whether a different dataset might
  yield better absolute accuracy, though no decision had been made on
  switching datasets as of this writing.

## Outcome / Current Status

- Given the results achieved and their consistency with (or proximity
  to) published benchmarks on the same dataset, the project moved into
  the **paper-writing stage**, treating the current pipeline results as
  sufficient to report and discuss — including the comparison to recent
  literature — rather than continuing indefinite refinement.

## Next Step

See [Results & Next Steps](10-results-and-next-steps.md) for the
consolidated metrics table and current open questions heading into the
conference paper draft.
