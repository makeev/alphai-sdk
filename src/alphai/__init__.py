"""alphai — Python SDK for the AlphaAI financial-news REST API.

The public surface (``Client``, ``AsyncClient``, models, and errors) is wired up
in later build steps. For now only the version is exported.
"""

from ._version import __version__

__all__ = ["__version__"]
