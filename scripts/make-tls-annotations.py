#!/usr/bin/env python3
"""
Writes the sample sheet and the spot annotations of the TLS Visium demo (Dawo, Nonchev, Silina,
Zenodo 10.5281/zenodo.14620362, CC BY 4.0) in the shape st-prep reads:

- `samples.csv`: `sample_id, path, tissue, condition` for the 8 Space Ranger folders
  (KC1-3 kidney, LC1-5 lung; `condition` = tissue so the demo compares kidney with lung).
- `annotations.csv`: `sample_id, obs_id, annotation` from each preprocessed h5ad's
  `obs["ground_truth"]` (the authors' manual spot annotation), with the labels spelled out:
  TUM -> Tumor, NOR -> Normal, TLS -> TLS, INFL -> Immune, UNASSIGNED -> Unassigned, and LN
  (lymph node tissue, LC3 only) -> Lymph_node. `obs_id` is the Visium barcode.

Only h5py and the standard library are needed (the h5ad files hold a dense X, so they are
not opened with anndata).

Usage: scripts/make-tls-annotations.py [data/tls-visium]
"""
import collections
import csv
import sys
from pathlib import Path

import h5py

MAP = {"TUM": "Tumor", "NOR": "Normal", "TLS": "TLS", "INFL": "Immune", "UNASSIGNED": "Unassigned",
       "LN": "Lymph_node"}
SAMPLES = [("KC1", "kidney"), ("KC2", "kidney"), ("KC3", "kidney"),
           ("LC1", "lung"), ("LC2", "lung"), ("LC3", "lung"), ("LC4", "lung"), ("LC5", "lung")]


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "data/tls-visium")
    with open(root / "samples.csv", "w", newline="") as fs, open(root / "annotations.csv", "w", newline="") as fa:
        ws = csv.writer(fs)
        ws.writerow(["sample_id", "path", "tissue", "condition"])
        wa = csv.writer(fa)
        wa.writerow(["sample_id", "obs_id", "annotation"])
        for sid, tissue in SAMPLES:
            ws.writerow([sid, f"TLS_VISIUM_USZ/10x_Visium/{sid}", tissue, tissue])
            with h5py.File(root / "TLS_VISIUM_USZ" / "h5ad_preprocessed" / f"{sid}.h5ad") as f:
                barcodes = [b.decode() for b in f["obs"]["_index"][:]]
                g = f["obs"]["ground_truth"]
                cats = [c.decode() for c in g["categories"][:]]
                counts = collections.Counter()
                for barcode, code in zip(barcodes, g["codes"][:]):
                    label = MAP.get(cats[code], cats[code])
                    counts[label] += 1
                    wa.writerow([sid, barcode, label])
            print(sid, tissue, len(barcodes), dict(counts), file=sys.stderr)


if __name__ == "__main__":
    main()
