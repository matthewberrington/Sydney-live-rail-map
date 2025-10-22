from shapely.ops import linemerge, unary_union
from shapely.geometry import LineString, Point
import numpy as np

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