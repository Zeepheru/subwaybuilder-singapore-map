import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp


def integer_proportional_allocation(
    weights: pd.DataFrame,
    row_totals: pd.Series,
    col_totals: pd.Series,
) -> pd.DataFrame:
    """
    Integer allocation satisfying both row and column totals,
    while minimizing absolute deviation from row-wise proportional targets.

    weights:
        DataFrame whose rows sum to 1.
    row_totals:
        Integer target total per row, indexed like weights.index.
    col_totals:
        Integer target total per column, indexed like weights.columns.

    Returns:
        Integer-valued DataFrame with the same index/columns as weights.
    """
    # Align inputs
    row_totals = row_totals.reindex(weights.index)
    col_totals = col_totals.reindex(weights.columns)

    if row_totals.isna().any() or col_totals.isna().any():
        raise ValueError("row_totals / col_totals must cover all rows/columns")

    W = weights.to_numpy(dtype=float)
    r = row_totals.to_numpy(dtype=int)
    c = col_totals.to_numpy(dtype=int)

    # Basic validation
    if np.any(W < 0):
        raise ValueError("weights must be nonnegative")

    if not np.allclose(W.sum(axis=1), 1):
        raise ValueError("each row of weights must sum to 1")

    if np.any(r < 0) or np.any(c < 0):
        raise ValueError("totals must be nonnegative")

    if r.sum() != c.sum():
        raise ValueError("row_totals.sum() must equal col_totals.sum()")

    n_rows, n_cols = W.shape
    n = n_rows * n_cols

    # Desired real-valued allocation
    target = W * r[:, None]
    target = target.ravel()

    # We minimize sum |x - target|.
    # Introduce auxiliary d >= |x-target|.
    #
    # Variables:
    #   x[0:n]       integer allocation
    #   d[0:n]       continuous absolute deviations
    #
    # objective = sum(d)
    c_obj = np.r_[np.zeros(n), np.ones(n)]

    # Row constraints
    A_row = np.zeros((n_rows, 2 * n))
    for i in range(n_rows):
        start = i * n_cols
        stop = start + n_cols
        A_row[i, start:stop] = 1

    row_constraint = LinearConstraint(A_row, r, r)

    # Column constraints
    A_col = np.zeros((n_cols, 2 * n))
    for j in range(n_cols):
        A_col[j, j:n:n_cols] = 1

    col_constraint = LinearConstraint(A_col, c, c)

    # Absolute-deviation constraints:
    #
    # d >= x - target
    # d >= target - x
    A_abs = np.zeros((2 * n, 2 * n))
    lb_abs = np.full(2 * n, -np.inf)
    ub_abs = np.full(2 * n, np.inf)

    for k in range(n):
        # x - d <= target
        A_abs[2 * k, k] = 1
        A_abs[2 * k, n + k] = -1
        ub_abs[2 * k] = target[k]

        # -x - d <= -target
        A_abs[2 * k + 1, k] = -1
        A_abs[2 * k + 1, n + k] = -1
        ub_abs[2 * k + 1] = -target[k]

    abs_constraint = LinearConstraint(A_abs, lb_abs, ub_abs)

    # x integer, x >= 0
    # d continuous, d >= 0
    integrality = np.r_[np.ones(n), np.zeros(n)]

    bounds = Bounds(
        np.zeros(2 * n),
        np.full(2 * n, np.inf),
    )

    result = milp(
        c=c_obj,
        integrality=integrality,
        bounds=bounds,
        constraints=[
            row_constraint,
            col_constraint,
            abs_constraint,
        ],
    )

    if not result.success:
        raise ValueError(f"No feasible integer allocation: {result.message}")

    x = np.rint(result.x[:n]).astype(int)

    return pd.DataFrame(
        x.reshape(n_rows, n_cols),
        index=weights.index,
        columns=weights.columns,
    )
