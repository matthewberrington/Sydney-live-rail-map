from shapely.geometry import LineString, Point
from shapely.ops import linemerge, unary_union
import json
import matplotlib.pyplot as plt
from utils import get_total_length, degrees_to_metres
import pickle
import numpy as np

def cut_line_between(line, start_dist, end_dist):
    if start_dist >= end_dist:
        raise ValueError("start_dist must be less than end_dist")
    start_cut = cut_line(line, start_dist)
    if start_cut is None:
        return None
    sub_line = start_cut[1]
    end_cut = cut_line(sub_line, end_dist - start_dist)
    if end_cut is None:
        return sub_line
    return end_cut[0]

def cut_line(line, distance):
    if distance <= 0.0:
        return None, LineString(line)
    if distance >= line.length:
        return LineString(line), None

    coords = list(line.coords)
    for i, p in enumerate(coords):
        pd = line.project(Point(p))
        if pd == distance:
            return LineString(coords[:i+1]), LineString(coords[i:])
        if pd > distance:
            prev_p = Point(coords[i-1])
            next_p = Point(p)
            ratio = (distance - line.project(prev_p)) / (line.project(next_p) - line.project(prev_p))
            x = prev_p.x + ratio * (next_p.x - prev_p.x)
            y = prev_p.y + ratio * (next_p.y - prev_p.y)
            cut_point = (x, y)
            return (
                LineString(coords[:i] + [cut_point]),
                LineString([cut_point] + coords[i:])
            )
    return None

def project_stations_onto_track(coords, stations):
    line = LineString(list(zip(*coords)))

    # Project each station onto the line
    stations_projected = {}
    for station_name in stations.keys():
        x, y = stations[station_name]
        pt = Point(x, y)
        s = line.project(pt)
        proj_pt = line.interpolate(s)
        stations_projected[station_name] = list(proj_pt.coords[0])
    return stations_projected

def split_track_by_stations_inclusive(coords, stations):
    line = LineString(list(zip(*coords)))
    line_length = line.length

    # Project each station onto the line
    projections = []
    for station_name in stations.keys():
        x, y = stations[station_name]
        pt = Point(x, y)
        s = line.project(pt)
        proj_pt = line.interpolate(s)
        projections.append({'name': station_name, 's': s, 'point': proj_pt})

    # Add start and end points of the line as virtual "stations"
    projections.append({'name': '__START__', 's': 0.0, 'point': line.interpolate(0.0)})
    projections.append({'name': '__END__', 's': line_length, 'point': line.interpolate(line_length)})

    # Sort by distance along the line
    projections.sort(key=lambda p: p['s'])

    # Create segments between consecutive projected points
    segments = []
    for i in range(len(projections) - 1):
        start_s = projections[i]['s']
        end_s = projections[i + 1]['s']
        segment = cut_line_between(line, start_s, end_s)
        segments.append({
            'from': projections[i]['name'],
            'to': projections[i + 1]['name'],
            'line': segment
        })

    return segments

def get_station_orientations(coords, stations):
    line = LineString(list(zip(*coords)))

    # Project each station onto the line
    orientations = []
    for station_name in stations.keys():
        x, y = stations[station_name]
        pt = Point(x, y)
        s = line.project(pt)
        p1 = line.interpolate(s-0.01)
        p2 = line.interpolate(s+0.01)
        slope = (p2.y - p1.y) / (p2.x - p1.x)
        if p1.x < p2.x:
            angle = np.arctan(slope)
        else:
            angle = np.arctan(slope) + np.pi
        orientations.append(angle)

    return orientations

def to_ordered_coords(segments):
    merged = linemerge(unary_union(segments))
    if merged.geom_type == "MultiLineString":
        ordered_coords = [list(ls.coords) for ls in merged.geoms]
    else:
        ordered_coords = list(merged.coords)
    return ordered_coords

def evenly_spaced_points(xs, ys, N):
    xs, ys = np.array(xs), np.array(ys)
    dx = np.diff(xs)
    dy = np.diff(ys)
    seg_lengths = np.sqrt(dx**2 + dy**2)
    cumulative = np.insert(np.cumsum(seg_lengths), 0, 0)
    total_length = cumulative[-1]
    target_d = np.linspace(0, total_length, N)
    x_interp = np.interp(target_d, cumulative, xs)
    y_interp = np.interp(target_d, cumulative, ys)
    return x_interp, y_interp

def get_segments(ref, to):
    segments = []
    for feature in data["features"]:
        geom = feature["geometry"]
        geom_type = geom["type"]
        coords = geom["coordinates"]
        properties = feature["properties"]

        if geom_type == "LineString":
            if '@relations' in properties.keys():
                if properties["@relations"][0]["reltags"]["to"] == to:
                    if properties["@relations"][0]["reltags"]["ref"] == ref:
                        segments.append(LineString(geom["coordinates"]))
    merged = linemerge(unary_union(segments))
    return list(merged.coords)

def get_stations(ref, to):
    stations = {}
    for feature in data["features"]:
        geom = feature["geometry"]
        props = feature["properties"]
        if geom["type"] == "Point":
            if "railway" in props.keys() and props["railway"] == 'stop':
                if '@relations' in props.keys():
                    if props["@relations"][0]["reltags"]["to"] == to:
                        if props["@relations"][0]["reltags"]["ref"] == ref:
                            stations[props["name"]] = geom["coordinates"]
    return stations

def get_midline_coords(segments1, segments2, N, flip = True):
    x1_interp, y1_interp = evenly_spaced_points(*zip(*segments1),N)
    x2_interp, y2_interp = evenly_spaced_points(*zip(*segments2),N)
    if flip:
        x2_interp = np.flip(x2_interp)
        y2_interp = np.flip(y2_interp)
    return (x1_interp + x2_interp)/2, (y1_interp + y2_interp)/2

def get_station_midpoint(stations1, stations2):
    stations = {}
    for station_name in stations1.keys():
        xA, yA = stations1[station_name]
        xB, yB = stations2[station_name]
        stations[station_name] = (xA + xB)/2, (yA + yB)/2
    return stations

def station_degrees_to_metres(stations_deg, origin):
    stations = {}
    for key, val in stations_deg.items():
        stations[key] = degrees_to_metres(*val, origin)
    return stations

if __name__ == '__main__':
    with open("export.geojson") as f:
        data = json.load(f)

    origin = (151.22289335, -33.8937485)

    N_interp = 3000
    L2A_track_deg = get_segments('L2', 'Randwick')
    L2B_track_deg = get_segments('L2', 'Circular Quay')
    L2_track_deg = get_midline_coords(L2A_track_deg, L2B_track_deg, N_interp)
    L2_track_m = degrees_to_metres(*L2_track_deg, origin)

    L3A_track_deg = get_segments('L3', 'Juniors Kingsford')
    L3B_track_deg = get_segments('L3', 'Circular Quay')
    L3_track_deg = get_midline_coords(L3A_track_deg, L3B_track_deg, N_interp)
    L3_track_m = degrees_to_metres(*L3_track_deg, origin)

    L2_stationsA = get_stations('L2', 'Randwick')
    L2_stationsB = get_stations('L2', 'Circular Quay')
    L2_stations_deg = get_station_midpoint(L2_stationsA, L2_stationsB)
    L2_stations_m = station_degrees_to_metres(L2_stations_deg, origin)
    L2_stations_m = project_stations_onto_track(L2_track_m, L2_stations_m)

    L3_stationsA = get_stations('L3', 'Juniors Kingsford')
    L3_stationsB = get_stations('L3', 'Circular Quay')
    L3_stations_deg = get_station_midpoint(L3_stationsA, L3_stationsB)
    L3_stations_m = station_degrees_to_metres(L3_stations_deg, origin)
    L3_stations_m = project_stations_onto_track(L3_track_m, L3_stations_m)

    # # -----------------------------
    # # Split by stations
    # # -----------------------------
    segments_L2 = split_track_by_stations_inclusive(L2_track_m, L2_stations_m)
    segments_L3 = split_track_by_stations_inclusive(L3_track_m, L3_stations_m)
    orientations_L2 = get_station_orientations(L2_track_m, L2_stations_m)
    orientations_L3 = get_station_orientations(L3_track_m, L3_stations_m)
    
    plt.figure()
    plt.plot(*L2_track_m, color = 'lightgrey')
    plt.plot(*L3_track_m, color = 'lightgrey')

    for station_coords in L2_stations_m.values():
        plt.plot(*station_coords, marker = 's', color = 'k')

    for station_coords in L3_stations_m.values():
        plt.plot(*station_coords, marker = 's', color = 'k')

    for segment in segments_L2:
        plt.plot(*zip(*list(segment['line'].coords)))
    
    for segment in segments_L3:
        plt.plot(*zip(*list(segment['line'].coords)))

    plt.gca().axis('equal')

    #TODO: get anble to station
    t = np.array([0,100])
    for idx,(x,y) in enumerate(L2_stations_m.values()):
        theta = orientations_L2[idx]
        plt.plot(x+np.cos(theta)*t,y+np.sin(theta)*t, 'k')
    plt.show()
    