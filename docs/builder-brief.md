# Brief for building an app of the spatial transcriptomics workflows

You are building one or more Pennsieve processor apps, each in its own git repo under
`~/code/pennsieve/<repo>` (remote `git@github.com:pennsieve-apps/<repo>.git`, public). Repo names
carry **no `processor-` prefix** (unlike the older cytometry and iEEG apps): `st-prep`, `st-qc`,
`st-domains`, `st-svg`, `cell2location`, `st-celltype`, `st-niches`, `st-ccc`, `st-compare`,
`st-report`. Refer to sibling apps by these names in READMEs and `sample-input/README.md`. The
apps form three workflows for spatial transcriptomics, meant to be used broadly (any tissue,
human or mouse, sequencing- or imaging-based platforms), not only on the demo data:

- **A. Spatial Domain Mapping & Condition Comparison** (Visium, Visium HD, Slide-seq):
  `st-prep → st-qc → st-domains → {st-svg, st-compare} → st-report`
- **B. Cell-type Deconvolution & Niches** (Visium + a scRNA-seq reference):
  `st-prep → st-qc → cell2location (+ reference input) → st-niches → st-report`
- **C. Single-cell Spatial Profiling** (Xenium, MERSCOPE, CosMx):
  `st-prep → st-qc → st-celltype → {st-niches, st-ccc} → st-report`

## Read first

1. `~/code/pennsieve/workflow-spatial-transcriptomics/docs/conventions.md`: the file and port
   contract between apps. Follow it exactly. If something in it is wrong or missing, say so in
   your report instead of silently diverging.
2. Finished apps to copy layout, tone and level of care from (same organization, earlier
   workflows): `~/code/pennsieve/processor-cytometry-batch-assess` (Python, Lambda-capable:
   `processor/entry.py`, `main.py`, `handler.py`, Makefile, tests, `docker-compose.yml`,
   `dev.env`, README with port table, parameters, runtime section with measured memory,
   `THIRD_PARTY.md`, `CITATION.cff`, `sample-input/README.md`) and
   `~/code/pennsieve/processor-cytometry-report` (the report app: templates, figures, citations
   gathered from every step's provenance). `~/code/pennsieve/processor-fcs-prep` is the prep app
   of the cytometry workflows (sample sheet handling, per-sample streaming).
3. The app manifest schema:
   `~/code/pennsieve/workflow-spatial-transcriptomics/docs/app-manifest.v1.schema.json`.
   Validate `app.yml` against it (`python3.12 -m venv` + `pip install jsonschema pyyaml` in your
   scratch dir). Do NOT add `application.relations`.

## Every repo has

`app.yml` (`# yaml-language-server: $schema=https://schemas.pennsieve.io/app-manifest/v1.json`,
`schemaVersion: "1.0"`, `application` with name/description/type processor/tags, `runtime`
cpu/memory/computeTypes/timeoutSeconds, `parameters`, `inputs`, `outputs`). Tags include the
data domain and research fields: `spatial-transcriptomics`, `transcriptomics`, `genomics`,
`single-cell`, platform tags where specific (`visium`, `xenium`, `merscope`, `cosmx`), plus
task tags (`quality-control`, `clustering`, `deconvolution`, `cell-typing`,
`cell-cell-communication`, `differential-expression`, `report`, ...).

`Dockerfile` (linux/amd64, pinned base image by digest and pinned package versions,
non-interactive, no network at run time, as small as reasonable; `python:3.12-slim` + pinned pip
`requirements.txt`; CPU-only torch from the PyTorch CPU index where torch is needed, never the
CUDA wheels unless the app declares `gpu`), `processor/` code, `tests/` (pytest on a tiny
synthetic fixture, no Docker; `tests/make_fixture.py` writes it), `Makefile` (`test`,
`fixture`, `run` = docker compose over a fixture into `data/output/`, `clean`),
`docker-compose.yml`, `dev.env`, `sample-input/README.md` (how to get real input),
`README.md`, `THIRD_PARTY.md` (every bundled component with its licence), `LICENSE`
(Apache-2.0 for our code; if the image links GPL code in-process, say so in THIRD_PARTY.md
and the README), `VERSION` (`0.1.0`), `CITATION.cff` (below), `.gitignore`.

Light, fast steps (st-svg, st-compare, st-report) declare `computeTypes: [standard, lambda]`
with memory ≤ 3008 MB if they fit, and a `processor/handler.py` Lambda entry like
processor-cytometry-batch-assess. Heavy ones are `standard` only, sized from your measurement;
cell2location declares `[standard, gpu]` and uses the GPU when torch sees one.

Python: 3.12. Core pins (newest on PyPI as of 2026-10-29, check and pin exact versions):
scanpy 1.12.x, anndata 0.13.x, squidpy 1.8.x, scvi-tools 1.5.x, cell2location 0.1.5,
liana 1.10.x, pydeseq2 0.5.x, pybanksy 1.3.x (GPL-3.0), harmonypy 2.1.x, leidenalg 0.12
(igraph is GPL-2+; say so). Use `scanpy.pp.neighbors` + `scanpy.tl.leiden(flavor="igraph",
n_iterations=2)` for clustering.

## README

What the app does and why, for a biologist and for a computational analyst; port table;
parameters table (defaults, what each does); outputs with columns; runtime (cpu/memory chosen
and **measured** peak memory and wall time on the demo data, saying it was amd64 emulation on
an M-series Mac); limitations (what the method cannot tell you); licences; **Citations**.

## Citations: verified, and in CITATION.cff

Every paper or software you cite: authors, title, journal, year, volume:pages, DOI (and PMID if
it has one). Verify each via `https://api.crossref.org/works/<DOI>` (or DataCite for Zenodo /
software DOIs, `https://api.datacite.org/dois/<DOI>`) and, for the PMID,
`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=<DOI>[doi]&retmode=json`
then `esummary`: title, author list and year must match. Never cite something you could not
verify; cite the software repo URL instead.

`CITATION.cff` (CFF 1.2.0): `type: software`, title = app name, abstract, `repository-code`
`https://github.com/pennsieve-apps/<repo>`, license, keywords, **one entity author**
`- name: Pennsieve (University of Pennsylvania)`, no `version`/`date-released`, and
`references:` for every cited work, with **authors exactly as Crossref/DataCite list them** (all
of them, in order, `family-names`/`given-names`; a consortium as `name:`). Validate with
`cffconvert --validate`.

Already verified by the coordinator on Crossref/DataCite (title, first author, journal, year,
volume, pages match; re-check anyway and add PMIDs):

- scanpy: Wolf FA, Angerer P, Theis FJ. Genome Biol 2018;19:15. 10.1186/s13059-017-1382-0
- anndata: Virshup I, et al. JOSS 2024;9(96):4371. 10.21105/joss.04371
- squidpy: Palla G, et al. Nat Methods 2022;19:171-178. 10.1038/s41592-021-01358-2
- SpatialData: Marconato L, et al. Nat Methods 2025;22:58-62. 10.1038/s41592-024-02212-x
- BANKSY: Singhal V, et al. Nat Genet 2024;56:431-441. 10.1038/s41588-024-01664-3
- cell2location: Kleshchevnikov V, et al. Nat Biotechnol 2022;40:661-671. 10.1038/s41587-021-01139-4
- scvi-tools: Gayoso A, et al. Nat Biotechnol 2022;40:163-166. 10.1038/s41587-021-01206-w
- LIANA+: Dimitrov D, et al. Nat Cell Biol 2024;26:1613-1622. 10.1038/s41556-024-01469-w
- CellPhoneDB: Efremova M, et al. Nat Protoc 2020;15:1484-1506. 10.1038/s41596-020-0292-x
- PyDESeq2: Muzellec B, et al. Bioinformatics 2023;39(9):btad547. 10.1093/bioinformatics/btad547
- DESeq2: Love MI, Huber W, Anders S. Genome Biol 2014;15:550. 10.1186/s13059-014-0550-8
- Pseudobulk: Squair JW, et al. Nat Commun 2021;12:5692. 10.1038/s41467-021-25960-2
- Leiden: Traag VA, Waltman L, van Eck NJ. Sci Rep 2019;9:5233. 10.1038/s41598-019-41695-z
- UMAP: McInnes L, Healy J, Saul N, Großberger L. JOSS 2018;3(29):861. 10.21105/joss.00861
- Harmony: Korsunsky I, et al. Nat Methods 2019;16:1289-1296. 10.1038/s41592-019-0619-0
- Moran's I: Moran PAP. Biometrika 1950;37:17-23. 10.1093/biomet/37.1-2.17
- SpatialDE: Svensson V, Teichmann SA, Stegle O. Nat Methods 2018;15:343-346. 10.1038/nmeth.4636
- Spatial clustering benchmark (SDMBench): Yuan Z, et al. Nat Methods 2024;21:712-722. 10.1038/s41592-024-02215-8
- Deconvolution benchmark (Spotless): Sang-aram C, et al. eLife 2024;12:RP88431. 10.7554/eLife.88431
- Integration benchmark: Li B, et al. Nat Methods 2022;19:662-670. 10.1038/s41592-022-01480-9
- CellCharter (niches): Varrone M, et al. Nat Genet 2024;56:74-84. 10.1038/s41588-023-01588-4
- Visium / spatial transcriptomics: Ståhl PL, et al. Science 2016;353:78-82. 10.1126/science.aaf2403
- Xenium demo data paper: Janesick A, et al. Nat Commun 2023;14:8353. 10.1038/s41467-023-43458-x
- Museum of spatial transcriptomics (background): Moses L, Pachter L. Nat Methods 2022;19:534-546. 10.1038/s41592-022-01409-2
- Tabula Sapiens: The Tabula Sapiens Consortium. Science 2022;376:eabl4896. 10.1126/science.abl4896
- TLS Visium demo data: Dawo S, Nonchev K, Silina K. Zenodo 2025. 10.5281/zenodo.14620362 (CC BY 4.0; DataCite)
- 10x Genomics demo datasets (Human Lymph Node Visium; Xenium FFPE Human Breast Cancer Rep1/Rep2):
  cite the 10x dataset pages (CC BY 4.0), no DOI.

## Licences (re-check the LICENSE file of what you bundle)

scanpy, anndata, squidpy, spatialdata, scvi-tools, liana (1.x): BSD-3-Clause. cell2location:
Apache-2.0. pydeseq2: MIT. harmonypy: BSD-3-Clause. pybanksy: GPL-3.0 (an image that bundles it
is GPL as a whole; say so). igraph / leidenalg: GPL-2.0+ / GPL-3.0 (same note; every scanpy image
has them). torch: BSD-3-Clause. Never use code with no licence, non-commercial, or academic-only
terms. Do not copy code from GPL tools into our Apache code; call them as libraries.

## Test on real data

Demo data (read-only, do not modify), under `~/code/pennsieve/workflow-spatial-transcriptomics/data/`:

- `tls-visium/`: 8 Space Ranger 2.1.0 outputs (kidney ×3, lung ×5) + `samples.csv`
  (`sample_id, path, tissue`) + `annotations.csv` (spot labels TLS/Immune/Tumor/Normal/Unassigned).
- `lymph-node/`: `V1_Human_Lymph_Node/` (Space Ranger 1.1.0 layout: `filtered_feature_bc_matrix.h5`,
  `spatial/tissue_positions_list.csv`, `scalefactors_json.json`, images) + `samples.csv`;
  `reference/tabula-sapiens-lymph-node.h5ad` (scRNA-seq, raw counts in `X`, `obs["cell_type"]`,
  gene symbols in `var["feature_name"]` / Ensembl ids as `var_names`).
- `xenium-breast/`: `Rep1/`, `Rep2/` (`cell_feature_matrix.h5`, `cells.parquet`, `cells.csv.gz`,
  `cell_boundaries.parquet`) + `samples.csv`.

Upstream outputs, once other builders produce them, are in
`~/code/pennsieve/workflow-spatial-transcriptomics/data/work/<demo>/<step>/` (e.g.
`data/work/xenium/prep/spatial`, `data/work/tls/qc/spatial`). If what you need isn't there
yet, write a fixture generator in `tests/make_fixture.py` that follows the contract (a small
synthetic sample or two with a few hundred observations, a few genes, a planted spatial
structure) and say so in your report; once the upstream output exists, re-run on it and put
your output under `data/work/<demo>/<step>/` for the builders after you. Local Docker has
8 GB shared with other builders running in parallel: test on subsamples (`MAX_OBS_PER_SAMPLE`
in st-prep, 20k), give `docker run` a `--memory` limit, measure peak memory
(`/sys/fs/cgroup/memory.peak` or `docker stats`), remove your containers, and use
`docker build --platform linux/amd64`.

## Git

`git init -b main` (if not yet a repo), commit with clear messages ending with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, commit as
`-c user.name="Joost Wagenaar" -c user.email="1605953+jwagenaar@users.noreply.github.com"`,
and add the remote `git@github.com:pennsieve-apps/<repo>.git`. **Do not push, tag or create
releases**: the coordinator pushes and releases.

## Report back

Short: repo path, commits, ports and parameters as built, what you ran it on and the results
(numbers), measured memory/time, image size, chosen cpu/memory, citations with DOIs/PMIDs and
how you verified them, deviations from conventions.md, open problems.
