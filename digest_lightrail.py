from shapely.geometry import LineString, Point
from shapely.ops import linemerge, unary_union
import json
import matplotlib.pyplot as plt
import numpy as np
from utils import get_total_length, degrees_to_metres
import pickle

def split_track_by_stations(xs, ys, stations):
    line = LineString(list(zip(xs, ys)))
    line_length = line.length

    # Project each station onto the line
    projections = []
    for x, y, name in stations:
        pt = Point(x, y)
        s = line.project(pt)
        proj_pt = line.interpolate(s)
        projections.append({'name': name, 's': s, 'point': proj_pt})

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

    return segments, projections

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

def tangent_angle_at_point(line: LineString, x: float, y: float, degrees: bool = False) -> float:
    """
    Compute the tangent angle of a LineString at or near a given (x, y) point.

    Parameters
    ----------
    line : shapely.geometry.LineString
        The input line.
    x, y : float
        Coordinates of the point (assumed to lie on or near the line).
    degrees : bool, optional
        If True, return angle in degrees. Otherwise radians.

    Returns
    -------
    float
        Tangent angle at that point (radians by default).
    """
    pt = Point(x, y)

    # Project point onto the line to find the distance along it
    s = line.project(pt)

    # Small offset for finite-difference derivative
    eps = min(1e-6, line.length * 1e-6)
    s1 = max(0, s - eps)
    s2 = min(line.length, s + eps)

    p1 = line.interpolate(s1)
    p2 = line.interpolate(s2)

    dx = p2.x - p1.x
    dy = p2.y - p1.y

    angle = np.atan2(dy, dx)
    return np.degrees(angle) if degrees else angle


def get_station_coords(target_refs):
    stations = []
    for feature in data["features"]:
        geom = feature["geometry"]
        props = feature["properties"]
        if geom["type"] == "Point":
            if "railway" in props.keys() and props["railway"] == 'stop':
                if '@relations' in props.keys():
                    if props["@relations"][0]["reltags"]["ref"] in target_refs:
                        if props["@relations"][0]["reltags"]["to"] == 'Circular Quay':
                            stations.append((*geom["coordinates"], props["name"]))
    return stations

def get_LineStrings(target_ref):
    linestrings = []
    for feature in data["features"]:
        geom = feature["geometry"]
        props = feature["properties"]
        if geom["type"] == "LineString":
            if "@relations" in props:
                ref = props["@relations"][0]["reltags"].get("ref")
                if ref in target_ref:
                    linestrings.append(LineString(geom["coordinates"]))
    return linestrings

def merge_linestrings(linestrings):
    # return merged geometry (LineString or MultiLineString)
    merged = linemerge(unary_union(linestrings))
    return merged

def extract_coords_from_merged(merged, idx=0):
    # helper to get coords list for a particular part when merged is MultiLineString
    if merged.geom_type == "MultiLineString":
        return list(merged.geoms[idx].coords)
    else:
        return list(merged.coords)

def merge_and_extract_coords(linestrings):
    merged = linemerge(unary_union(linestrings))
    if merged.geom_type == "MultiLineString":
        ordered_coords = [list(ls.coords) for ls in merged.geoms]
    else:
        ordered_coords = list(merged.coords)
    return ordered_coords

if __name__ == "__main__":
    with open("lightrail.geojson") as f:
        data = json.load(f)

    L2_linestrings = get_LineStrings("L2")
    L3_linestrings = get_LineStrings("L3")

    L2_merged = merge_linestrings(L2_linestrings)
    L3_merged = merge_linestrings(L3_linestrings)

    L2_coords = extract_coords_from_merged(L2_merged, 0)  # 0 = Randwick-bound
    L3_coords = extract_coords_from_merged(L3_merged, 1)  # 1 = Juniors-Kingsford bound

    coords = L2_coords + L3_coords
    lons, lats = map(list, zip(*coords))

    origin = ((np.min(lons) + np.max(lons))/2, (np.min(lats) + np.max(lats))/2)
    xs_L2, ys_L2 = degrees_to_metres(*zip(*L2_coords), origin)
    xs_L3, ys_L3 = degrees_to_metres(*zip(*L3_coords), origin)

    L2_line = LineString(zip(xs_L2, ys_L2))
    L3_line = LineString(zip(xs_L3, ys_L3))

    stations_L2 = []
    for lon, lat, name in get_station_coords("L2"):
        stations_L2.append((*degrees_to_metres(lon, lat, origin), name))
    stations_L3 = []
    for lon, lat, name in get_station_coords("L3"):
        stations_L3.append((*degrees_to_metres(lon, lat, origin), name))

    
    segments_L2, projected_stations_L2 = split_track_by_stations(xs_L2, ys_L2, stations_L2)
    segments_L3, projected_stations_L3 = split_track_by_stations(xs_L3, ys_L3, stations_L3)

    # # -----------------------------
    # # Calculate positions of LEDs
    # # -----------------------------
    
    LED_geometry = {}
    LED_idx = 0
    minimum_spacing = 75
    for seg in (segments_L2 + segments_L3):
        if seg['line'] == None:
            continue
        x, y = seg['line'].xy
        N = int((get_total_length(x,y))//minimum_spacing) + 1
        x_LED, y_LED = evenly_spaced_points(x, y, N)
        for i in range(0, N-1):
            angle = tangent_angle_at_point(seg['line'], x_LED[i], y_LED[i], degrees = True)
            LED_geometry['D'+str(LED_idx+100)] = (x_LED[i], y_LED[i], angle)
            LED_idx += 1
    # Note: Am missing the last node at end of L2 and L3

    with open('LED_geometry.pckl', 'wb') as file:
        pickle.dump(LED_geometry, file)

    # # -----------------------------
    # # Calculate positions of stations
    # # -----------------------------

    station_geometry = {}
    station_idx = 0

    for p in projected_stations_L2:
        distance_to_L2 = p['point'].distance(L2_line)
        distance_to_L3 = p['point'].distance(L3_line)
        if distance_to_L2 < distance_to_L3:
            line = L2_line
            line_name = 'L2'
        else:
            line = L3_line
            line_name = 'L3'
        angle_station = tangent_angle_at_point(line, p['point'].x, p['point'].y, degrees = True)
        station_geometry[station_idx] = (p['point'].x, p['point'].y, angle_station, p['name'], line_name)
        station_idx += 1

    with open('station_geometry.pckl', 'wb') as file:
        pickle.dump(station_geometry, file)


    # # -----------------------------
    # # Plot
    # # -----------------------------
    
    plt.figure()
    plt.plot(xs_L2, ys_L2, 'lightgray', lw=2, label="L2 Track")
    plt.plot(xs_L3, ys_L3, 'lightgray', lw=2, label="L3 Track")

    for LEDxy in LED_geometry.values():
        plt.plot(LEDxy[0], LEDxy[1],'ok')

    # plt.plot(xs_L3_combined, ys_L3_combined, 'green', lw=2, label="L3 Track (with shared section)")

    for p in projected_stations_L2:
        plt.scatter(p['point'].x, p['point'].y, color='red')
        plt.text(p['point'].x, p['point'].y, p['name'], fontsize=8, ha='left')
    for p in projected_stations_L3:
        plt.scatter(p['point'].x, p['point'].y, color='red')
        plt.text(p['point'].x, p['point'].y, p['name'], fontsize=8, ha='left')

    plt.axis('equal')
    plt.show()
