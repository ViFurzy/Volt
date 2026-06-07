"""Battery drain estimation logic for Volt."""
import datetime

from ui.settings_manager import load_config

def calculate_time_remaining(device_id: str, current_percent: int) -> str:
    """Calculate the estimated time remaining based on historical drain rate.

    Looks back up to 24 hours to find a period of strictly decreasing battery.
    Returns a formatted string like '~14h 30m left', or 'Estimating...' if 
    there is insufficient data.
    """
    cfg = load_config()
    history = cfg.get("history", {}).get(device_id, [])
    
    if len(history) < 2:
        return "Estimating..."
        
    now = datetime.datetime.now()
    cutoff = now - datetime.timedelta(hours=24)
    
    # Parse valid history within the last 24h
    valid_points = []
    for entry in reversed(history):
        try:
            dt = datetime.datetime.fromisoformat(entry["timestamp"])
            if dt < cutoff:
                break  # history is chronological, so older points are earlier
            valid_points.append({"dt": dt, "percent": entry["percent"]})
        except Exception:
            continue
            
    if len(valid_points) < 2:
        return "Estimating..."
        
    # valid_points is currently newest to oldest (because we reversed history)
    # The newest point should be roughly current_percent
    latest = valid_points[0]
    
    # Find an older point where the battery was strictly higher (indicating a drain)
    # We want the oldest point in our 24h window that represents a continuous drain.
    # To be safe, we just find the oldest point that is > latest["percent"] 
    # without any charging interruptions (battery going up) in between.
    
    drain_start = latest
    for pt in valid_points[1:]:
        if pt["percent"] > drain_start["percent"]:
            drain_start = pt
        elif pt["percent"] < drain_start["percent"]:
            # Battery was lower in the past, meaning it was charged between then and now!
            # We break here to only look at the most recent continuous discharging cycle.
            break
            
    if drain_start["percent"] <= latest["percent"]:
        # No discharging recorded
        return "Estimating..."
        
    # Calculate drain rate
    percent_drained = drain_start["percent"] - latest["percent"]
    time_elapsed_secs = (latest["dt"] - drain_start["dt"]).total_seconds()
    
    if time_elapsed_secs <= 0:
        return "Estimating..."
        
    time_elapsed_hours = time_elapsed_secs / 3600.0
    drain_per_hour = percent_drained / time_elapsed_hours
    
    # Require at least 0.1% per hour to avoid absurdly large estimates (e.g., years)
    if drain_per_hour < 0.1:
        return "Estimating..."
        
    hours_left = current_percent / drain_per_hour
    
    h = int(hours_left)
    m = int((hours_left - h) * 60)
    
    if h > 0:
        return f"~{h}h {m}m left"
    return f"~{m}m left"
