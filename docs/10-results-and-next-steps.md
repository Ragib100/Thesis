# Results Summary & Next Steps

## Consolidated Pipeline Results

| Stage | Slice-level Detection | Patient-level Detection | Dice | IoU | Precision | Recall |
|---|---|---|---|---|---|---|
| Single-patient U-Net validation | 100% (21/21 TP), 23 false-positive slices | — | — | — | — | 100% (on tested patient) |
| Full-dataset U-Net (raw) | 71.62% | — | 0.65 | — | — | 71.62% |
| + Stacked generalization (ensemble) | 73.16% (93% with lowered threshold, at cost of false positives) | — | 0.77 | 0.63 | 82.32% | 73.16% |
| + Classifier fusion pipeline | 82.12% | 95.25% | — | — | — | — |
| 3D reconstruction (full volume) | Below 95% target 3D accuracy | — | — | — | — | — |

*Note: some cells are intentionally left blank where that specific metric
was not reported at that stage; refer to the individual stage documents
for full context.*

## Benchmark Context

- Recent literature (2026) on the NSCLC-Radiomics dataset reports a
  highest 3D Dice score of **0.70** for tumor segmentation/reconstruction
  — the current project's results should be interpreted relative to this
  published ceiling, not only against an absolute 95% target.

## Key Decisions Made Along the Way

1. **Dataset choice** was grounded in literature precedent (most 3D lung
   cancer reconstruction papers use LIDC-IDRI or NSCLC-Radiomics), not
   just data availability.
2. **Local enhancement** was preferred over global enhancement, with
   iterative parameter tuning validated by side-by-side comparison
   tables against prior results.
3. **Opening by reconstruction** (diamond SE, post-enhancement) was
   preferred over plain morphological opening for better shape
   preservation of tumor regions.
4. **U-Net** was preferred over mean shift segmentation based on
   comparison against ground truth.
5. When raw U-Net full-dataset performance (71.62% detection) fell short
   of the single-patient pilot's implied target (90–100%), **stacked
   generalization** was introduced to improve precision/Dice, though it
   only marginally improved recall.
6. Recognizing that the classification stage could not compensate for
   underlying segmentation gaps, the **classifier fusion pipeline** was
   introduced to filter false-positive regions before final mask fusion,
   substantially improving both slice- and patient-level detection.
7. 3D reconstruction was corrected from tumor-region-only visualization
   to **full-volume visualization** for proper anatomical context.
8. Below-95% 3D accuracy was contextualized against recent published
   benchmarks (3D Dice 0.70) rather than treated as an isolated failure.

## Open Questions Going Into Paper Drafting

- Whether to explore an alternative dataset to potentially improve
  absolute 3D reconstruction accuracy, or to proceed with current
  results framed against the published benchmark ceiling.
- Whether further segmentation refinement (beyond classifier fusion) is
  worth pursuing before finalizing results for publication, or whether
  current results are sufficient given the field's current benchmark
  ceiling.

## Current Status

The project has been instructed to begin preparing a conference paper
based on the pipeline and results documented here:
**Dataset selection → Image enhancement → Morphological processing →
Segmentation (U-Net) → Stacked generalization → Classifier fusion →
3D reconstruction**, benchmarked against recent (2026) published results
on the NSCLC-Radiomics dataset.

## Suggested Paper Structure (Draft Starting Point)

1. Introduction & Motivation (3D tumor reconstruction for lung cancer)
2. Related Work (brief benchmark comparison, esp. the 2026 paper with
   3D Dice 0.70)
3. Dataset (NSCLC-Radiomics description)
4. Methodology
   - Preprocessing: enhancement (global vs. local)
   - Morphological processing (opening by reconstruction)
   - Segmentation: U-Net
   - Ensemble refinement: stacked generalization
   - Classifier fusion pipeline
5. Experimental Results (tables above, plus 3D reconstruction figures)
6. Discussion (comparison to published benchmark, limitations)
7. Conclusion & Future Work (e.g., alternative datasets, further
   segmentation refinement)
