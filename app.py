"""SmartBus AI - Flask backend. Run: python app.py"""
import os, math, random, sqlite3, time, datetime as dt
from pathlib import Path
from flask import Flask, jsonify, request, render_template
from ml.predictor import predict_eta

app = Flask(__name__)
DB = Path(__file__).parent / "data" / "smartbus.db"

# ---- Demo network (map coordinates on a 0-100 grid; 1 unit ~ 0.2 km) ----
ROUTES = {
 "R1": {"name": "Central Station - Tech Park", "stops": [("Central Station",10,80),("Market Road",25,62),("City College",42,55),("Green Park",58,40),("Hospital Gate",75,30),("Tech Park",90,15)]},
 "R2": {"name": "Old Town - Airport", "stops": [("Old Town",8,20),("Temple Square",24,30),("Bus Depot",40,38),("Lake View",55,60),("Industrial Estate",72,72),("Airport",92,85)]},
 "R3": {"name": "University - Riverside", "stops": [("University",12,50),("Library Circle",30,45),("Metro Gate",48,25),("Sports Complex",65,22),("Riverside Mall",85,35)]},
}
BUSES = {"BUS-101":("R1",0.0,28),"BUS-102":("R1",0.5,24),"BUS-201":("R2",0.2,30),"BUS-202":("R2",0.7,22),"BUS-301":("R3",0.4,26)}
LOOP_SECONDS = 600  # demo bus completes its route in 10 minutes

def km(a, b): return math.hypot(a[0]-b[0], a[1]-b[1]) * 0.2
def route_info(rid):
    pts = [(s[1], s[2]) for s in ROUTES[rid]["stops"]]; cum = [0.0]
    for i in range(1, len(pts)): cum.append(cum[-1] + km(pts[i-1], pts[i]))
    return pts, cum

def traffic_now(h=None):
    h = dt.datetime.now().hour if h is None else h
    return 2 if h in (8,9,10,17,18,19) else 1 if 11 <= h <= 16 else 0

def bus_state(bus_id):
    rid, off, base = BUSES[bus_id]; pts, cum = route_info(rid); total = cum[-1]
    t = time.time(); d = (((t / LOOP_SECONDS) + off) % 1) * total
    i = max(j for j in range(len(cum)) if cum[j] <= d) if d < total else len(cum)-2
    i = min(i, len(pts)-2); seg = (d - cum[i]) / (cum[i+1] - cum[i])
    x = pts[i][0] + (pts[i+1][0]-pts[i][0]) * seg; y = pts[i][1] + (pts[i+1][1]-pts[i][1]) * seg
    speed = max(6, base * [1, .8, .6][traffic_now()] + 4 * math.sin(t / 15 + off * 6))
    return {"bus": bus_id, "route": rid, "x": x, "y": y, "d": d, "total": total, "cum": cum, "speed": round(speed, 1), "lat": round(10.9 + y/500, 5), "lon": round(76.9 + x/500, 5)}

# ---- Database ----
def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c
def init_db():
    DB.parent.mkdir(exist_ok=True)
    c = db(); c.executescript("""
      CREATE TABLE IF NOT EXISTS buses(id TEXT PRIMARY KEY, route_id TEXT, capacity INT);
      CREATE TABLE IF NOT EXISTS routes(id TEXT PRIMARY KEY, name TEXT);
      CREATE TABLE IF NOT EXISTS trips(id INTEGER PRIMARY KEY, bus_id TEXT, route_id TEXT, day TEXT, hour INT, scheduled_min REAL, actual_min REAL, traffic INT);
      CREATE TABLE IF NOT EXISTS contacts(id INTEGER PRIMARY KEY, name TEXT, email TEXT, message TEXT, created TEXT);""")
    if c.execute("SELECT COUNT(*) FROM trips").fetchone()[0] == 0:
        r = random.Random(7)
        for b, (rid, _, _) in BUSES.items():
            c.execute("INSERT OR REPLACE INTO buses VALUES(?,?,?)", (b, rid, 50))
        for rid, v in ROUTES.items(): c.execute("INSERT OR REPLACE INTO routes VALUES(?,?)", (rid, v["name"]))
        for n in range(400):
            b = r.choice(list(BUSES)); rid = BUSES[b][0]; h = r.randint(6, 21); tr = traffic_now(h)
            sched = r.uniform(25, 40); act = sched * (1 + .12 * tr + r.gauss(0, .06))
            c.execute("INSERT INTO trips(bus_id,route_id,day,hour,scheduled_min,actual_min,traffic) VALUES(?,?,?,?,?,?,?)",
                      (b, rid, (dt.date.today() - dt.timedelta(days=n % 14)).isoformat(), h, sched, act, tr))
    c.commit(); c.close()

def err(msg, code=400): return jsonify({"error": msg}), code

# ---- Pages & API ----
def _page(name): return lambda: render_template(name + ".html")
for _n, _u in [("home","/"),("tracking","/tracking"),("planner","/planner"),("eta","/eta"),("routes","/routes"),("analytics","/analytics"),("about","/about"),("contact","/contact")]:
    app.add_url_rule(_u, _n, _page(_n))

@app.route("/api/meta")
def meta():
    return jsonify({"routes": {k: {"name": v["name"], "stops": [s[0] for s in v["stops"]]} for k, v in ROUTES.items()},
                    "buses": {b: v[0] for b, v in BUSES.items()}})

@app.route("/api/track")
def track():
    bus, stop = request.args.get("bus"), request.args.get("stop")
    if bus not in BUSES: return err("Choose a valid bus number.")
    s = bus_state(bus); rid = s["route"]; stops = ROUTES[rid]["stops"]; names = [x[0] for x in stops]
    if stop not in names: return err("That stop is not on this bus route. Pick a stop from the list.")
    idx = names.index(stop); remaining = s["cum"][idx] - s["d"]; passed = remaining < 0
    if passed: remaining += s["total"]
    hist = 24.0
    p = predict_eta({"lat": s["lat"], "lon": s["lon"], "speed": s["speed"], "distance": max(remaining, .05),
                     "traffic": traffic_now(), "hour": dt.datetime.now().hour, "dow": dt.datetime.now().weekday(), "hist_speed": hist})
    status = "On Time" if p["delay_min"] <= 2 else "Slightly Delayed" if p["delay_min"] <= 5 else "Delayed"
    upcoming = [{"name": n, "km": round(s["cum"][i] - s["d"], 2), "eta_min": round((s["cum"][i] - s["d"]) / max(s["speed"], 5) * 60, 1)}
                for i, n in enumerate(names) if s["cum"][i] > s["d"]]
    return jsonify({"demo_data": True, "bus": bus, "route": rid, "route_name": ROUTES[rid]["name"], "position": {"x": s["x"], "y": s["y"], "lat": s["lat"], "lon": s["lon"]},
        "stops": [{"name": a, "x": b, "y": c} for a, b, c in stops], "speed": s["speed"], "distance_km": round(remaining, 2),
        "eta_min": p["eta_min"], "delay_min": p["delay_min"], "status": status, "model": p["model"],
        "just_passed": passed, "traffic": ["Light", "Moderate", "Heavy"][traffic_now()], "upcoming": upcoming})

@app.route("/api/predict", methods=["POST"])
def predict():
    d = request.get_json(silent=True) or {}
    try:
        f = {"speed": float(d["speed"]), "distance": float(d["distance"]), "traffic": int(d["traffic"]),
             "hour": int(d["hour"]), "dow": int(d["dow"]), "hist_speed": float(d.get("hist_speed", 24))}
    except (KeyError, ValueError, TypeError):
        return err("Please fill in speed, distance, traffic, hour and day with valid numbers.")
    if not (1 <= f["speed"] <= 80): return err("Speed must be between 1 and 80 km/h.")
    if not (0.1 <= f["distance"] <= 100): return err("Distance must be between 0.1 and 100 km.")
    if f["traffic"] not in (0, 1, 2): return err("Traffic must be Light, Moderate or Heavy.")
    if not (0 <= f["hour"] <= 23) or not (0 <= f["dow"] <= 6): return err("Hour must be 0-23 and day must be Monday-Sunday.")
    for k in ("lat", "lon"): f[k] = float(d.get(k, 10.9))
    return jsonify(predict_eta(f))

@app.route("/api/traffic-effect")
def traffic_effect():
    dist = float(request.args.get("distance", 5)); speed = float(request.args.get("speed", 28))
    return jsonify([{"traffic": n, "eta_min": predict_eta({"speed": speed, "distance": dist, "traffic": i, "hour": 9, "dow": 1, "hist_speed": 24})["eta_min"]}
                    for i, n in enumerate(["Light", "Moderate", "Heavy"])])

@app.route("/api/history")
def history():
    c = db(); rows = c.execute("SELECT hour, AVG(scheduled_min) s, AVG(actual_min) a FROM trips GROUP BY hour ORDER BY hour").fetchall(); c.close()
    out = []
    for r in rows:
        pred = predict_eta({"speed": 28, "distance": r["s"] / 60 * 25, "traffic": traffic_now(r["hour"]), "hour": r["hour"], "dow": 2, "hist_speed": 24})["eta_min"]
        out.append({"hour": f'{r["hour"]}:00', "scheduled": round(r["s"], 1), "actual": round(r["a"], 1), "predicted": pred})
    return jsonify(out)

@app.route("/api/analytics")
def api_analytics():
    c = db(); rows = c.execute("SELECT route_id, AVG(actual_min - scheduled_min) delay, AVG(actual_min <= scheduled_min + 3) ontime, COUNT(*) n FROM trips GROUP BY route_id").fetchall()
    tot = c.execute("SELECT AVG(actual_min <= scheduled_min + 3) o FROM trips").fetchone()["o"]; c.close()
    delayed = []
    for b in BUSES:
        s = bus_state(b); stops = ROUTES[s["route"]]["stops"]; nxt = next((i for i, x in enumerate(s["cum"]) if x > s["d"]), len(stops)-1)
        dist = max(s["cum"][nxt] - s["d"], .1)
        p = predict_eta({"speed": s["speed"], "distance": dist, "traffic": traffic_now(), "hour": dt.datetime.now().hour, "dow": dt.datetime.now().weekday(), "hist_speed": 24})
        if p["delay_min"] > 2: delayed.append({"bus": b, "route": s["route"], "delay_min": p["delay_min"], "next_stop": stops[nxt][0]})
    return jsonify({"total_buses": len(BUSES), "active_routes": len(ROUTES), "avg_wait_min": round(random.Random(int(time.time()//60)).uniform(6, 9), 1),
                    "on_time_pct": round(tot * 100, 1), "delayed_buses": len(delayed), "delayed": delayed,
                    "routes": [{"route": r["route_id"], "name": ROUTES[r["route_id"]]["name"], "avg_delay": round(r["delay"], 1), "on_time_pct": round(r["ontime"] * 100, 1), "trips": r["n"]} for r in rows]})

@app.route("/api/plan")
def plan():
    src, dst = request.args.get("src"), request.args.get("dst"); out = []
    if not src or not dst or src == dst: return err("Choose two different stops.")
    for b, (rid, _, _) in BUSES.items():
        names = [x[0] for x in ROUTES[rid]["stops"]]
        if src in names and dst in names and names.index(src) < names.index(dst):
            s = bus_state(b); i, j = names.index(src), names.index(dst); wait_km = s["cum"][i] - s["d"]
            if wait_km < 0: wait_km += s["total"]
            trip_km = s["cum"][j] - s["cum"][i]; now = dt.datetime.now()
            base = {"speed": s["speed"], "traffic": traffic_now(), "hour": now.hour, "dow": now.weekday(), "hist_speed": 24}
            w = predict_eta({**base, "distance": max(wait_km, .05)}); t = predict_eta({**base, "distance": max(trip_km, .05)})
            out.append({"bus": b, "route": rid, "wait_min": w["eta_min"], "trip_min": t["eta_min"], "trip_km": round(trip_km, 1),
                        "fare": round(5 + 1.5 * trip_km), "status": "On Time" if w["delay_min"] <= 2 else "Delayed"})
    if not out: return err("No direct bus runs from that stop to that stop. Try a different pair on the same route.")
    return jsonify({"demo_data": True, "options": sorted(out, key=lambda o: o["wait_min"])})

@app.route("/api/contact", methods=["POST"])
def api_contact():
    d = request.get_json(silent=True) or {}
    n, e, m = (d.get(k, "").strip() for k in ("name", "email", "message"))
    if not n or "@" not in e or len(m) < 5: return err("Enter your name, a valid email and a message of at least 5 characters.")
    c = db(); c.execute("INSERT INTO contacts(name,email,message,created) VALUES(?,?,?,?)", (n, e, m, dt.datetime.now().isoformat())); c.commit(); c.close()
    return jsonify({"ok": True})

init_db()  # also runs under gunicorn
if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=int(os.environ.get("PORT", 5000)))
