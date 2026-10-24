"""Train models (synthetic data by default; swap make_data() for the trips table).
  python ml/train.py          -> Random Forest saved to ml/eta_model.joblib
  python ml/train.py --gru    -> also trains a GRU (needs tensorflow) -> ml/gru_eta.keras"""
import sys, numpy as np, joblib
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
sys.path.insert(0, str(Path(__file__).parent))
from predictor import baseline

def make_data(n=6000, seed=1):
    r = np.random.default_rng(seed); X, y = [], []
    for _ in range(n):
        f = dict(lat=r.uniform(10, 11), lon=r.uniform(76, 77), speed=r.uniform(8, 45),
                 distance=r.uniform(0.3, 15), traffic=int(r.integers(0, 3)),
                 hour=int(r.integers(5, 23)), dow=int(r.integers(0, 7)), hist_speed=r.uniform(15, 35))
        X.append([f["lat"], f["lon"], f["speed"], f["distance"], f["traffic"], f["hour"], f["dow"], f["hist_speed"]])
        y.append(baseline(f) * r.normal(1, 0.08))
    return np.array(X), np.array(y)

if __name__ == "__main__":
    X, y = make_data(); Xt, Xv, yt, yv = train_test_split(X, y, test_size=0.2, random_state=0)
    rf = RandomForestRegressor(200, random_state=0).fit(Xt, yt)
    print("RF MAE (min):", round(mean_absolute_error(yv, rf.predict(Xv)), 2))
    joblib.dump(rf, Path(__file__).parent / "eta_model.joblib")
    if "--gru" in sys.argv:
        from tensorflow import keras  # input: last 6 readings of [speed, distance, traffic]
        S = np.stack([X[:, [2, 3, 4]] * np.random.normal(1, .05, (len(X), 3)) for _ in range(6)], axis=1)
        m = keras.Sequential([keras.layers.GRU(32, input_shape=(6, 3)), keras.layers.Dense(16, activation="relu"), keras.layers.Dense(1)])
        m.compile("adam", "mae"); m.fit(S, y, epochs=5, batch_size=64, validation_split=.2)
        m.save(Path(__file__).parent / "gru_eta.keras")
        print("GRU saved. Load it in predictor.predict_eta() to blend with the Random Forest.")
