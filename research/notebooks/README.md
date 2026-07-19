# research/notebooks — exploration

Free-form Jupyter exploration lives here. Notebooks are for *looking* — the
moment an idea is worth testing rigorously, move it into a `research/backtests/<idea>/`
folder that uses the shared `research/lib` engine, so the result is reproducible
and comparable to every other idea.

Start a notebook with the repo root on the path:

```python
import sys; sys.path.insert(0, "..", )  # or run jupyter from the repo root
from research.lib.data_loader import load_bars, resample
from research.lib.backtester import backtest
from research.lib.metrics import compute_metrics, equity_curve
```

Keep `.ipynb_checkpoints/` out of git (already in `.gitignore`).
