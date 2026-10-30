# Spatial transcriptomics workflows on Pennsieve

Four end-to-end workflows for spatial transcriptomics, built from reusable, open-source Pennsieve
apps. They cover the questions most spatial studies ask, on both kinds of platform: sequencing-based
(10x Visium, Visium HD, Slide-seq), where an observation is a spot or bin holding several cells, and
imaging-based (10x Xenium, Vizgen MERSCOPE, NanoString CosMx), where it is a segmented cell. They follow
the practice set out in the scverse best-practices guide (Heumos et al. 2023) and the spatial analysis
landscape reviewed by Moses & Pachter (2022).

| Workflow | Question it answers | Data | Definition |
|---|---|---|---|
| **Spatial Domain Mapping & Condition Comparison** | What are the tissue's domains, which genes are spatially patterned, and what differs between conditions within each domain? | Visium, Visium HD, Slide-seq | `workflow/spatial-domain-mapping.json` |
| **Cell-type Deconvolution & Niches** | Which cell types make up each spot, which co-locate, and how are they organised? | Visium + a scRNA-seq reference | `workflow/cell-type-deconvolution-niches.json` (CPU) and `workflow/cell-type-deconvolution-niches-gpu.json` (GPU) |
| **Single-cell Spatial Profiling** | Which cell types are where, which neighbourhoods do they form, and how do they signal to each other? | Xenium, MERSCOPE, CosMx | `workflow/single-cell-spatial-profiling.json` |

## Spatial Domain Mapping & Condition Comparison

```
spatial ─► st-prep ─► st-qc ─┬─► st-domains ─► st-compare ─┐
              │ metadata     └─► st-svg ───────────────────┼─► st-report
              └──────────── (metadata to every step) ──────┘
```

1. Read Space Ranger output (h5 or MTX), Visium HD bins or AnnData into one AnnData per sample.
2. Filter low-quality spots by robust outlier detection, normalize, and select HVGs.
3. Find spatial domains shared across sections with BANKSY (Singhal et al. 2024): each spot's expression
   is augmented with its neighbourhood's, sections are integrated with Harmony, and Leiden clusters the
   result. Each domain gets marker genes, sample coverage, and, when spots are annotated, agreement
   with the annotation.
4. Rank spatially variable genes per section by Moran's I, with a consensus across sections.
5. Test each domain's abundance between conditions and run pseudobulk differential expression per domain
   (PyDESeq2), the approach that keeps false discoveries in check (Squair et al. 2021).
6. Write a report.

## Cell-type Deconvolution & Niches

```
spatial ───► st-prep ─► st-qc ─► cell2location ─► st-niches ─┐
                 │ metadata          ▲                        ├─► st-report
reference ───────┼───────────────────┘                        │
                 └──────── (metadata to every step) ──────────┘
```

1. and 2. as above.
3. Estimate reference signatures from the scRNA-seq reference and map every spot's cell-type abundance
   with cell2location (Kleshchevnikov et al. 2022), one of the two best-performing deconvolution
   methods in independent benchmarks (Li et al. 2022; Sang-aram et al. 2024). Report per-spot
   abundances, co-location groups (cell types that occur together), and each spot's strongest group.
4. Score neighbourhood enrichment, co-occurrence and cellular niches of the co-location groups. (A
   spot's single dominant cell type is reported too, but with a fine-grained reference and about 7
   cells per spot, most spots have none, so the groups are the label used here.)
5. Write a report.

The workflow comes in two versions, one per cell2location variant: the **CPU** workflow runs
cell2location on a standard node with 5,000 training epochs (about 2 h for a 4,000-spot section on
4 vCPU); the **GPU** workflow runs its CUDA build on a GPU node with the tutorial's 30,000 epochs.
Use the GPU workflow wherever the compute node has GPUs.

## Single-cell Spatial Profiling

```
spatial ─► st-prep ─► st-qc ─► st-celltype ─┬─► st-niches ─┐
              │ metadata                    └─► st-ccc ────┼─► st-report
              └──────────── (metadata to every step) ──────┘
```

1. and 2. as above, with the platform's negative-control counts as an extra QC measure.
3. Cluster cells across samples (Harmony, Leiden) and label clusters from canonical marker sets checked
   against PanglaoDB (Franzén et al. 2019), or from your own `markers.csv`.
4. Score neighbourhood enrichment and co-occurrence between cell types, and find cellular niches from each
   cell's neighbourhood composition (after Schürch et al. 2020 and CellCharter, Varrone et al. 2024).
5. Infer ligand–receptor communication between cell types with LIANA+ (Dimitrov et al. 2024), and test
   which pairs are spatially co-expressed.
6. Write a report.

## Apps

All apps are in the [`pennsieve-apps`](https://github.com/pennsieve-apps) GitHub organization, released
to the Pennsieve App Store, and documented in their own README: method, ports, parameters, measured
runtime and memory, licences and citations. Unlike the earlier cytometry and iEEG apps, their names
carry no `processor-` prefix.

| Step | App | Tool | What it does; runtime on the demo |
|---|---|---|---|
| prep | [st-prep](https://github.com/pennsieve-apps/st-prep) | scanpy, h5py, pyarrow | Visium (h5/MTX), Visium HD, Xenium, MERSCOPE, CosMx, h5ad, SpatialData into one AnnData per sample; 22–60 s |
| qc | [st-qc](https://github.com/pennsieve-apps/st-qc) | scanpy | MAD or fixed thresholds, normalization, HVGs, PCA; 16–67 s |
| domains | [st-domains](https://github.com/pennsieve-apps/st-domains) | BANKSY, Harmony, Leiden | Spatial domains shared across sections; 3.1 min (8 Visium sections) |
| svg | [st-svg](https://github.com/pennsieve-apps/st-svg) | squidpy | Moran's I per section and consensus; 39–43 s (can run as Lambda) |
| compare | [st-compare](https://github.com/pennsieve-apps/st-compare) | PyDESeq2, SciPy | Composition and pseudobulk DE between conditions per label; 2 min (can run as Lambda) |
| deconvolution | [cell2location](https://github.com/pennsieve-apps/cell2location) | cell2location, scvi-tools | Reference signatures, per-spot abundances, co-location groups; two variants: `cpu` (default) and `gpu`; ~2 h on 4 vCPU at 5,000 epochs |
| celltype | [st-celltype](https://github.com/pennsieve-apps/st-celltype) | scanpy, Harmony, Leiden | Clusters and marker-based cell types; 3.5 min (285 k cells) |
| niches | [st-niches](https://github.com/pennsieve-apps/st-niches) | squidpy, scikit-learn | Neighbourhood enrichment, co-occurrence, niches; 35 s (lymph node) to 58 s (285 k cells) |
| ccc | [st-ccc](https://github.com/pennsieve-apps/st-ccc) | LIANA+ | Ligand–receptor consensus and spatial bivariate scores; 88 s (285 k cells) |
| report | [st-report](https://github.com/pennsieve-apps/st-report) | pandas, matplotlib, Jinja2 | Offline HTML report and tables for any of the workflows; 3–9 s (can run as Lambda) |

Runtimes were measured under amd64 emulation on an Apple-silicon Mac. Every step loops over all the
samples it receives, so one run processes the whole study.

The apps share one contract for files and ports, described in [`docs/conventions.md`](docs/conventions.md):

- One AnnData `.h5ad` per sample with raw counts, coordinates, images and QC metrics.
- A `samples.csv` sample sheet and `prep.json` in the metadata port.
- `labels.csv` (`sample_id, obs_id, <label>`) from every app that labels observations, so st-niches,
  st-ccc and st-compare work on domains, cell types or deconvolved types alike.

## Workflow interface

**Inputs.** `spatial`: a folder with one platform output per sample (or `.h5ad` / `.zarr` files), an
optional `samples.csv` (`sample_id, path, condition, ...`; when present, only its rows are samples) and an
optional `annotations.csv` (`sample_id, obs_id, annotation`). Cell-type Deconvolution & Niches also takes
`reference`: an `.h5ad` of single-cell RNA-seq from the same tissue, with raw counts and a `cell_type`
column. Single-cell Spatial Profiling reads an optional `markers.csv` next to the data.

**Outputs.** Each workflow binds its report, tables and main results to `derivatives/<workflow>/...`
folders by default (see the definitions); the QC'd AnnData files are offered without a default
destination.

**Defaults set for the demos.** Change these per step for your own study:
- st-compare: `CONDITION_COLUMN=tissue` (the TLS demo compares kidney with lung).
- st-niches: `LABEL_COLUMN=colocation_group` after cell2location, `cell_type` after st-celltype.
- cell2location: `N_CELLS_PER_LOCATION=8` suits 55 µm Visium spots; use 1–3 for Visium HD 8 µm bins.

## Platform features exercised

- Named, linked ports with subfolder placement.
- Links that skip levels: prep's metadata goes to every step.
- A second workflow input (the scRNA-seq reference) joining mid-pipeline.
- Fan-out and fan-in DAGs.
- One app (st-niches, st-report) serving several workflows on different labels.
- Lambda-capable steps next to Fargate steps.
- An app with two variants from one release (cell2location `cpu` and `gpu`), and a workflow per variant.
- A workflow interface whose outputs are bound to dataset folders at run time.

## Demo data

All CC BY 4.0. `scripts/fetch-sample-data.sh [tls|lymph|xenium|all]` downloads them into `data/`, checks
every file's checksum, and writes the sample sheets, the TLS annotations and the subsampled reference.

- **TLS kidney and lung tumours (Visium).** Dawo S, Nonchev K, Silina K. *10x Visium Spatial
  Transcriptomics Dataset: Kidney (3) and Lung (5) Cancer with Tertiary Lymphoid Structures.* Zenodo
  (2025). https://doi.org/10.5281/zenodo.14620362. Eight FFPE sections, Space Ranger 2.1.0, with the
  authors' spot annotations (TLS, Immune, Tumor, Normal, Lymph node, Unassigned), 2.1 GB. Used for
  Spatial Domain Mapping & Condition Comparison (kidney vs lung).
- **Human lymph node (Visium).** 10x Genomics, *Human Lymph Node*, Space Ranger 1.1.0, 4,035 spots.
  With a reference of 7,296 cells (≤ 500 per type, 10x cells only) drawn from the Tabula Sapiens
  Lymph_Node dataset on CELLxGENE (The Tabula Sapiens Consortium 2022). The pairing of the cell2location
  tutorial. Used for Cell-type Deconvolution & Niches.
- **Breast cancer (Xenium).** 10x Genomics, *FFPE Human Breast Cancer*, Xenium Onboard Analysis 1.0.1,
  replicates 1 and 2 (Janesick et al. 2023): 313-gene panel, 167,780 and 118,752 cells. Used for
  Single-cell Spatial Profiling.

## Run locally (no Pennsieve account needed)

```
scripts/fetch-sample-data.sh all
scripts/run-local.sh a data/tls-visium data/run-a
REFERENCE=data/lymph-node/reference/tabula-sapiens-lymph-node.h5ad scripts/run-local.sh b data/lymph-node data/run-b
scripts/run-local.sh c data/xenium-breast data/run-c
MAX_OBS_PER_SAMPLE=20000 scripts/run-local.sh c data/xenium-breast data/quick   # quick run
```

The script builds each app from the sibling checkouts (`../st-prep`, ..., `../cell2location`). It
assembles every step's `INPUT_DIR` from the linked outputs, the way a compute node does, and prints where
the report is.

Regenerate the workflow definitions after releasing an app or changing its resources (each step pins the
release tag of its sibling repo's checked-out commit, and memory is rounded up to a Fargate size):

```
scripts/build-workflows.py
```

## Citations

- **Background and practice**
  - Ståhl PL, Salmén F, Vickovic S, et al. Visualization and analysis of gene expression in tissue sections by spatial transcriptomics. *Science* 2016;353(6294):78-82. doi:10.1126/science.aaf2403. PMID 27365449.
  - Moses L, Pachter L. Museum of spatial transcriptomics. *Nat Methods* 2022;19(5):534-546. doi:10.1038/s41592-022-01409-2. PMID 35273392.
  - Heumos L, Schaar AC, Lance C, et al. Best practices for single-cell analysis across modalities. *Nat Rev Genet* 2023;24(8):550-572. doi:10.1038/s41576-023-00586-w. PMID 37002403.
- **Data structures and core tools**
  - Wolf FA, Angerer P, Theis FJ. SCANPY: large-scale single-cell gene expression data analysis. *Genome Biol* 2018;19(1):15. doi:10.1186/s13059-017-1382-0. PMID 29409532.
  - Virshup I, Rybakov S, Theis FJ, Angerer P, Wolf FA. anndata: Access and store annotated data matrices. *J Open Source Softw* 2024;9(101):4371. doi:10.21105/joss.04371.
  - Palla G, Spitzer H, Klein M, et al. Squidpy: a scalable framework for spatial omics analysis. *Nat Methods* 2022;19(2):171-178. doi:10.1038/s41592-021-01358-2. PMID 35102346.
  - Marconato L, Palla G, Yamauchi KA, et al. SpatialData: an open and universal data framework for spatial omics. *Nat Methods* 2025;22(1):58-62. doi:10.1038/s41592-024-02212-x. PMID 38509327.
- **Spatial domains and spatially variable genes**
  - Singhal V, Chou N, Lee J, et al. BANKSY unifies cell typing and tissue domain segmentation for scalable spatial omics data analysis. *Nat Genet* 2024;56(3):431-441. doi:10.1038/s41588-024-01664-3. PMID 38413725.
  - Korsunsky I, Millard N, Fan J, et al. Fast, sensitive and accurate integration of single-cell data with Harmony. *Nat Methods* 2019;16(12):1289-1296. doi:10.1038/s41592-019-0619-0. PMID 31740819.
  - Traag VA, Waltman L, van Eck NJ. From Louvain to Leiden: guaranteeing well-connected communities. *Sci Rep* 2019;9(1):5233. doi:10.1038/s41598-019-41695-z. PMID 30914743.
  - Yuan Z, Zhao F, Lin S, et al. Benchmarking spatial clustering methods with spatially resolved transcriptomics data. *Nat Methods* 2024;21(4):712-722. doi:10.1038/s41592-024-02215-8. PMID 38491270.
  - Moran PAP. Notes on Continuous Stochastic Phenomena. *Biometrika* 1950;37(1-2):17-23. doi:10.1093/biomet/37.1-2.17.
  - Svensson V, Teichmann SA, Stegle O. SpatialDE: identification of spatially variable genes. *Nat Methods* 2018;15(5):343-346. doi:10.1038/nmeth.4636. PMID 29553579.
- **Deconvolution and cell typing**
  - Kleshchevnikov V, Shmatko A, Dann E, et al. Cell2location maps fine-grained cell types in spatial transcriptomics. *Nat Biotechnol* 2022;40(5):661-671. doi:10.1038/s41587-021-01139-4. PMID 35027729.
  - Gayoso A, Lopez R, Xing G, et al. A Python library for probabilistic analysis of single-cell omics data. *Nat Biotechnol* 2022;40(2):163-166. doi:10.1038/s41587-021-01206-w. PMID 35132262.
  - Li B, Zhang W, Guo C, et al. Benchmarking spatial and single-cell transcriptomics integration methods for transcript distribution prediction and cell type deconvolution. *Nat Methods* 2022;19(6):662-670. doi:10.1038/s41592-022-01480-9. PMID 35577954.
  - Sang-aram C, Browaeys R, Seurinck R, Saeys Y. Spotless, a reproducible pipeline for benchmarking cell type deconvolution in spatial transcriptomics. *eLife* 2024;12:RP88431. doi:10.7554/eLife.88431. PMID 38787371.
  - Franzén O, Gan LM, Björkegren JLM. PanglaoDB: a web server for exploration of mouse and human single-cell RNA sequencing data. *Database* 2019;2019:baz046. doi:10.1093/database/baz046. PMID 30951143.
- **Niches and cell–cell communication**
  - Schürch CM, Bhate SS, Barlow GL, et al. Coordinated Cellular Neighborhoods Orchestrate Antitumoral Immunity at the Colorectal Cancer Invasive Front. *Cell* 2020;182(5):1341-1359.e19. doi:10.1016/j.cell.2020.07.005. PMID 32763154.
  - Varrone M, Tavernari D, Santamaria-Martínez A, Walsh LA, Ciriello G. CellCharter reveals spatial cell niches associated with tissue remodeling and cell plasticity. *Nat Genet* 2024;56(1):74-84. doi:10.1038/s41588-023-01588-4. PMID 38066188.
  - Dimitrov D, Schäfer PSL, Farr E, et al. LIANA+ provides an all-in-one framework for cell–cell communication inference. *Nat Cell Biol* 2024;26(9):1613-1622. doi:10.1038/s41556-024-01469-w. PMID 39223377.
- **Differential expression between conditions**
  - Love MI, Huber W, Anders S. Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2. *Genome Biol* 2014;15(12):550. doi:10.1186/s13059-014-0550-8. PMID 25516281.
  - Muzellec B, Teleńczuk M, Cabeli V, Andreux M. PyDESeq2: a python package for bulk RNA-seq differential expression analysis. *Bioinformatics* 2023;39(9):btad547. doi:10.1093/bioinformatics/btad547. PMID 37669147.
  - Squair JW, Gautier M, Kathe C, et al. Confronting false discoveries in single-cell differential expression. *Nat Commun* 2021;12(1):5692. doi:10.1038/s41467-021-25960-2. PMID 34584091.
- **Demo data**
  - Dawo S, Nonchev K, Silina K. 10x Visium Spatial Transcriptomics Dataset: Kidney (3) and Lung (5) Cancer with Tertiary Lymphoid Structures. Zenodo 2025. doi:10.5281/zenodo.14620362 (CC BY 4.0).
  - Janesick A, Shelansky R, Gottscho AD, et al. High resolution mapping of the tumor microenvironment using integrated single-cell, spatial and in situ analysis. *Nat Commun* 2023;14(1):8353. doi:10.1038/s41467-023-43458-x. PMID 38114474.
  - The Tabula Sapiens Consortium. The Tabula Sapiens: A multiple-organ, single-cell transcriptomic atlas of humans. *Science* 2022;376(6594):eabl4896. doi:10.1126/science.abl4896. PMID 35549404.
  - 10x Genomics. Human Lymph Node (Visium, Space Ranger 1.1.0) and FFPE Human Breast Cancer (Xenium, Rep1/Rep2). https://www.10xgenomics.com/datasets (CC BY 4.0).

Every DOI was checked on Crossref (DataCite for Zenodo) and every PMID on PubMed: title, authors, journal
and year match. `CITATION.cff` carries the full author lists. Each app's README lists the full set for its
step.

## Licence

The workflow definitions, scripts and docs in this repository are Apache-2.0. Each app states its own
licence, and its image includes third-party components under their licences. The images of st-domains
and st-celltype are GPL-3.0 as a whole (pybanksy, harmonypy, igraph); each app's `THIRD_PARTY.md` lists
its components.
