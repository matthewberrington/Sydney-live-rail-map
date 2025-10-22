from shapely.geometry import LineString, Point
import json
import matplotlib.pyplot as plt
import numpy as np
from utils import get_total_length, degrees_to_metres
import pickle
from utils_geospatial import merge_linestrings, extract_coords_from_merged, cut_line_between, get_LineStrings, tangent_angle_at_point, evenly_spaced_points

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

def get_LineStrings(geojson_data, target_ref):
    linestrings = []
    for feature in geojson_data["features"]:
        geom = feature["geometry"]
        props = feature["properties"]
        if geom["type"] == "LineString":
            if "@relations" in props:
                ref = props["@relations"][0]["reltags"].get("ref")
                if ref in target_ref:
                    linestrings.append(LineString(geom["coordinates"]))
    return linestrings

def get_station_coords(geojson_data, target_refs):
    stations = []
    for feature in geojson_data["features"]:
        geom = feature["geometry"]
        props = feature["properties"]
        if geom["type"] == "Point":
            if "railway" in props.keys() and props["railway"] == 'stop':
                if '@relations' in props.keys():
                    if props["@relations"][0]["reltags"]["ref"] in target_refs:
                        if props["@relations"][0]["reltags"]["to"] == 'Circular Quay':
                            stations.append((*geom["coordinates"], props["name"]))
    return stations

if __name__ == "__main__":
    with open("lightrail.geojson") as f:
        geojson_data = json.load(f)

    L2_linestrings = get_LineStrings(geojson_data, "L2")
    L3_linestrings = get_LineStrings(geojson_data, "L3")

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
    for lon, lat, name in get_station_coords(geojson_data, "L2"):
        stations_L2.append((*degrees_to_metres(lon, lat, origin), name))
    stations_L3 = []
    for lon, lat, name in get_station_coords(geojson_data, "L3"):
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
