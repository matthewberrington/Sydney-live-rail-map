from kipy import KiCad
import kipy
from kipy.board_types import BoardText, BoardSegment, BoardArc, Via, Net, Track, ArcTrack, BoardSegment, Zone
from kipy.proto.board.board_types_pb2 import BoardLayer
from kipy.geometry import Vector2, Angle, PolygonWithHoles, PolyLineNode, PolyLine
from kipy.util import from_mm
from kipy.proto.common import HorizontalAlignment, VerticalAlignment, StrokeLineStyle
from MapProjection import MapProjection
import json
import matplotlib.pyplot as plt
import math
import pickle
from matplotlib import colormaps
from shapely.geometry import GeometryCollection, LineString, MultiLineString, box

MAP_ORIGIN_LON = 151.22289335
MAP_ORIGIN_LAT = -33.8937485
PCB_ORIGIN_MM = (148.5, 210.0)
KICAD_TIMEOUT_MS = 15000
CREATE_ITEMS_BATCH_SIZE = 500
board_clip_rect = None

def get_net_by_name(name: str):
    nets = board.get_nets()
    for net in nets:
        if net.name == name:
            return net
    return None
    
def add_via(
    x: float, y: float, net: str, diameter_mm: float = 0.5, drill_mm: float = 0.3
):
    via = Via()
    net_object = get_net_by_name(net)
    if net_object is not None:
        via.position = Vector2.from_xy_mm(x, y)
        via.diameter = from_mm(diameter_mm)
        via.drill_diameter = from_mm(drill_mm)
        via.net = net_object
        items_to_add.append(via)  # Store the via for later addition

def get_pad_position(footprint, net):
    for pad in footprint.definition.pads:
        if pad.net.name == net:
            return pad.position.x/1e6, pad.position.y/1e6
    return None


def get_pad_by_number(footprint, pad_number):
    for pad in footprint.definition.pads:
        if str(pad.number) == str(pad_number):
            return pad
    return None


def get_pad_position_by_number(footprint, pad_number):
    pad = get_pad_by_number(footprint, pad_number)
    if pad is None:
        return None
    return pad.position.x / 1e6, pad.position.y / 1e6

def calc_from_xy(
    x0: float,
    y0: float,
    xprime: float,
    yprime: float,
    angle: float,
):
    x2 = x0 + xprime * -math.cos(math.radians(angle)) - yprime * math.sin(math.radians(angle))
    y2 = (
        y0 + xprime * math.sin(math.radians(angle)) + yprime * -math.cos(math.radians(angle))
    )  # Add because KiCad's Y-axis is inverted
    return (x2, y2)

def draw_line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    width: float = 0.1,
    style=StrokeLineStyle.SLS_SOLID,
    net: str = "",
    layer= 'BL_F_SilkS',
) -> None:
    boardSegment = BoardSegment()
    boardSegment.start = Vector2.from_xy_mm(x1, y1)
    boardSegment.end = Vector2.from_xy_mm(x2, y2)
    boardSegment.attributes.stroke.width = from_mm(width)
    boardSegment.attributes.stroke.style = style
    boardSegment.layer = layer

    if net != "":
        boardSegment.net = get_net_by_name(net)

    items_to_add.append(boardSegment)  # Store the segment for later addition


def create_items_in_batches(items, batch_size=CREATE_ITEMS_BATCH_SIZE):
    if not items:
        return

    for start in range(0, len(items), batch_size):
        board.create_items(items[start:start + batch_size])


def map_polyline_to_pcb_polyline(xs, ys, projection, reverse=False):
    polyline = PolyLine()
    points = list(zip(xs, ys))
    if reverse:
        points.reverse()

    for map_x, map_y in points:
        pcb_x, pcb_y = projection.map_to_pcb(map_x, map_y)
        polyline.append(PolyLineNode.from_xy(from_mm(pcb_x), from_mm(pcb_y)))

    return polyline


def create_line(line, projection, layer='BL_F_SilkS', width=0.1):
    if hasattr(line, "track_components"):
        for track_component in line.track_components:
            create_line(track_component, projection, layer=layer, width=width)
        return

    if hasattr(line, "map_x") and hasattr(line, "map_y"):
        xs = line.map_x
        ys = line.map_y
    elif isinstance(line, tuple) and len(line) == 2:
        xs, ys = line
    else:
        raise TypeError(f"Unsupported line geometry type: {type(line)}")

    segments = []
    line_geometry = LineString(zip(xs, ys))
    if board_clip_rect is not None:
        line_geometry = line_geometry.intersection(board_clip_rect)

    if line_geometry.is_empty:
        return

    if isinstance(line_geometry, LineString):
        line_geometries = [line_geometry]
    elif isinstance(line_geometry, MultiLineString):
        line_geometries = list(line_geometry.geoms)
    elif isinstance(line_geometry, GeometryCollection):
        line_geometries = [
            geometry for geometry in line_geometry.geoms if isinstance(geometry, LineString)
        ]
    else:
        return

    for line_part in line_geometries:
        coords = list(line_part.coords)
        for idx in range(len(coords) - 1):
            x0, y0 = coords[idx]
            x1, y1 = coords[idx + 1]
            start_x, start_y = projection.map_to_pcb(x0, y0)
            end_x, end_y = projection.map_to_pcb(x1, y1)
            boardSegment = BoardSegment()
            boardSegment.start = Vector2.from_xy_mm(start_x, start_y)
            boardSegment.end = Vector2.from_xy_mm(end_x, end_y)
            boardSegment.attributes.stroke.width = from_mm(width)
            # arcTrack.attributes.stroke.style = StrokeLineStyle.SLS_SOLID
            boardSegment.layer = layer
            segments.append(boardSegment)
    items_to_add.extend(segments)


def format_station_name(name, wrap_at=14):
    if len(name) <= wrap_at or " " not in name:
        return name

    words = name.split()
    best_text = name
    best_score = len(name)
    for idx in range(1, len(words)):
        line1 = " ".join(words[:idx])
        line2 = " ".join(words[idx:])
        score = max(len(line1), len(line2))
        if score < best_score:
            best_text = f"{line1}\n{line2}"
            best_score = score
    return best_text


def add_station_label(station, offset_mm=4.0, size_mm=3.0, layer=BoardLayer.BL_F_SilkS, flip_label_side=False):
    if not station.name:
        return

    text = BoardText()
    text.value = format_station_name(station.name)

    label_angle = (station.orientation + 90) % 360
    if 90 < label_angle < 270:
        label_angle = (station.orientation - 90) % 360

    if flip_label_side:
        label_angle = (label_angle + 180) % 360

    if 60 < label_angle < 120 or 240 < label_angle < 300:
        offset_mm += 0.5

    text_x = round(station.pcb_x + offset_mm * math.cos(math.radians(label_angle)), 10)
    text_y = round(station.pcb_y - offset_mm * math.sin(math.radians(label_angle)), 10)

    text.layer = layer
    text.position = Vector2.from_xy_mm(text_x, text_y)
    text.attributes.font_name = "Carlito"
    text.attributes.size = Vector2.from_xy_mm(size_mm, size_mm)
    text.attributes.stroke_width = from_mm(0.12)
    text.attributes.angle = 0
    text.attributes.bold = True
    text.attributes.multiline = "\n" in text.value
    text.attributes.line_spacing = 0.8

    if 80 < label_angle < 100:
        text.attributes.vertical_alignment = VerticalAlignment.VA_BOTTOM
        text.attributes.horizontal_alignment = HorizontalAlignment.HA_CENTER
    elif 260 < label_angle < 280:
        text.attributes.vertical_alignment = VerticalAlignment.VA_TOP
        text.attributes.horizontal_alignment = HorizontalAlignment.HA_CENTER
    else:
        text.attributes.vertical_alignment = VerticalAlignment.VA_CENTER
        if text_x >= station.pcb_x:
            text.attributes.horizontal_alignment = HorizontalAlignment.HA_LEFT
        else:
            text.attributes.horizontal_alignment = HorizontalAlignment.HA_RIGHT

    line_end_x = round(station.pcb_x + (offset_mm - 0.5) * math.cos(math.radians(label_angle)), 10)
    line_end_y = round(station.pcb_y - (offset_mm - 0.5) * math.sin(math.radians(label_angle)), 10)
    draw_line(station.pcb_x, station.pcb_y, line_end_x, line_end_y, width=0.6, layer='BL_F_SilkS')

    items_to_add.append(text)


def draw_station_rectangle(
    x: float,
    y: float,
    width: float,
    height: float,
    angle: float = 0,
    line_width: float = 0.4,
    layer='BL_F_SilkS',
):
    hw = width / 2
    hh = height / 2
    corners = [(x - hw, y - hh), (x + hw, y - hh), (x + hw, y + hh), (x - hw, y + hh)]

    theta = math.radians(angle)
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)
    rotated_corners = []
    for cx, cy in corners:
        dx = cx - x
        dy = cy - y
        rx = x + dx * -cos_theta - dy * sin_theta
        ry = y + dx * sin_theta + dy * -cos_theta
        rotated_corners.append((rx, ry))

    for idx in range(4):
        x1, y1 = rotated_corners[idx]
        x2, y2 = rotated_corners[(idx + 1) % 4]
        draw_line(x1, y1, x2, y2, width=line_width, layer=layer)


def add_station_outline(station, width_mm=2.8, height_mm=2.0, line_width=0.4, layer='BL_F_SilkS'):
    if not station.name:
        return

    draw_station_rectangle(
        station.pcb_x,
        station.pcb_y,
        width_mm,
        height_mm,
        angle=station.orientation,
        line_width=line_width,
        layer=layer,
    )

def add_adjacent_via(footprint, offset_mm, angle, net, layer, width=0.5, backside_power = False):
    pad_x, pad_y = get_pad_position(footprint, net)
    via_offset_x = -offset_mm * math.cos(math.radians(footprint.orientation.degrees + angle))
    via_offset_y = offset_mm * math.sin(math.radians(footprint.orientation.degrees + angle))
    add_via(pad_x + via_offset_x, pad_y + via_offset_y, net = net)
    draw_line(pad_x, pad_y, pad_x + via_offset_x, pad_y + via_offset_y, width = width, net = net, layer = layer)
    if backside_power:
        s = -math.tan(math.radians(footprint.orientation.degrees))
        x1 = footprint.position.x/1e6
        y1 = footprint.position.y/1e6
        x2 = pad_x + via_offset_x
        y2 = pad_y + via_offset_y

        x = (s**2 * x1 + s * (y2 - y1) + x2)/(s**2 +1)
        y = (s**2 * y2 + s * (x2 - x1) + y1)/(s**2 +1)
        draw_line(x, y, pad_x + via_offset_x, pad_y + via_offset_y, width = width, net = net, layer = 'BL_B_Cu')
def board_edge(x0, x1, y0, y1, projection):
    arcTrack = BoardSegment()
    start_x, start_y = projection.map_to_pcb(x0, y0)
    end_x, end_y = projection.map_to_pcb(x1, y1)
    arcTrack.start = Vector2.from_xy_mm(start_x, start_y)
    arcTrack.end = Vector2.from_xy_mm(end_x, end_y)
    arcTrack.width = 1
    arcTrack.layer = 'BL_Edge_Cuts'
    return arcTrack


def reproject_stations(stations, projection):
    for station in stations:
        station.pcb_x, station.pcb_y = projection.geo_to_pcb(station.longitude, station.latitude)

if __name__=='__main__':
    try:
        kicad = KiCad(timeout_ms=KICAD_TIMEOUT_MS)
        print(f"Connected to KiCad {kicad.get_version()}")
    except BaseException as e:
        print(f"Not connected to KiCad: {e}")
        raise

    board = kicad.get_board()
    width_metres = 5000
    height_metres = 8000
    board_clip_rect = box(
        -width_metres / 2,
        -height_metres / 2,
        width_metres / 2,
        height_metres / 2,
    )
    scale = 25000
    projection = MapProjection(
        origin_lon=MAP_ORIGIN_LON,
        origin_lat=MAP_ORIGIN_LAT,
        scale=1 / scale,
        pcb_origin_mm=PCB_ORIGIN_MM,
    )

    items_to_add = []

    # ### CREATE HARBOUR ###
    with open('clark_island_geometry.pckl', 'rb') as file:
        clark_island_geometry = pickle.load(file)
    island = map_polyline_to_pcb_polyline(
        clark_island_geometry[0],
        clark_island_geometry[1],
        projection,
        reverse=True,
    )
    coastline_geometry = "coastline_gerometry.pckl"
    with open('coastline_geometry.pckl', 'rb') as file:
        coastline_geometry_ROI = pickle.load(file)
    outline = map_polyline_to_pcb_polyline(
        coastline_geometry_ROI[0],
        coastline_geometry_ROI[1],
        projection,
    )
    outline.append(PolyLineNode.from_xy(from_mm(200), from_mm(-200)))
    outline.closed = True
    polygon =  PolygonWithHoles()
    polygon.outline = outline
    polygon.add_hole(island)
    zone = Zone()
    zone.layers = ['BL_F_Cu']
    zone.outline = polygon    
    create_items_in_batches([zone])

    # ### BOARD EDGES ###

    edges = []   
    edges.append(board_edge(-width_metres/2, +width_metres/2, +height_metres/2, +height_metres/2, projection))
    edges.append(board_edge(-width_metres/2, +width_metres/2, -height_metres/2, -height_metres/2, projection))
    edges.append(board_edge(+width_metres/2, +width_metres/2, +height_metres/2, -height_metres/2, projection))
    edges.append(board_edge(-width_metres/2, -width_metres/2, +height_metres/2, -height_metres/2, projection))
    board.create_items(edges)

    ### TRACKS ###

    with open('L2_track_geometry.pckl', 'rb') as file:
        L2_track_geometry = pickle.load(file)
    # create_line(L2_track_geometry, projection, layer='BL_B_Cu')
    with open('L3_track_geometry.pckl', 'rb') as file:
        L3_track_geometry = pickle.load(file)
    # create_line(L3_track_geometry, projection, layer='BL_B_Cu')

    ### TRACKS ###
    for train_line in ['T1', 'T2', 'T3', 'T4', 'T8', 'T9']:
        with open(f'{train_line}_tracks_geometry.pckl', 'rb') as file:
            tracks = pickle.load(file)
        create_line(tracks, projection, layer='BL_F_Mask', width = 0.3)

    ### PLACE LEDS ###

    with open('L2_stations_geometry.pckl', 'rb') as file:
        L2_station_geometry = pickle.load(file)
    with open('L3_stations_geometry.pckl', 'rb') as file:
        L3_station_geometry = pickle.load(file)
    reproject_stations(L2_station_geometry, projection)
    reproject_stations(L3_station_geometry, projection)

    LEDs = []
    for footprint in board.get_footprints():
        reference = footprint.reference_field.text.value
        if reference[0] == 'D' and int(reference[1:]) >= 100:
            LEDs.append(footprint)
    LEDs.sort(key=lambda LED: int(LED.reference_field.text.value[1:]))

    via_offset = 0.6
    for idx, station in enumerate(L2_station_geometry):
        LEDs[idx].position = Vector2.from_xy_mm(station.pcb_x,station.pcb_y)
        LEDs[idx].orientation = Angle.from_degrees(station.orientation + 180)
        add_adjacent_via(LEDs[idx], via_offset, 90, 'GND', 'BL_F_Cu', width=0.5)
        add_adjacent_via(LEDs[idx], via_offset, 270, '+5V', 'BL_F_Cu', width=0.5, backside_power=True)
        add_station_outline(station)
        add_station_label(station, flip_label_side=(station.name == "UNSW High Street"))

    for idx, station in enumerate(L3_station_geometry):
        LEDs[idx + len(L2_station_geometry)].position = Vector2.from_xy_mm(station.pcb_x,station.pcb_y)
        LEDs[idx + len(L2_station_geometry)].orientation = Angle.from_degrees(station.orientation + 180)
        add_adjacent_via(LEDs[idx + len(L2_station_geometry)], via_offset, 90, 'GND', 'BL_F_Cu', width=0.5)
        add_adjacent_via(LEDs[idx + len(L2_station_geometry)], via_offset, 270, '+5V', 'BL_F_Cu', width=0.5, backside_power=True)
        add_station_outline(station)
        add_station_label(station, flip_label_side=True)
    board.update_items(LEDs)
    create_items_in_batches(items_to_add)

    # # Load the GeoJSON file
    # with open(geojson_file, "r") as f:
    #     data = json.load(f)


    # lines_to_show = ("L2", "L3")
    # x_origin = 151.22287115
    # y_origin = -33.893729
    
    # scale = 25000
    # x_scale = -1/scale * 111320000 * math.cos(-33.8727) #converts to metres at Sydney latitude
    # y_scale = -1/scale * 111320000 #converts to metres
    # board_origin = (297/2, 420/2)


    # tracks_to_add = []
    # # Loop through features and plot based on geometry type
    # for feature in data["features"]:
    #     geom = feature["geometry"]
    #     geom_type = geom["type"]
    #     coords = geom["coordinates"]
    #     properties = feature["properties"]

    #     if geom_type == "LineString":
    #         if '@relations' in properties.keys():
    #             if properties["@relations"][0]["reltags"]["ref"] in lines_to_show:
    #                 xs, ys = evenly_spaced_points
    #                 for i in range(len(xs) -1):
    #                     x1 = (xs[i] - x_origin)*x_scale + board_origin[0]
    #                     y1 = (ys[i] - y_origin)*y_scale + board_origin[1]
    #                     x2 = (xs[i+1] - x_origin)*x_scale + board_origin[0]
    #                     y2 = (ys[i+1] - y_origin)*y_scale + board_origin[1]
    #                     width = 1
    #                     arcTrack = Track()
    #                     arcTrack.start = Vector2.from_xy_mm(x1, y1)
    #                     arcTrack.end = Vector2.from_xy_mm(x2, y2)
    #                     arcTrack.width = 1
    #                     # arcTrack.attributes.stroke.style = StrokeLineStyle.SLS_SOLID
    #                     arcTrack.layer = 'BL_F_Cu'
    #                     # board.create_items(arcTrack)
    #                     tracks_to_add.append(arcTrack)
    #                     # plt.plot(xs, ys, color=properties["@relations"][0]["reltags"]["colour"])

    # # Define coordinates in mm
    # x1, y1 = 10, 10
    # x2, y2 = 30, 10
    # width = 1

    # arcTrack = Track()
    # arcTrack.start = Vector2.from_xy_mm(x1, y1)
    # arcTrack.end = Vector2.from_xy_mm(x2, y2)
    # arcTrack.width = 1
    # # arcTrack.attributes.stroke.style = StrokeLineStyle.SLS_SOLID
    # arcTrack.layer = 'BL_F_Cu'
    # board.create_items(tracks_to_add)
    # board.create_items(arcTrack)

    # plt.figure()
    # cmap = colormaps['hsv']
    # i = 0
    # for track in tracks_to_add:
    #     plt.plot([track.start.x, track.end.x], [track.start.y, track.end.y], color = cmap(i%1))
    #     i+=0.0001
    # plt.show()
    
