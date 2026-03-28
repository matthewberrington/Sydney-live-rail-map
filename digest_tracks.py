from Station import Station
from Track import Track
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
        station_projected = Station(station.name, station.line, *proj_pt.coords[0], station.map_origin, station.scale)
        stations_projected.append(station_projected)
    
    for station in stations_projected:
        station.orientation = get_station_orientations(track, station)

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

def get_station_orientations(track, station):
    x, y = station.get_displacement()
    pt = Point(x, y)
    s = track.line_cartesian.project(pt)
    p1 = track.line_cartesian.interpolate(s-0.01)
    p2 = track.line_cartesian.interpolate(s+0.01)
    slope = (p2.y - p1.y) / (p2.x - p1.x)
    if p1.x < p2.x:
        orientation = np.arctan(slope)
    else:
        orientation = np.arctan(slope) + np.pi
    return orientation

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

def get_track(ref, to, origin):
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
    track = Track(ref, lon, lat, origin)
    return track

def get_stations(track, destination = None, origin = None):
    stations = []
    for feature in data["features"]:
        geom = feature["geometry"]
        props = feature["properties"]
        if geom["type"] == "Point":
            if "railway" in props.keys() and props["railway"] == 'stop':
                if '@relations' in props.keys():
                    if props["@relations"][0]["reltags"]["to"] == destination or destination == None:
                        line = props["@relations"][0]["reltags"]["ref"]
                        if props["@relations"][0]["reltags"]["ref"] == track.name:
                            station = Station(props["name"], line, *geom["coordinates"], origin)
                            stations.append(station)
    stations.sort(key=lambda station: track.distance_along(station))
    return stations

def get_track_midline(track1, track2, N, flip = True):
    lon1_interp, lat1_interp = evenly_spaced_points(track1.longitudes, track1.latitudes, N)
    lon2_interp, lat2_interp = evenly_spaced_points(track2.longitudes, track2.latitudes, N)
    if flip:
        lon2_interp = np.flip(lon2_interp)
        lat2_interp = np.flip(lat2_interp)
    track = Track(track1.name, (lon1_interp + lon2_interp)/2, (lat1_interp + lat2_interp)/2, track1.map_origin, track1.scale)
    return track

def get_station_midpoint(stations1, stations2):
    stations = []
    for station1 in stations1:
        station2 = next((s for s in stations2 if s.name == station1.name), None)
        if station2:
            mid_lat = (station1.latitude + station2.latitude)/2
            mid_lon = (station1.longitude + station2.longitude)/2
            stations.append(Station(station1.name, station1.line, mid_lon, mid_lat, station1.map_origin, station1.scale))
    return stations

def get_pseudo_stations(stations, track, minimum_distance):
    pseudo_stations = []
    for i in range(len(stations)-1):
        station1 = stations[i]
        station2 = stations[i+1]
        l1 = track.distance_along(station1)
        l2 = track.distance_along(station2)
        num_pseudo_stations = int((l2 - l1)//minimum_distance) -1
        delta_l = (l2 - l1)/(num_pseudo_stations+1)
        for j in range(num_pseudo_stations):
            l = l1 + (j+1)*delta_l
            x, y = track.get_line_cartesian().interpolate(l).coords[0]
            pseudo_station = Station.cartesian(f'__PSEUDO__', track.name, x, y, track.map_origin, track.scale)
            pseudo_stations.append(pseudo_station)
    return pseudo_stations
    
if __name__ == '__main__':
    with open("export.geojson") as f:
        data = json.load(f)

    origin = (151.22289335, -33.8937485)
    # x_origin = 151.22287115
    # y_origin = -33.893729

    N_interp = 3000
    L2A_track = get_track('L2', 'Randwick', origin)
    L2B_track = get_track('L2', 'Circular Quay', origin)
    L2_track = get_track_midline(L2A_track, L2B_track, N_interp)
    
    L3A_track = get_track('L3', 'Juniors Kingsford', origin)
    L3B_track = get_track('L3', 'Circular Quay', origin)
    L3_track = get_track_midline(L3A_track, L3B_track, N_interp)

    L2_stationsA = get_stations(L2_track, destination = 'Randwick', origin=origin)
    L2_stationsB = get_stations(L2_track, destination = 'Circular Quay', origin=origin)
    L2_stations = project_stations_onto_track(L2_track, L2_stationsA, L2_stationsB)

    L3_stationsA = get_stations(L3_track, destination = 'Juniors Kingsford', origin=origin)
    L3_stationsB = get_stations(L3_track, destination = 'Circular Quay', origin=origin)
    L3_stations = project_stations_onto_track(L3_track, L3_stationsA, L3_stationsB)

    ### Define pseudo-stations

    L2_pseudo_stations = get_pseudo_stations(L2_stations, L2_track, minimum_distance = 100)
    L3_pseudo_stations = get_pseudo_stations(L3_stations, L3_track, minimum_distance = 100)

    plt.plot(*L2_track.get_displacements(), color = 'lightgrey')
    plt.plot(*L3_track.get_displacements(), color = 'lightgrey')
        
    for station in L2_stations + L3_stations:
        x,y = station.get_displacement()
        plt.plot(x, y, marker = 's', color = 'r')
        plt.plot([x, 25*np.cos(station.orientation)], [y, 25*np.sin(station.orientation)], color = 'r')
    for station in L2_pseudo_stations + L3_pseudo_stations:
        x,y = station.get_displacement()
        plt.plot(x, y, marker = '*', color = 'b')
        plt.plot([x, 25*np.cos(station.orientation)], [y, 25*np.sin(station.orientation)], color = 'b')

    plt.gca().axis('equal')
    plt.show()
    

    # # -----------------------------
    # segments_L2 = split_track_by_stations_inclusive(L2_track, L2_stations)
    # segments_L3 = split_track_by_stations_inclusive(L3_track, L3_stations)
    # orientations_L2 = get_station_orientations(L2_track, L2_stations)
    # orientations_L3 = get_station_orientations(L3_track, L3_stations)
    
    # plt.figure()
    # plt.plot(*L2_track, color = 'lightgrey')
    # plt.plot(*L3_track, color = 'lightgrey')

    # for station_coords in L2_stations_m.values():
    #     plt.plot(*station_coords, marker = 's', color = 'k')

    # for station_coords in L3_stations_m.values():
    #     plt.plot(*station_coords, marker = 's', color = 'k')

    # for segment in segments_L2:
    #     plt.plot(*zip(*list(segment['line'].coords)))
    
    # for segment in segments_L3:
    #     plt.plot(*zip(*list(segment['line'].coords)))

    # plt.gca().axis('equal')

    
    # t = np.array([0,100])
    # for idx,(x,y) in enumerate(L2_stations_m.values()):
    #     theta = orientations_L2[idx]
    #     plt.plot(x+np.cos(theta)*t,y+np.sin(theta)*t, 'k')

    # station_geometry = {}
    # for idx, (key, val) in enumerate(L3_stations_m.items()):
    #     theta = orientations_L3[idx]
    #     station_geometry[key] = (*val, theta)
    # for idx, (key, val) in enumerate(L2_stations_m.items()):
    #     theta = orientations_L2[idx]
    #     station_geometry[key] = (*val, theta)

    # with open('station_geometry.pckl', 'wb') as file:
    #     pickle.dump(station_geometry, file)
    # with open('L2_tracks.pckl', 'wb') as file:
    #     pickle.dump(L2_track_m, file)
    # with open('L3_tracks.pckl', 'wb') as file:
    #     pickle.dump(L3_track_m, file)


    # plt.show()
    
    