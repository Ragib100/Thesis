"""
make_test_fixture.py

Synthesise one tiny fake patient — 10 CT slices at 64x64 with a square
"GTV-1" contour on four of them — in the same DICOM + RTSTRUCT layout as
the real TCIA download.

The point is to be able to run and debug a pipeline stage on a laptop in
a second or two, without the 12.6 GB dataset present. The ground truth is
known exactly (slices 3-6, a 20x20 px square at rows/cols 20-40), so a
stage that mangles geometry shows up immediately rather than after an
hour of Kaggle time.

Usage:
    python make_test_fixture.py <output-dir>
    python build_slice_dataset.py --dataset-dir <output-dir> --out-dir /tmp/out --size 64
"""
import os, sys, numpy as np, pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import generate_uid, ExplicitVRLittleEndian, CTImageStorage

root = sys.argv[1]
pdir = os.path.join(root, "LUNG1-999", "study", "ct")
sdir = os.path.join(root, "LUNG1-999", "study", "rt")
os.makedirs(pdir, exist_ok=True); os.makedirs(sdir, exist_ok=True)

ROWS = COLS = 64
NSLICES = 10
DZ, DY, DX = 3.0, 0.98, 0.98
series_uid = generate_uid()
sop_uids = []

for i in range(NSLICES):
    fm = FileMetaDataset()
    fm.MediaStorageSOPClassUID = CTImageStorage
    fm.MediaStorageSOPInstanceUID = generate_uid()
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(None, {}, file_meta=fm, preamble=b"\0"*128)
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = fm.MediaStorageSOPInstanceUID
    sop_uids.append(ds.SOPInstanceUID)
    ds.Modality = "CT"
    ds.SeriesInstanceUID = series_uid
    ds.PatientID = "LUNG1-999"
    ds.ImagePositionPatient = [-250.0, -250.0, i * DZ]
    ds.PixelSpacing = [DY, DX]
    ds.SliceThickness = DZ
    ds.Rows, ds.Columns = ROWS, COLS
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16; ds.BitsStored = 16; ds.HighBit = 15
    ds.PixelRepresentation = 1
    ds.RescaleSlope = 1; ds.RescaleIntercept = -1024
    arr = np.random.randint(200, 900, (ROWS, COLS), dtype=np.int16)
    ds.PixelData = arr.tobytes()
    ds.save_as(os.path.join(pdir, f"1-{i+1:03d}.dcm"), enforce_file_format=True)

# RTSTRUCT: a square GTV on slices 3..6 only
fm = FileMetaDataset()
fm.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.481.3"
fm.MediaStorageSOPInstanceUID = generate_uid()
fm.TransferSyntaxUID = ExplicitVRLittleEndian
rt = FileDataset(None, {}, file_meta=fm, preamble=b"\0"*128)
rt.SOPClassUID = fm.MediaStorageSOPClassUID
rt.SOPInstanceUID = fm.MediaStorageSOPInstanceUID
rt.Modality = "RTSTRUCT"
rt.PatientID = "LUNG1-999"

roi = Dataset(); roi.ROINumber = 1; roi.ROIName = "GTV-1"
roi.ReferencedFrameOfReferenceUID = generate_uid()
lung = Dataset(); lung.ROINumber = 2; lung.ROIName = "Lung-Left"
lung.ReferencedFrameOfReferenceUID = roi.ReferencedFrameOfReferenceUID
rt.StructureSetROISequence = [roi, lung]

contours = []
for zi in range(3, 7):
    z = zi * DZ
    # 20x20 px square starting at pixel (20,20) -> world mm
    pts = []
    for (c, r) in [(20, 20), (40, 20), (40, 40), (20, 40)]:
        pts += [-250.0 + c * DX, -250.0 + r * DY, z]
    ci = Dataset(); ci.ReferencedSOPInstanceUID = sop_uids[zi]
    con = Dataset()
    con.ContourImageSequence = [ci]
    con.ContourGeometricType = "CLOSED_PLANAR"
    con.NumberOfContourPoints = 4
    con.ContourData = pts
    contours.append(con)

rc = Dataset(); rc.ReferencedROINumber = 1; rc.ContourSequence = contours
rt.ROIContourSequence = [rc]
rt.save_as(os.path.join(sdir, "rtstruct.dcm"), enforce_file_format=True)
print(f"fixture written -> {root}  ({NSLICES} CT slices, GTV on 4 of them)")
