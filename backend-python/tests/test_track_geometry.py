"""Landmarks must use measured coordinates; pit status must not reveal future stops."""
import copy
from datetime import datetime, timezone
from services.track_geometry_service import add_track_landmarks, measured_pit_state

T = datetime(2026, 10, 9, tzinfo=timezone.utc).timestamp()
def date(t): return datetime.fromtimestamp(T + t, timezone.utc).isoformat()
def samples(waypoints):
    result = []
    for a, b in zip(waypoints, waypoints[1:]):
        for i in range(int((b[0] - a[0]) * 2)):
            t = a[0] + i / 2; u = (t - a[0]) / (b[0] - a[0])
            result.append([T + t, a[1] + u * (b[1] - a[1]), a[2] + u * (b[2] - a[2])])
    result.append([T + waypoints[-1][0], *waypoints[-1][1:]])
    return result
def dataset():
    return {'complete_archive': True, 'track': {'points': [[0, 0], [10000, 0], [10000, 5000], [0, 5000]],
            'bounds': [0, 0, 10000, 5000], 'driver_number': 1, 'lap': 2},
            'events': {'laps': [{'driver_number': 1, 'lap_number': 2, 'date_start': date(15)}],
                       'pit': [{'driver_number': 2, 'date': date(30), 'lane_duration': 20}]},
            'locations': {'1': samples([(0, 3500, 0), (30, 6500, 0)]),
                          '2': samples([(0, 1000, 0), (8, 2000, -160), (20, 5000, -160), (32, 8000, -160), (40, 9000, 0), (50, 10000, 0)])}}

def test_start_line_is_interpolated_at_lap_boundary_not_arbitrary_polyline_origin():
    d = dataset(); add_track_landmarks(d)
    assert d['track']['start_finish']['x'] == 5000
    assert d['track']['start_finish']['y'] == 0
    assert d['track']['start_finish']['direction'][0] > 0
    assert d['track']['start_finish']['approximate']

def test_pit_lane_is_a_distinct_measured_open_path_with_joining_endpoints():
    d = dataset(); add_track_landmarks(d); pit = d['track']['pit_lane']
    assert pit and len(pit['points']) >= 5
    assert pit['points'][0] != pit['points'][-1]
    assert any(p[1] == -160 for p in pit['points'])
    assert pit['entry'][1] > -20 and pit['exit'][1] > -20
    assert pit['approximate']

def test_missing_pit_measurements_or_no_lane_separation_do_not_create_parallel_fake_route():
    d = dataset(); d['events']['pit'][0]['lane_duration'] = None; add_track_landmarks(d)
    assert d['track']['pit_lane'] is None
    assert measured_pit_state(d, 2, T + 20) == (None, None)
    d = dataset(); d['locations']['2'] = samples([(0, 1000, 0), (50, 10000, 0)]); add_track_landmarks(d)
    assert d['track']['pit_lane'] is None

def test_pit_occupancy_uses_only_past_locations_and_does_not_stay_pit_after_exit():
    d = dataset(); add_track_landmarks(d)
    assert measured_pit_state(d, 2, T) == (False, None)
    inside, entry = measured_pit_state(d, 2, T + 20)
    assert inside and datetime.fromisoformat(entry).timestamp() <= T + 20
    changed = copy.deepcopy(d); changed['events']['pit'][0]['date'] = date(500); changed['events']['pit'][0]['lane_duration'] = 400
    changed['locations']['2'] = [p for p in changed['locations']['2'] if p[0] <= T + 20]
    assert measured_pit_state(changed, 2, T + 20) == (inside, entry)
    assert measured_pit_state(d, 2, T + 42) == (False, None)

def test_stale_locations_cannot_claim_current_pit_occupancy():
    d = dataset(); add_track_landmarks(d)
    d['locations']['2'] = [p for p in d['locations']['2'] if p[0] <= T + 20]
    assert measured_pit_state(d, 2, T + 25) == (None, None)

def test_unknown_start_timing_does_not_reuse_first_shape_vertex_as_finish_line():
    d = dataset(); d['events']['laps'] = []; add_track_landmarks(d)
    assert 'start_finish' not in d['track']
