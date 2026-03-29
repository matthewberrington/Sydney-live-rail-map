from Station import Station
from Track import Track
from MapProjection import MapProjection
from shapely.geometry import LineString, Point
from shapely.ops import linemerge, unary_union
import json
import matplotlib.pyplot as plt
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

def project_stations_onto_track(track, stationsA, stationsB):
    stations = get_station_midpoint(stationsA, stationsB)

    # Project each station onto the line
    stations_projected = []
    for station in stations:
        pt = Point(station.longitude, station.latitude)
        s = track.line_spherical.project(pt)
        proj_pt = track.line_spherical.interpolate(s)
        station_projected = Station(station.name, *proj_pt.coords[0], track)
        stations_projected.append(station_projected)
    
    return stations_projected

def split_track_by_stations_inclusive(track, stations):

    major_nodes = stations
    # Create segments between consecutive projected points
    segments = []
    for i in range(len(major_nodes) - 1):
        node1 = major_nodes[i]
        node2 = major_nodes[i+1]
        point1 = Point(*node1.get_displacement())
        point2 = Point(*node2.get_displacement())
        length1 = track.get_line_cartesian().project(point1)
        length2 = track.get_line_cartesian().project(point2)
        segment = cut_line_between(track.get_line_cartesian(), length1, length2)
        segments.append({
            'from': node1.name,
            'to': node2.name,
            'line': segment
        })

    return segments

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

def get_track(ref, to, projection):
    segments = []
    for feature in data["features"]:
        geom = feature["geometry"]
        geom_type = geom["type"]
        properties = feature["properties"]

        if geom_type == "LineString":
            if '@relations' in properties.keys():
                if properties["@relations"][0]["reltags"]["to"] == to:
                    if properties["@relations"][0]["reltags"]["ref"] == ref:
                        segments.append(LineString(geom["coordinates"]))
    lon, lat = list(zip(*to_ordered_coords(segments)))
    track = Track(ref, lon, lat, projection)
    return track

def get_stations(track, destination = None):
    stations = []
    for feature in data["features"]:
        geom = feature["geometry"]
        props = feature["properties"]
        if geom["type"] == "Point":
            if "railway" in props.keys() and props["railway"] == 'stop':
                if '@relations' in props.keys():
                    if props["@relations"][0]["reltags"]["to"] == destination or destination == None:
                        if props["@relations"][0]["reltags"]["ref"] == track.name:
                            station = Station(props["name"], *geom["coordinates"], track)
                            stations.append(station)
    stations.sort(key=lambda station: station.chainage)
    return stations

def get_track_midline(track1, track2, N, flip = True):
    lon1_interp, lat1_interp = evenly_spaced_points(track1.longitudes, track1.latitudes, N)
    lon2_interp, lat2_interp = evenly_spaced_points(track2.longitudes, track2.latitudes, N)
    if flip:
        lon2_interp = np.flip(lon2_interp)
        lat2_interp = np.flip(lat2_interp)
    track = Track(track1.name, (lon1_interp + lon2_interp)/2, (lat1_interp + lat2_interp)/2, projection)
    return track

def get_station_midpoint(stations1, stations2):
    #error occurs if all station are not on same track
    track = stations1[0].track
    stations = []
    for station1 in stations1:
        station2 = next((s for s in stations2 if s.name == station1.name), None)
        if station2:
            mid_lat = (station1.latitude + station2.latitude)/2
            mid_lon = (station1.longitude + station2.longitude)/2
            stations.append(Station(station1.name, mid_lon, mid_lat, track))
    return stations

def get_pseudo_stations(stations, track, minimum_distance):
    pseudo_stations = []
    for i in range(len(stations)-1):
        station1 = stations[i]
        station2 = stations[i+1]
        
        l1 = station1.chainage
        l2 = station2.chainage
        num_pseudo_stations = int((l2 - l1)//minimum_distance) -1
        delta_l = (l2 - l1)/(num_pseudo_stations+1)
        for j in range(num_pseudo_stations):
            l = l1 + (j+1)*delta_l
            x, y = track.line_cartesian.interpolate(l).coords[0]
            lon, lat = projection.map_to_geo(x, y)
            pseudo_station = Station(f'__PSEUDO__', lon, lat, track)
            pseudo_stations.append(pseudo_station)
    return pseudo_stations
    
if __name__ == '__main__':
    with open("export.geojson") as f:
        data = json.load(f)

    projection = MapProjection(origin_lon = 151.22289335, origin_lat = -33.8937485, scale=1.0)
    # x_origin = 151.22287115
    # y_origin = -33.893729

    N_interp = 3000
    L2A_track = get_track('L2', 'Randwick', projection)
    L2B_track = get_track('L2', 'Circular Quay', projection)
    L2_track = get_track_midline(L2A_track, L2B_track, N_interp)

    L3A_track = get_track('L3', 'Juniors Kingsford', projection)
    L3B_track = get_track('L3', 'Circular Quay', projection)
    L3_track = get_track_midline(L3A_track, L3B_track, N_interp)

    L2_stationsA = get_stations(L2_track, destination = 'Randwick')
    L2_stationsB = get_stations(L2_track, destination = 'Circular Quay')
    L2_stations = project_stations_onto_track(L2_track, L2_stationsA, L2_stationsB)

    L3_stationsA = get_stations(L3_track, destination = 'Juniors Kingsford')
    L3_stationsB = get_stations(L3_track, destination = 'Circular Quay')
    L3_stations = project_stations_onto_track(L3_track, L3_stationsA, L3_stationsB)

    ### Define pseudo-stations

    L2_pseudo_stations = get_pseudo_stations(L2_stations, L2_track, minimum_distance = 100)
    L3_pseudo_stations = get_pseudo_stations(L3_stations, L3_track, minimum_distance = 100)

    plt.plot(L2_track.map_x, L2_track.map_y, color = 'lightgrey')
    plt.plot(L3_track.map_x, L3_track.map_y, color = 'lightgrey')

    for station in L2_stations + L3_stations:
        plt.plot(station.map_x, station.map_y, marker = 's', color = 'r')
        plt.plot([station.map_x, station.map_x + 25*np.cos(np.deg2rad(station.orientation))], [station.map_y, station.map_y + 25*np.sin(np.deg2rad(station.orientation))], color = 'r')
    for station in L2_pseudo_stations + L3_pseudo_stations:
        plt.plot(station.map_x, station.map_y, marker = '*', color = 'b')
        plt.plot([station.map_x, station.map_x + 25*np.cos(np.deg2rad(station.orientation))], [station.map_y, station.map_y + 25*np.sin(np.deg2rad(station.orientation))], color = 'b')

    plt.gca().axis('equal')
    plt.show()