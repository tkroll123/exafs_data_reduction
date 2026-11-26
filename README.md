# EXAFS Data Reduction

A small browser-based tool for the first reduction steps of X-ray absorption
(XAS / EXAFS) scans recorded with the **SSRL EXAFS Data Collector**
(e.g. `sample_A.001`), in particular at beamlines 7-3 and 9-3, and reduces
the many fluorescence channels to one spectrum. It runs locally as a Flask web server and is used from
Chrome (or any modern browser).

For each scan it

* reads the SSRL ASCII header and data block (no hard-coded column positions),
* guesses which columns are energy, I0, I1, the reference foil and the
  fluorescence channels (`SCA1_n`, `SCA2_n`, `FFn`, …) — every guess can be changed,
* drops bad fluorescence channels automatically — dead channels, channels with
  zero counts, channels with sudden local drops (e.g. dead-time losses when a
  diffraction peak hits part of the detector) and channels with excess noise —
  and shows the reason; any choice can be overridden by clicking,
* picks the fluorescence detector that actually carries the signal
  (highest edge-jump signal-to-noise) when several are recorded,
* calibrates the energy axis with the reference foil
  (maximum of dμ/dE near the tabulated edge, with Gaussian smoothing and a
  cubic-spline derivative, or the original XAS_Worker method),
* sums the good channels, divides by I0 and multiplies by the mean I0 of the
  scan (`SumRatio = Σ channels / I0 · ⟨I0⟩`, so a weak beam gives a lower weight),
* merges several scans by adding counts (Σ counts / Σ I0 · ⟨I0⟩),
* writes `*_processed.dat` and `*_merged_Nscans.dat` text files whose
  header records every setting used.

The processing logic is a configurable port of
**XAS_Worker** by Leland B. Gee (MIT license).

A full user manual (installation, every menu entry, the algorithms and the
output file format) is in [`docs/manual.pdf`](docs/manual.pdf)
(source: [`docs/manual.tex`](docs/manual.tex)).

---

## Installation

Requirements: **Python 3.9 or newer** and a web browser. Nothing else has to
be installed system-wide; the Python packages go into a local virtual
environment.

```bash
git clone https://github.com/tkroll123/exafs_data_reduction.git
cd exafs_data_reduction
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

On **Windows** (PowerShell or cmd):

```bat
git clone https://github.com/tkroll123/exafs_data_reduction.git
cd exafs_data_reduction
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Running

```bash
.venv/bin/python app.py          # Windows: .venv\Scripts\python app.py
```

Then open <http://127.0.0.1:5050> in the browser. Stop the server with
`Ctrl+C` in the terminal.

On macOS / Linux, `./start.sh` (or `bash start.sh`) does all of this in one step:
it creates the virtual environment on first use, starts the server and opens
the page in Chrome (or the default browser).

The server only listens on `127.0.0.1` (your own computer). Opened scans are
kept in memory and are forgotten when the server stops; your files on disk
are never modified.

## Quick start

1. **Open files…** and select one or more SSRL scan files.
2. Check the **Channels** and **Energy calibration** settings in the left
   menu (they are pre-filled from the file; the foil element is guessed from
   the energy range).
3. Look at the tabs: *Channels / I0* (click a bar to drop a channel),
   *Calibration* (the point used for the edge is marked in red),
   *Summed ratio*.
4. Tick the files you want and use **Download selected** to save one
   `<name>_processed.dat` per file, or **Merge checked** /
   **Download merged** to combine them.

## Repository layout

| Path | Contents |
|------|----------|
| `app.py` | Flask server: open / process / export / merge endpoints |
| `xas_core.py` | Parser and processing (channels, detector choice, calibration, merge, export) |
| `templates/index.html` | The user interface (HTML + JavaScript, plots with Plotly) |
| `docs/manual.tex`, `docs/manual.pdf` | User manual |
| `requirements.txt` | Python dependencies |

## Building the manual

```bash
cd docs
latexmk -pdf manual.tex      # or: pdflatex manual.tex (run twice)
```

## Supported reference foils

Sc, Ti, V, Cr, Mn, Fe, Co, Ni, Cu, Zn K-edges (edit `FOILS` in
`xas_core.py` to add more).

## Acknowledgements

Processing steps follow XAS_Worker by Leland B. Gee
(MIT License, © 2023 Leland B. Gee).
