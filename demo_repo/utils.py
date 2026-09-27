# utils.py — simple utility functions (low complexity, low churn)


def add(a, b):
    """Return the sum of a and b."""
    return a + b


def subtract(a, b):
    """Return the difference of a and b."""
    return a - b


def multiply(a, b):
    """Return the product of a and b."""
    return a * b


def greet(name: str) -> str:
    """Return a greeting string."""
    if not name:
        return "Hello, stranger!"
    return f"Hello, {name}!"
