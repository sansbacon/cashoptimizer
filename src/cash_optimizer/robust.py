from __future__ import annotations

import numpy as np


def build_error_covariance_from_errors(
    errors: np.ndarray,
    min_overlap: int = 5,
    shrinkage: float = 0.05,
) -> np.ndarray:
    """Build an error covariance matrix from historical errors with NaN support.

    The input matrix is expected as shape (n_samples, n_players). Missing values are
    allowed and handled pairwise.
    """
    if errors.ndim != 2:
        raise ValueError("errors must be a 2D array (n_samples, n_players)")

    samples, n_players = errors.shape
    if samples < 2 or n_players < 1:
        raise ValueError("errors must include at least 2 samples and 1 player")

    cov = np.zeros((n_players, n_players), dtype=float)

    for i in range(n_players):
        col_i = errors[:, i]
        valid_i = ~np.isnan(col_i)
        if valid_i.sum() < 2:
            cov[i, i] = 1e-6
        else:
            var_i = float(np.nanvar(col_i, ddof=1))
            cov[i, i] = max(var_i, 1e-6)

    for i in range(n_players):
        col_i = errors[:, i]
        for j in range(i + 1, n_players):
            col_j = errors[:, j]
            mask = (~np.isnan(col_i)) & (~np.isnan(col_j))
            overlap = int(mask.sum())
            if overlap < min_overlap:
                value = 0.0
            else:
                value = float(np.cov(col_i[mask], col_j[mask], ddof=1)[0, 1])
            cov[i, j] = value
            cov[j, i] = value

    if shrinkage > 0:
        alpha = min(max(float(shrinkage), 0.0), 1.0)
        diag = np.diag(np.diag(cov))
        cov = (1.0 - alpha) * cov + alpha * diag

    return nearest_psd_covariance(cov)


def build_error_covariance_aligned_by_player(
    ordered_player_ids: list[str],
    error_history_by_player_id: dict[str, list[float | None]],
    min_overlap: int = 5,
    shrinkage: float = 0.05,
) -> np.ndarray:
    """Build covariance aligned to optimizer player order.

    ordered_player_ids should match the optimizer's active player order. Missing players
    in error_history_by_player_id are treated as all-NaN historical rows.
    """
    if not ordered_player_ids:
        raise ValueError("ordered_player_ids cannot be empty")

    lengths = {
        len(values)
        for values in error_history_by_player_id.values()
    }
    if len(lengths) > 1:
        raise ValueError("All player error history lists must have the same length")
    history_len = next(iter(lengths), 0)
    if history_len == 0:
        raise ValueError("error_history_by_player_id must include at least one history row")

    cols: list[np.ndarray] = []
    for player_id in ordered_player_ids:
        values = error_history_by_player_id.get(player_id)
        if values is None:
            col = np.full(history_len, np.nan, dtype=float)
        else:
            if len(values) != history_len:
                raise ValueError("All player error history lists must have the same length")
            col = np.array([np.nan if v is None else float(v) for v in values], dtype=float)
        cols.append(col)

    errors = np.column_stack(cols)
    return build_error_covariance_from_errors(
        errors=errors,
        min_overlap=min_overlap,
        shrinkage=shrinkage,
    )


def nearest_psd_covariance(covariance: np.ndarray, min_eigenvalue: float = 1e-8) -> np.ndarray:
    if covariance.ndim != 2 or covariance.shape[0] != covariance.shape[1]:
        raise ValueError("covariance must be a square matrix")

    sym = (covariance + covariance.T) / 2.0
    eigvals, eigvecs = np.linalg.eigh(sym)
    eigvals = np.maximum(eigvals, min_eigenvalue)
    repaired = eigvecs @ np.diag(eigvals) @ eigvecs.T
    repaired = (repaired + repaired.T) / 2.0

    # Preserve original variances when available.
    original_diag = np.diag(sym)
    scale = np.ones_like(original_diag)
    repaired_diag = np.diag(repaired)
    positive = repaired_diag > 0
    scale[positive] = np.sqrt(np.maximum(original_diag[positive], min_eigenvalue) / repaired_diag[positive])
    repaired = (repaired * scale[:, None]) * scale[None, :]
    return (repaired + repaired.T) / 2.0


def covariance_to_correlation(covariance: np.ndarray) -> np.ndarray:
    if covariance.ndim != 2 or covariance.shape[0] != covariance.shape[1]:
        raise ValueError("covariance must be a square matrix")

    std = np.sqrt(np.maximum(np.diag(covariance), 1e-12))
    denom = std[:, None] * std[None, :]
    corr = np.divide(covariance, denom, out=np.zeros_like(covariance), where=denom > 0)
    np.fill_diagonal(corr, 1.0)
    return (corr + corr.T) / 2.0


def nearest_correlation_matrix(correlation: np.ndarray, min_eigenvalue: float = 1e-8) -> np.ndarray:
    if correlation.ndim != 2 or correlation.shape[0] != correlation.shape[1]:
        raise ValueError("correlation must be a square matrix")

    sym = (correlation + correlation.T) / 2.0
    eigvals, eigvecs = np.linalg.eigh(sym)
    eigvals = np.maximum(eigvals, min_eigenvalue)
    repaired = eigvecs @ np.diag(eigvals) @ eigvecs.T

    d = np.sqrt(np.maximum(np.diag(repaired), 1e-12))
    repaired = repaired / (d[:, None] * d[None, :])
    np.fill_diagonal(repaired, 1.0)
    return (repaired + repaired.T) / 2.0


def matrix_sqrt_psd(covariance: np.ndarray, min_eigenvalue: float = 1e-8) -> np.ndarray:
    cov = nearest_psd_covariance(covariance, min_eigenvalue=min_eigenvalue)
    eigvals, eigvecs = np.linalg.eigh(cov)
    eigvals = np.maximum(eigvals, min_eigenvalue)
    sqrt_cov = eigvecs @ np.diag(np.sqrt(eigvals)) @ eigvecs.T
    return (sqrt_cov + sqrt_cov.T) / 2.0


def sparsify_covariance_by_correlation_threshold(
    covariance: np.ndarray,
    correlation_threshold: float,
    min_eigenvalue: float = 1e-8,
) -> np.ndarray:
    """Zero weak off-diagonal correlations and return PSD-repaired covariance."""
    if covariance.ndim != 2 or covariance.shape[0] != covariance.shape[1]:
        raise ValueError("covariance must be a square matrix")
    threshold = float(correlation_threshold)
    if threshold < 0 or threshold > 1:
        raise ValueError("correlation_threshold must be in [0, 1]")
    if threshold == 0:
        return nearest_psd_covariance(covariance, min_eigenvalue=min_eigenvalue)

    corr = covariance_to_correlation(covariance)
    mask = np.abs(corr) < threshold
    np.fill_diagonal(mask, False)

    std = np.sqrt(np.maximum(np.diag(covariance), min_eigenvalue))
    sparse_corr = corr.copy()
    sparse_corr[mask] = 0.0
    sparse_corr = nearest_correlation_matrix(sparse_corr, min_eigenvalue=min_eigenvalue)
    sparse_cov = (sparse_corr * std[:, None]) * std[None, :]
    return nearest_psd_covariance(sparse_cov, min_eigenvalue=min_eigenvalue)
