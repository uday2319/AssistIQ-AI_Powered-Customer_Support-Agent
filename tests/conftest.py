import os

# Tests keep conversations in memory so they don't need a database.
# This runs before any test imports the graph.
os.environ["CHECKPOINT_BACKEND"] = "memory"
