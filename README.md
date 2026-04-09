# XFOIL Python Interface

A Python-based interface for [XFOIL](https://web.mit.edu/drela/Public/web/xfoil/), the subsonic airfoil analysis tool developed at MIT. This program automates XFOIL's interactive command-line workflow, sweeps through angles of attack, and generates publication-quality plots — all without the user ever touching XFOIL directly.

Built as a learning project bridging aerodynamic fundamentals and software engineering.

---

## Features

- **Automated AoA sweeps** — specify a range and step size, Python handles the rest
- **Internal convergence stepping** — walks XFOIL in smaller internal steps (0.05°) for better convergence, saves only your desired points
- **Multi-Reynolds number analysis** — run multiple Re numbers sequentially, results stored separately per Re
- **Viscous and inviscid flow** — full viscous boundary layer analysis with transition prediction, or inviscid panel method
- **Full aerodynamic output** — CL, CD, CM, CDp, CDf, and boundary layer transition locations (x_tr top and bottom)
- **Pressure distribution plots** — Cp vs x/c with airfoil geometry overlay and aerodynamic coefficient annotation
- **Multi-AoA Cp plots** — overlay multiple pressure distributions on one graph
- **Multi-Re comparison plots** — CL vs α and drag polar curves for all Reynolds numbers on one graph, always including the current run. Additional polar files can be loaded on top for further comparison
- **Experimental data overlay** — load your own data files and overlay them on comparison plots
- **Append logic** — append new sweep results to existing polar files without overwriting, automatic ascending AoA sort. After appending, plots are generated from the full merged AoA range in the file
- **Pause and resume** — press Ctrl+C during a sweep to pause, continue or save results up to that point
- **Flexible save options** — save polar files (.dat/.txt/.csv), CPWR data files, and plots (.png) with custom filenames
- **Readable terminal output** — results table hides viscous-only columns (CDp, CDf, x_tr) for inviscid runs instead of printing N/A for every row
- **Mathtext plot labels** — all plots use matplotlib mathtext for subscripted coefficient labels (C_L, C_D, C_p, etc.) and Greek symbols (α) without requiring a LaTeX install
- **Landscape drag polars** — drag polar plots rendered in landscape orientation for better readability

---

## Requirements

- Python 3.8+
- [XFOIL](https://web.mit.edu/drela/Public/web/xfoil/) installed on your system (Windows only)
- Dependencies:

```bash
pip install -r requirements.txt
```

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/elijahoantoine/xfoil-interface.git
cd xfoil-interface
```
⚠️ If you fork this repository, replace elijahoantoine with your username.

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Make sure XFOIL is installed. If it's not on your system PATH, the program will prompt you to locate the executable manually via a file browser on first run. If you don't have XFOIL, you can download it from the [MIT XFOIL page](https://web.mit.edu/drela/Public/web/xfoil/).

---

## Usage

```bash
python XFOIL_Interface/main.py
```

The program will walk you through:

1. **Airfoil input** — type a NACA designation (e.g. `naca2412`), paste a path to a `.dat` coordinate file, or press Enter to browse. Coordinate files are validated for content before being accepted
2. **Flow type** — viscous or inviscid
3. **Reynolds number(s)** — enter one or more Re numbers for multi-Re analysis (viscous only)
4. **Mach number** — default 0 (incompressible), max reliable 0.5
5. **Moment center** — x/c location, default 0.25 (quarter-chord)
6. **AoA range** — start, end, and step size, or a single point. Supports both ascending and descending sweeps
7. **Max iterations** — default 1000
8. **Run** — XFOIL runs automatically, results table printed to terminal
9. **Save** — choose which files to save and where

---
## Project Structure

```bash
xfoil-interface/
├── XFOIL_Interface/
│   ├── main.py               # Entry point, user interaction flow, save logic
│   ├── xfoil_interface.py    # XFOIL process management and communication
│   ├── plotting.py           # All matplotlib plot generation
│   ├── airfoil_geometry.py   # Airfoil coordinate reading and geometry plotting
│   ├── utils.py              # Input getters, data parsing, file handling helpers
├── requirements.txt
├── README.md
├── LICENSE
└── .gitignore
```
---

## Known Limitations

- **Windows only** — relies on `pywinpty` for pseudo-terminal emulation to communicate with XFOIL's interactive Fortran process. Linux support would require a different PTY approach (e.g. `ptyprocess`).
- **Internal step size capped at 0.05°** — XFOIL's internal polar accumulation buffer has a practical limit. Using a finer step (e.g. 0.025°) over large AoA ranges can cause truncated results. If your sweep is large, consider splitting it into smaller ranges and using the append feature.
- **High-AoA convergence** — XFOIL is a panel method and struggles post-stall. For sweeps that include deep stall angles, use the descending sweep direction option or split your sweep and append results.
- **Low subsonic only** — XFOIL's compressibility corrections break down above Mach 0.5. Results above this are unreliable.
- **Loaded .dat files** — custom airfoil coordinate files may require clean coordinate distributions for good convergence. Poorly distributed panels will cause convergence issues that XFOIL's `PANE` command can partially mitigate but not always resolve.

---

## Future Work

- Streamlit web interface for browser-based use
- Live updating Cp plot during sweep
- Boundary layer visualization
- Automated convergence recovery using XFOIL's `INIT` command

---

## Contributing

Pull requests are welcome. If you find a bug or want to suggest an improvement, open an issue.

---

## License

MIT License — use it, modify it, build on it.

---

## Acknowledgements

- [XFOIL](https://web.mit.edu/drela/Public/web/xfoil/) by Mark Drela and Harold Youngren, MIT
- Built with Python, matplotlib, numpy, and pywinpty
