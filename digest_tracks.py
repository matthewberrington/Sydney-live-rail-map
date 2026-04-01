import argparse
import json
import pickle
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import GeometryCollection, LineString, MultiLineString, Point
from shapely.ops import linemerge, unary_union

from MapProjection import MapProjection
from Station import Station
from Track import Track

sys.modules.setdefault("digest_tracks", sys.modules[__name__])

PCB_ORIGIN_MM = (148.5, 210.0)
LIGHT_RAIL_INPUT_PATH = "lightrail.geojson"
TRAIN_INPUT_CANDIDATES = ("train.geojson", "trains.geojson")
LIGHT_RAIL_INTERPOLATION_POINTS = 3000


@dataclass(frozen=True)
class LightRailLineSpec:
    ref: str
    destination_a: str
    destination_b: str
    pseudo_station_spacing_m: float = 75.0


@dataclass
class LightRailLineGeometry:
    ref: str
    track: Track
    stations: list[Station]
    pseudo_stations: list[Station]


@dataclass
class RouteGeometryGroup:
    ref: str
    mode: str
    relation_names: tuple[str, ...]
    destinations: tuple[str, ...]
    geometry_geo: LineString | MultiLineString
    geometry_map: LineString | MultiLineString
    track_components: list[Track]


LightRailLineGeometry.__module__ = "digest_tracks"
RouteGeometryGroup.__module__ = "digest_tracks"


LIGHT_RAIL_SPECS = (
    LightRailLineSpec("L2", "Randwick", "Circular Quay"),
    LightRailLineSpec("L3", "Juniors Kingsford", "Circular Quay"),
)


def cut_line(line, distance):
    if distance <= 0.0:
        return None, LineString(line)
    if distance >= line.length:
        return LineString(line), None

    coords = list(line.coords)
    for index, point in enumerate(coords):
        projected_distance = line.project(Point(point))
        if projected_distance == distance:
            return LineString(coords[: index + 1]), LineString(coords[index:])
        if projected_distance > distance:
            previous_point = Point(coords[index - 1])
            next_point = Point(point)
            ratio = (distance - line.project(previous_point)) / (
                line.project(next_point) - line.project(previous_point)
            )
            cut_point = (
                previous_point.x + ratio * (next_point.x - previous_point.x),
                previous_point.y + ratio * (next_point.y - previous_point.y),
            )
            return (
                LineString(coords[:index] + [cut_point]),
                LineString([cut_point] + coords[index:]),
            )
    return None


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


def evenly_spaced_points(xs, ys, count):
    xs = np.array(xs)
    ys = np.array(ys)
    dx = np.diff(xs)
    dy = np.diff(ys)
    segment_lengths = np.sqrt(dx**2 + dy**2)
    cumulative = np.insert(np.cumsum(segment_lengths), 0, 0)
    target_distance = np.linspace(0, cumulative[-1], count)
    x_interp = np.interp(target_distance, cumulative, xs)
    y_interp = np.interp(target_distance, cumulative, ys)
    return x_interp, y_interp


def load_json_data(path=None, default_candidates=()):
    if path:
        candidates = [Path(path)]
    else:
        candidates = [Path(candidate) for candidate in default_candidates]

    if not candidates:
        raise FileNotFoundError("No JSON input path was provided")

    candidate_descriptions = []
    for candidate in candidates:
        candidate_descriptions.append(str(candidate))
        if not candidate.exists():
            continue
        if candidate.is_dir():
            raise IsADirectoryError(f"Expected a JSON file, got directory: {candidate}")
        with open(candidate) as file:
            return json.load(file), candidate

    raise FileNotFoundError(
        "No JSON file found. Checked: " + ", ".join(candidate_descriptions)
    )


def load_export_data(path=None):
    return load_json_data(path=path, default_candidates=(LIGHT_RAIL_INPUT_PATH,))


def load_train_data(path=None):
    return load_json_data(path=path, default_candidates=TRAIN_INPUT_CANDIDATES)


def iter_relation_tags(feature):
    properties = feature.get("properties", {})
    for relation in properties.get("@relations", []):
        yield relation.get("reltags", {})


def get_primary_relation_tags(feature):
    properties = feature.get("properties", {})
    relations = properties.get("@relations", [])
    if not relations:
        return None
    return relations[0].get("reltags", {})


def iter_line_geometries(feature):
    geometry = feature["geometry"]
    geometry_type = geometry["type"]
    if geometry_type == "LineString":
        yield LineString(geometry["coordinates"])
    elif geometry_type == "MultiLineString":
        for coords in geometry["coordinates"]:
            yield LineString(coords)


def merge_line_segments(segments):
    if not segments:
        raise ValueError("No line segments supplied")

    merged = unary_union(segments)
    if isinstance(merged, GeometryCollection):
        line_geometries = [
            geometry
            for geometry in merged.geoms
            if geometry.geom_type in {"LineString", "MultiLineString"}
        ]
        if not line_geometries:
            raise ValueError("No line geometry found after merging segments")
        merged = unary_union(line_geometries)

    merged = linemerge(merged)
    if merged.geom_type not in {"LineString", "MultiLineString"}:
        raise ValueError(f"Unexpected merged geometry type: {merged.geom_type}")
    return merged


def explode_lines(geometry):
    if geometry.geom_type == "LineString":
        return [geometry]
    if geometry.geom_type == "MultiLineString":
        return list(geometry.geoms)
    raise ValueError(f"Unsupported geometry type: {geometry.geom_type}")


def build_track_from_segments(ref, segments, projection):
    geometry = merge_line_segments(segments)
    if geometry.geom_type != "LineString":
        raise ValueError(f"{ref} resolved to {geometry.geom_type}, expected a single LineString")
    longitudes, latitudes = zip(*geometry.coords)
    return Track(ref, list(longitudes), list(latitudes), projection)


def build_track_components(ref, geometry, projection):
    components = []
    exploded = sorted(explode_lines(geometry), key=lambda line: line.length, reverse=True)
    for index, component in enumerate(exploded, start=1):
        longitudes, latitudes = zip(*component.coords)
        component_name = ref if len(exploded) == 1 else f"{ref}_{index}"
        components.append(Track(component_name, list(longitudes), list(latitudes), projection))
    return components


def build_map_geometry(track_components):
    map_segments = [track.line_cartesian for track in track_components]
    if len(map_segments) == 1:
        return map_segments[0]
    return MultiLineString([list(segment.coords) for segment in map_segments])


def collect_relation_segments(data, relation_filter):
    grouped_segments = defaultdict(list)
    relation_names = defaultdict(set)
    destinations = defaultdict(set)

    for feature in data["features"]:
        segments = list(iter_line_geometries(feature))
        if not segments:
            continue

        for tags in iter_relation_tags(feature):
            if not relation_filter(tags):
                continue

            ref = tags["ref"]
            grouped_segments[ref].extend(segments)

            route_name = tags.get("name")
            if route_name:
                relation_names[ref].add(route_name)

            destination = tags.get("to")
            if destination:
                destinations[ref].add(destination)

    return grouped_segments, relation_names, destinations


def get_route_segments(data, ref, destination):
    segments = []
    for feature in data["features"]:
        for tags in iter_relation_tags(feature):
            if tags.get("ref") == ref and tags.get("to") == destination:
                segments.extend(iter_line_geometries(feature))
                break
    return segments


def get_light_rail_route_segments(data, ref, destination):
    segments = []
    for feature in data["features"]:
        tags = get_primary_relation_tags(feature)
        if tags is None:
            continue
        if tags.get("ref") == ref and tags.get("to") == destination:
            segments.extend(iter_line_geometries(feature))
    return segments


def get_stations(track, data, ref, destination=None):
    stations = []
    for feature in data["features"]:
        geometry = feature["geometry"]
        properties = feature.get("properties", {})
        if geometry["type"] != "Point" or properties.get("railway") != "stop":
            continue

        for tags in iter_relation_tags(feature):
            if tags.get("ref") != ref:
                continue
            if destination is not None and tags.get("to") != destination:
                continue
            stations.append(Station(properties["name"], *geometry["coordinates"], track))
            break

    stations.sort(key=lambda station: station.chainage)
    return stations


def get_light_rail_stations(track, data, destination=None):
    stations = []
    for feature in data["features"]:
        geometry = feature["geometry"]
        properties = feature.get("properties", {})
        if geometry["type"] != "Point" or properties.get("railway") != "stop":
            continue

        tags = get_primary_relation_tags(feature)
        if tags is None:
            continue
        if tags.get("ref") != track.name:
            continue
        if destination is not None and tags.get("to") != destination:
            continue

        stations.append(Station(properties["name"], *geometry["coordinates"], track))

    stations.sort(key=lambda station: station.chainage)
    return stations


def get_station_midpoint(stations_a, stations_b):
    track = stations_a[0].track
    stations = []
    for station_a in stations_a:
        station_b = next((station for station in stations_b if station.name == station_a.name), None)
        if station_b is None:
            continue

        midpoint_lon = (station_a.longitude + station_b.longitude) / 2
        midpoint_lat = (station_a.latitude + station_b.latitude) / 2
        stations.append(Station(station_a.name, midpoint_lon, midpoint_lat, track))
    return stations


def project_stations_onto_track(track, stations_a, stations_b):
    station_midpoints = get_station_midpoint(stations_a, stations_b)
    projected_stations = []
    for station in station_midpoints:
        point = Point(station.longitude, station.latitude)
        chainage = track.line_spherical.project(point)
        projected_point = track.line_spherical.interpolate(chainage)
        projected_stations.append(Station(station.name, *projected_point.coords[0], track))
    return projected_stations


def get_track_midline(track_a, track_b, count, projection, flip=True):
    lon_a, lat_a = evenly_spaced_points(track_a.longitudes, track_a.latitudes, count)
    lon_b, lat_b = evenly_spaced_points(track_b.longitudes, track_b.latitudes, count)
    if flip:
        lon_b = np.flip(lon_b)
        lat_b = np.flip(lat_b)
    return Track(track_a.name, (lon_a + lon_b) / 2, (lat_a + lat_b) / 2, projection)


def get_pseudo_stations(stations, track, projection, minimum_distance):
    pseudo_stations = []
    for index in range(len(stations) - 1):
        station_a = stations[index]
        station_b = stations[index + 1]

        start_chainage = station_a.chainage
        end_chainage = station_b.chainage
        pseudo_station_count = int((end_chainage - start_chainage) // minimum_distance) - 1
        if pseudo_station_count <= 0:
            continue
        spacing = (end_chainage - start_chainage) / (pseudo_station_count + 1)

        for pseudo_index in range(pseudo_station_count):
            chainage = start_chainage + (pseudo_index + 1) * spacing
            map_x, map_y = track.line_cartesian.interpolate(chainage).coords[0]
            longitude, latitude = projection.map_to_geo(map_x, map_y)
            pseudo_stations.append(Station("", longitude, latitude, track))

    return pseudo_stations


def build_light_rail_line(spec, data, projection):
    segments_a = get_light_rail_route_segments(data, spec.ref, spec.destination_a)
    segments_b = get_light_rail_route_segments(data, spec.ref, spec.destination_b)
    missing_destinations = []
    if not segments_a:
        missing_destinations.append(spec.destination_a)
    if not segments_b:
        missing_destinations.append(spec.destination_b)
    if missing_destinations:
        joined_destinations = ", ".join(missing_destinations)
        raise ValueError(f"Missing {spec.ref} route segments for: {joined_destinations}")

    track_a = build_track_from_segments(
        spec.ref,
        segments_a,
        projection,
    )
    track_b = build_track_from_segments(
        spec.ref,
        segments_b,
        projection,
    )
    track = get_track_midline(
        track_a,
        track_b,
        LIGHT_RAIL_INTERPOLATION_POINTS,
        projection,
    )

    stations_a = get_light_rail_stations(track, data, destination=spec.destination_a)
    stations_b = get_light_rail_stations(track, data, destination=spec.destination_b)
    stations = project_stations_onto_track(track, stations_a, stations_b)
    pseudo_stations = get_pseudo_stations(
        stations,
        track,
        projection,
        minimum_distance=spec.pseudo_station_spacing_m,
    )
    return LightRailLineGeometry(spec.ref, track, stations, pseudo_stations)


def write_light_rail_outputs(light_rail_line):
    stations = sorted(
        light_rail_line.stations + light_rail_line.pseudo_stations,
        key=lambda station: station.chainage,
    )
    with open(f"{light_rail_line.ref}_stations_geometry.pckl", "wb") as file:
        pickle.dump(stations, file)
    with open(f"{light_rail_line.ref}_track_geometry.pckl", "wb") as file:
        pickle.dump(light_rail_line.track, file)

def is_train_relation(tags):
    ref = tags.get("ref")
    route = tags.get("route")
    network = (tags.get("network") or "").lower()

    if not ref:
        return False
    if route in {"train", "subway"}:
        return True
    if ref.startswith(("T", "M")) and "light rail" not in network:
        return True
    return False


def build_train_route_groups(data, projection):
    grouped_segments = defaultdict(list)
    relation_names = defaultdict(set)
    destinations = defaultdict(set)

    for feature in data["features"]:
        properties = feature.get("properties", {})
        if not is_train_relation(properties):
            continue

        segments = list(iter_line_geometries(feature))
        if not segments:
            continue

        ref = properties["ref"]
        grouped_segments[ref].extend(segments)

        route_name = properties.get("name")
        if route_name:
            relation_names[ref].add(route_name)

        destination = properties.get("to")
        if destination:
            destinations[ref].add(destination)

    route_groups = {}
    for ref, segments in sorted(grouped_segments.items()):
        geometry = merge_line_segments(segments)
        track_components = build_track_components(ref, geometry, projection)
        route_groups[ref] = RouteGeometryGroup(
            ref=ref,
            mode="train",
            relation_names=tuple(sorted(relation_names[ref])),
            destinations=tuple(sorted(destinations[ref])),
            geometry_geo=geometry,
            geometry_map=build_map_geometry(track_components),
            track_components=track_components,
        )
    return route_groups


def sanitise_ref_for_filename(ref):
    return "".join(character if character.isalnum() else "_" for character in ref)


def write_train_route_outputs(route_groups):
    output_paths = {}
    for ref, route_group in route_groups.items():
        filename = f"{sanitise_ref_for_filename(ref)}_tracks_geometry.pckl"
        with open(filename, "wb") as file:
            pickle.dump(route_group, file)
        output_paths[ref] = filename
    return output_paths


def collect_available_route_refs(data):
    refs = set()
    for feature in data["features"]:
        properties = feature.get("properties", {})
        direct_ref = properties.get("ref")
        if direct_ref:
            refs.add(direct_ref)
        for tags in iter_relation_tags(feature):
            ref = tags.get("ref")
            if ref:
                refs.add(ref)
    return sorted(refs)


def plot_outputs(light_rail_lines, train_route_groups):
    for line in light_rail_lines.values():
        plt.plot(line.track.map_x, line.track.map_y, color="lightgrey")
        for station in line.stations:
            plt.plot(station.map_x, station.map_y, marker="s", color="r")
        for station in line.pseudo_stations:
            plt.plot(station.map_x, station.map_y, marker="*", color="b")

    for route_group in train_route_groups.values():
        for track in route_group.track_components:
            plt.plot(track.map_x, track.map_y, color="black", linewidth=0.8)

    plt.gca().axis("equal")
    plt.show()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="Path to the light rail geojson/json file")
    parser.add_argument("--train-input", help="Path to the train geojson/json file")
    parser.add_argument("--plot", action="store_true", help="Show a debug plot")
    return parser.parse_args()


def main():
    args = parse_args()
    light_rail_data, light_rail_input_path = load_export_data(args.input)

    projection = MapProjection(
        origin_lon=151.22289335,
        origin_lat=-33.8937485,
        scale=1 / 25000,
        pcb_origin_mm=PCB_ORIGIN_MM,
    )

    light_rail_lines = {}
    skipped_light_rail_lines = {}
    for spec in LIGHT_RAIL_SPECS:
        try:
            line = build_light_rail_line(spec, light_rail_data, projection)
        except ValueError as error:
            skipped_light_rail_lines[spec.ref] = str(error)
            continue

        write_light_rail_outputs(line)
        light_rail_lines[spec.ref] = line

    try:
        train_data, train_input_path = load_train_data(args.train_input)
        train_route_groups = build_train_route_groups(train_data, projection)
        train_output_paths = write_train_route_outputs(train_route_groups)
    except FileNotFoundError:
        train_input_path = None
        train_route_groups = {}
        train_output_paths = {}

    if args.plot:
        plot_outputs(light_rail_lines, train_route_groups)

    print(f"Loaded light rail export from {light_rail_input_path}")
    if light_rail_lines:
        print(f"Wrote light rail outputs for: {', '.join(sorted(light_rail_lines))}")
    if skipped_light_rail_lines:
        print("Skipped light rail outputs for:")
        for ref, message in skipped_light_rail_lines.items():
            print(f"  {ref}: {message}")

    if train_output_paths:
        print(f"Loaded train export from {train_input_path}")
        print("Wrote train route geometry for:")
        for ref, filename in train_output_paths.items():
            print(f"  {ref}: {filename}")
    else:
        if train_input_path is None:
            print("No train geojson/json file was found.")
        else:
            available_refs = ", ".join(collect_available_route_refs(train_data))
            print(f"Loaded train export from {train_input_path}")
            print("No train routes were found in the current train export.")
            print(f"Available route refs in this file: {available_refs}")


if __name__ == "__main__":
    main()
