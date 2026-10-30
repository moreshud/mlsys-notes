# Triton notes and kernels

Published notes and GPU kernel experiments from
[junuxyz/triton-notes](https://github.com/junuxyz/triton-notes), matching commit
`23b5e91`. Only files committed in that public version are included.

- [Triton basics](01.md)
- [HTML version with interactive diagrams](01.html)
- Kernel scripts in `kernels/`
- Benchmark plots and CSV files in `assets/benchmarks/`

## Build and preview

From the `mlsys-notes` repository root:

```sh
python3 labs/triton-notes/tools/build_site.py
python3 -m http.server 8000 --directory labs/triton-notes
```

Open [the local preview](http://localhost:8000/01.html).
The HTML builder uses Python's standard library. Kernel scripts require a GPU
environment with PyTorch and Triton installed.

The standalone repository's GitHub Pages workflow is excluded. The original
published site remains unchanged.
