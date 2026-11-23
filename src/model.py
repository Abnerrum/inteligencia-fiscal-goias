"""Correlação de Pearson e regressão linear simples por mínimos quadrados."""
import numpy as np
import statsmodels.api as sm


def fit_linear(df, x="frota", y="icms"):
    clean = df[[x, y]].astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 3 or clean[x].nunique() < 2 or clean[y].nunique() < 2:
        raise ValueError("O ajuste requer pelo menos três pares válidos e variação em X e Y.")
    model = sm.OLS(clean[y], sm.add_constant(clean[x], has_constant="add")).fit()
    return {
        "modelo": model,
        "intercepto": float(model.params["const"]),
        "inclinacao": float(model.params[x]),
        "pearson": float(clean[x].corr(clean[y])),
        "r2": float(model.rsquared),
        "mae": float(np.abs(model.resid).mean()),
        "rmse": float(np.sqrt(np.square(model.resid).mean())),
        "n": len(clean),
        "x_min": float(clean[x].min()),
        "x_max": float(clean[x].max()),
    }


def predict(result, x_value):
    return result["intercepto"] + result["inclinacao"] * float(x_value)


def project_trend(values, steps=12, skip=0):
    """Projeta uma série mensal pela reta de tendência, ignorando os primeiros `skip` meses."""
    y = np.asarray(values, dtype=float)
    if not np.isfinite(y).all() or len(y) - skip < 3:
        raise ValueError("A projeção requer pelo menos três meses seguidos e sem lacunas.")
    slope, intercept = np.polyfit(np.arange(skip, len(y)), y[skip:], 1)
    return intercept + slope * np.arange(len(y), len(y) + steps)


def interpret_pearson(r):
    magnitude = abs(r)
    if magnitude == 0:
        return "associação linear nula"
    if magnitude < 0.3:
        strength = "fraca"
    elif magnitude < 0.7:
        strength = "moderada"
    else:
        strength = "forte"
    direction = "positiva" if r > 0 else "negativa"
    return f"associação linear {strength} e {direction}"
