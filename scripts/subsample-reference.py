#!/usr/bin/env python3
"""
Makes the scRNA-seq reference of the Cell-type Deconvolution & Niches demo from the Tabula
Sapiens Lymph_Node dataset on CELLxGENE (The Tabula Sapiens Consortium, Science 2022,
doi:10.1126/science.abl4896; CC BY 4.0): raw UMI counts of the 10x cells (Smart-seq2 cells are
dropped: cell2location models UMI counts), at most --per-type cells per `cell_type` (seeded),
ERCC spike-ins dropped, Ensembl ids as var_names and gene symbols in var["feature_name"], and
the obs columns cell2location needs (`cell_type`, `donor_id`, `assay`, `tissue`, `compartment`).

Reads the 4 GB file with h5py row by row, so it needs little memory. Needs h5py, numpy,
scipy, pandas, anndata.

Usage: scripts/subsample-reference.py data/download/tabula-sapiens-lymph-node.h5ad \
           data/lymph-node/reference/tabula-sapiens-lymph-node.h5ad [--per-type 500] [--seed 42]
"""
import argparse
import sys

import anndata as ad
import h5py
import numpy as np
import pandas as pd
import scipy.sparse as sp


def categorical(group, key):
    g = group[key]
    if isinstance(g, h5py.Group):
        cats = np.array([c.decode() if isinstance(c, bytes) else c for c in g["categories"][:]], dtype=object)
        return pd.Categorical.from_codes(g["codes"][:], cats)
    v = g[:]
    return np.array([x.decode() if isinstance(x, bytes) else x for x in v], dtype=object)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("dst")
    p.add_argument("--per-type", type=int, default=500)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()
    rng = np.random.default_rng(a.seed)

    with h5py.File(a.src) as f:
        obs = pd.DataFrame({k: categorical(f["obs"], k) for k in
                            ("cell_type", "donor_id", "assay", "tissue", "compartment")})
        obs.index = categorical(f["obs"], "_index")
        is_10x = obs["assay"].astype(str).str.startswith("10x")
        keep = []
        for ct, idx in obs[is_10x].groupby("cell_type", observed=True).indices.items():
            rows = np.flatnonzero(is_10x.values)[idx]
            if len(rows) > a.per_type:
                rows = np.sort(rng.choice(rows, a.per_type, replace=False))
            keep.extend(rows.tolist())
        keep = np.array(sorted(keep))
        print(f"{len(keep)} of {len(obs)} cells ({is_10x.sum()} 10x), {obs['cell_type'].nunique()} cell types",
              file=sys.stderr)

        raw = f["raw"]
        indptr = raw["X"]["indptr"][:]
        data, indices, ptr = [], [], [0]
        for r in keep:
            s, e = indptr[r], indptr[r + 1]
            data.append(raw["X"]["data"][s:e])
            indices.append(raw["X"]["indices"][s:e])
            ptr.append(ptr[-1] + (e - s))
        n_genes = raw["X"].attrs["shape"][1]
        X = sp.csr_matrix((np.concatenate(data).astype(np.float32), np.concatenate(indices), np.array(ptr)),
                          shape=(len(keep), n_genes))
        var = pd.DataFrame({"feature_name": categorical(raw["var"], "feature_name"),
                            "ercc": raw["var"]["ercc"][:], "mt": raw["var"]["mt"][:]})
        var.index = categorical(raw["var"], "_index")

    assert np.allclose(X.data, np.round(X.data)), "raw.X is not integer counts"
    not_ercc = ~var["ercc"].values
    X = X[:, not_ercc]
    var = var.loc[not_ercc, ["feature_name", "mt"]]
    var["feature_name"] = var["feature_name"].astype(str)
    adata = ad.AnnData(X=X, obs=obs.iloc[keep].copy(), var=var)
    adata.obs["cell_type"] = adata.obs["cell_type"].astype(str).astype("category")
    adata.uns["source"] = {
        "dataset": "Tabula Sapiens - Lymph_Node (CELLxGENE collection e5f58829-1a66-40b5-a624-9046778e74f5, "
                   "dataset 18eb630b-a754-4111-8cd4-c24ec80aa5ec)",
        "doi": "10.1126/science.abl4896", "license": "CC BY 4.0",
        "subsample": f"<= {a.per_type} 10x cells per cell_type, seed {a.seed}, ERCC dropped",
    }
    adata.write_h5ad(a.dst, compression="gzip")
    print(adata, file=sys.stderr)
    print(adata.obs["cell_type"].value_counts().to_string(), file=sys.stderr)


if __name__ == "__main__":
    main()
