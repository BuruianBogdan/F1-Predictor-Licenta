"""Circuit landmarks from measured trajectories, in the map's own coordinate system."""
import bisect
import math
from datetime import datetime, timezone
from services.season_service import parse_time


def distance_to_path(x, y, points, closed=False):
    best = float('inf')
    pairs = zip(points, points[1:] + points[:1] if closed else points[1:])
    for a, b in pairs:
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = dx * dx + dy * dy
        u = max(0., min(1., ((x - a[0]) * dx + (y - a[1]) * dy) / length)) if length else 0.
        best = min(best, (x - a[0] - u * dx) ** 2 + (y - a[1] - u * dy) ** 2)
    return math.sqrt(best)


def position_at(points, at):
    i = bisect.bisect_right(points, at, key=lambda p: p[0]) - 1
    if i < 0 or i + 1 >= len(points):
        return None
    a, b = points[i:i + 2]
    if b[0] - a[0] > 3:
        return None
    u = (at - a[0]) / (b[0] - a[0])
    return [a[1] + u * (b[1] - a[1]), a[2] + u * (b[2] - a[2])]


def map_scale(track):
    x0, y0, x1, y1 = track['bounds']
    return min(680 / (x1 - x0), 350 / (y1 - y0))


def add_track_landmarks(data):
    track = data.get('track')
    if not track or track.get('landmarks_version') == 1:
        return
    # Shared with the reference lap; geographic SVG points have a different origin.
    lap = next((l for l in data['events'].get('laps', [])
                if l['driver_number'] == track['driver_number'] and l['lap_number'] == track['lap']), None)
    series = data['locations'].get(str(track['driver_number']), [])
    if lap and lap.get('date_start') and not lap.get('is_pit_out_lap'):
        at = parse_time(lap['date_start']).timestamp()
        p, before, after = position_at(series, at), position_at(series, at - .6), position_at(series, at + .6)
        if p and before and after and math.dist(before, after) > 1:
            track['start_finish'] = {'x': p[0], 'y': p[1], 'direction': [after[0] - before[0], after[1] - before[1]],
                                     'approximate': True, 'source': 'Measured position at approximate flying-lap timing boundary'}
    track['pit_lane'] = measured_pit_lane(data)
    # Live can inherit verified landmarks from an earlier session at the same meeting.
    if data.get('complete_archive'):
        track['landmarks_version'] = 1


def measured_pit_lane(data):
    track = data['track']; scale = map_scale(track)
    # The archive pit-duration record is published at completion, not an entry trigger.
    # Use it to locate a *static* measured route, never to reveal a future stop to strategy.
    candidates = sorted((p for p in data['events'].get('pit', []) if p.get('date') and
                         isinstance(p.get('lane_duration') or p.get('pit_duration'), (float, int)) and
                         8 <= (p.get('lane_duration') or p['pit_duration']) <= 180),
                        key=lambda p: p.get('lane_duration') or p['pit_duration'])
    for pit in candidates[:12]:
        end = parse_time(pit['date']).timestamp(); start = end - (pit.get('lane_duration') or pit['pit_duration'])
        series = data['locations'].get(str(pit['driver_number']), [])
        lo = bisect.bisect_left(series, start - 18, key=lambda p: p[0]); hi = bisect.bisect_right(series, end + 40, key=lambda p: p[0])
        points = series[lo:hi]
        if len(points) < 15 or any(b[0] - a[0] > 3 for a, b in zip(points, points[1:])):
            continue
        distances = [distance_to_path(p[1], p[2], track['points'], closed=True) * scale for p in points]
        separated = [i for i, p in enumerate(points) if start <= p[0] <= end and distances[i] > 2.2]
        if not separated:
            continue  # The source may lack sufficient lateral detail to separate the lanes.
        first, last = separated[0], separated[-1]
        while first > 0 and distances[first] > 1.1:
            first -= 1
        while last < len(points) - 1 and distances[last] > 1.1:
            last += 1
        if distances[first] > 1.1 or distances[last] > 1.1:
            continue  # Prefer a complete entry-to-exit route over a car stopped in the lane.
        route = []
        for p in points[first:last + 1]:
            xy = p[1:3]
            if not route or math.dist(route[-1], xy) * scale >= .6:
                route.append(xy)
        length = sum(math.dist(a, b) for a, b in zip(route, route[1:])) * scale
        circuit_length = sum(math.dist(a, b) for a, b in zip(track['points'], track['points'][1:] + track['points'][:1])) * scale
        if len(route) >= 5 and 12 <= length < circuit_length * .6:
            return {'points': route, 'entry': route[0], 'exit': route[-1], 'driver_number': pit['driver_number'],
                    'source': 'Measured trajectory around an archived pit-lane passage', 'approximate': True}
    return None


def measured_pit_state(data, number, at):
    """Use only positions already measured at the requested time; no future stop duration."""
    track = data.get('track') or {}; pit = track.get('pit_lane')
    if not pit:
        return None, None
    points = data['locations'].get(str(number), [])
    i = bisect.bisect_right(points, at, key=lambda p: p[0]) - 1
    if i < 0 or at - points[i][0] > 2.5:
        return None, None
    scale = map_scale(track)
    cache = data.setdefault('_pit_position_cache', {})
    def inside(p):
        xy = (p[1], p[2])
        if xy not in cache:
            if len(cache) > 20000:
                cache.clear()
            cache[xy] = (distance_to_path(*xy, pit['points']) * scale < 2.8 and
                         distance_to_path(*xy, track['points'], closed=True) * scale > 1.4)
        return cache[xy]
    if not inside(points[i]):
        return False, None
    entry = points[i][0]
    # Entry estimate comes solely from the past trajectory. A telemetry gap breaks it.
    while i > 0 and points[i][0] - points[i - 1][0] <= 3 and inside(points[i - 1]):
        i -= 1; entry = points[i][0]
    return True, datetime.fromtimestamp(entry, timezone.utc).isoformat()
