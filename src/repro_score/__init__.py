"""repro-score: how well a research code repository lets someone reproduce its paper, read from its files."""

__version__ = "0.2.0"

from .checks import Evidence, Item  # noqa: E402
from .repo import Repo  # noqa: E402
from .report import Report, score_repo  # noqa: E402

__all__ = ["Evidence", "Item", "Report", "Repo", "score_repo", "__version__"]
