"""ETA predictor. Uses a trained model if ml/eta_model.joblib exists,
otherwise a clearly labelled rule-based BASELINE (no GRU is running)."""
from pathlib import Path
import math
MODEL_PATH = Path(__file__).parent / "eta_model.joblib"
FEATURES = ["lat", "lon", "speed", "distance", "traffic", "hour", "dow", "hist_speed"]
_model = None
if MODEL_PATH.exists():
    try:
        import joblib
        _model = joblib.load(MODEL_PATH)
    except Exception:
        _model = None

def baseline(f):
    """Distance / effective speed, slowed by traffic and rush hours, blended with history."""
    traffic_factor = [1.0, 0.78, 0.55][int(f["traffic"])]
    rush = 0.9 if (8 <= f["hour"] <= 10 or 17 <= f["hour"] <= 19) and f["dow"] < 5 else 1.0
    eff = max(5.0, (0.6 * f["speed"] + 0.4 * f["hist_speed"]) * traffic_factor * rush)
    stops_penalty = 0.5 * math.floor(f["distance"] / 1.5)  # dwell time at stops
    return f["distance"] / eff * 60 + stops_penalty

def predict_eta(f):
    f = dict(f); f.setdefault("lat", 0.0); f.setdefault("lon", 0.0)
    if _model is not None:
        eta = float(_model.predict([[f[k] for k in FEATURES]])[0])
        label = "Random Forest (trained on synthetic data)"
    else:
        eta = baseline(f)
        label = "Rule-based baseline (simulation: no trained model loaded, GRU not running)"
    scheduled = f["distance"] / 25.0 * 60  # timetable assumes 25 km/h
    return {"eta_min": round(eta, 1), "scheduled_min": round(scheduled, 1),
            "delay_min": round(eta - scheduled, 1), "model": label,
            "trained": _model is not None}
