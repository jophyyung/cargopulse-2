"""Independent post-solve verifier: deliberately does not import the optimizer."""

from .validator import validate_solution_independently

__all__ = ["validate_solution_independently"]
