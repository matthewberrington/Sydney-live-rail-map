from kipy import KiCad
import kipy
from kipy.board_types import BoardText, BoardSegment, BoardArc, Via, Net, Track, ArcTrack
from kipy.geometry import Vector2, Angle
from kipy.util import from_mm
from kipy.proto.common import HorizontalAlignment, VerticalAlignment, StrokeLineStyle
import json
import matplotlib.pyplot as plt
import math
from matplotlib import colormaps
import pickle
from utils import get_total_length, degrees_to_metres

def draw_line(
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        width: float = 0.1,
        style=StrokeLineStyle.SLS_SOLID,
        net: str = "",
        layer='BL_F_SilkS',
    ) -> None:
        boardSegment = BoardSegment()
        boardSegment.start = Vector2.from_xy_mm(x1, y1)
        boardSegment.end = Vector2.from_xy_mm(x2, y2)
        boardSegment.attributes.stroke.width = from_mm(width)
        boardSegment.attributes.stroke.style = style
        boardSegment.layer = layer
    
        if net != "":
            boardSegment.net = get_net_by_name(net)
    
        text_to_add.append(boardSegment)  # Store the segment for later addition
    

def draw_station_rectangle(
        x: float,
        y: float,
        width: float,
        height: float,
        angle: float = 0,
        line_width: float = 0.2,
    ):
        # Calculate the four corners of the rectangle centered at (x, y)
        hw = width / 2
        hh = height / 2
    
        # Rectangle corners before rotation (relative to center)
        corners = [(x - hw, y - hh), (x + hw, y - hh), (x + hw, y + hh), (x - hw, y + hh)]
    
        # Rotate each corner around (x, y) by 'angle' degrees
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
    
        # Draw lines between consecutive corners
        for i in range(4):
            x1, y1 = rotated_corners[i]
            x2, y2 = rotated_corners[(i + 1) % 4]
            draw_line(x1, y1, x2, y2, line_width)


def draw_text(
    x: float,
    y: float,
    text: str,
    angle: float = 0,
    font_size_mm: float = 1.5,
    layer="BL_F_SilkS",
    bold=False,
    alignment = HorizontalAlignment.HA_LEFT
    ):
        boardText = BoardText()
        boardText.value = text
        boardText.layer = layer
        boardText.attributes.angle = angle
        boardText.attributes.font_name = "Gotham Narrow Medium"
        boardText.attributes.size = Vector2.from_xy_mm(font_size_mm, font_size_mm)
        boardText.attributes.bold = bold
        boardText.position = Vector2.from_xy_mm(x, y)
        boardText.attributes.vertical_alignment = VerticalAlignment.VA_CENTER
        boardText.attributes.horizontal_alignment = alignment
        text_to_add.append(boardText)  # Store the text for later addition

if __name__=='__main__':

    with open('LED_geometry.pckl', 'rb') as file:
        # Use pickle.load() to deserialize the object from the file
        LED_geometry = pickle.load(file)

    with open('station_geometry.pckl', 'rb') as file:
        # Use pickle.load() to deserialize the object from the file
        station_geometry = pickle.load(file)

    with open('coastline_geometry.pckl', 'rb') as file:
        # Use pickle.load() to deserialize the object from the file
        coastline_geometry = pickle.load(file)        
    try:
        kicad = KiCad()
        print(f"Connected to KiCad {kicad.get_version()}")
    except BaseException as e:
        print(f"Not connected to KiCad: {e}")

    kicad = KiCad()
    board = kicad.get_board()

    # Path to your GeoJSON file
    geojson_file = "export.geojson"

    # Load the GeoJSON file
    with open(geojson_file, "r") as f:
        data = json.load(f)

    board_origin = (297/2, 420/2)

    modified_components = []
    for footprint in board.get_footprints():
        ref = footprint.reference_field.text.value
        if ref in LED_geometry.keys():
            x, y, theta = LED_geometry[ref]
            footprint.position = Vector2.from_xy_mm(x/25 + board_origin[0],-y/25 + board_origin[1])
            footprint.orientation = Angle.from_degrees(theta + 180)
            modified_components.append(footprint)

    line_width = 0.4
    line_clearance = 0.05
    outline_offset = line_width + line_clearance * 2
    outline_width = 2.4 + outline_offset
    extra_platforms = 0
    outline_height = (1.6 + outline_offset) + (1.6 + 0.4) * (extra_platforms)
    text_to_add = []
    text_offset = 3
    for station in station_geometry.values():
        x_station, y_station, angle_station, name_station, line = station
        if line == 'L2':
            alignment = HorizontalAlignment.HA_LEFT
            dx = text_offset
        elif line == 'L3':
            alignment = HorizontalAlignment.HA_RIGHT
            dx = -text_offset
        draw_text(
            x_station/25 + board_origin[0] + dx,
            -y_station/25 + board_origin[1],
            name_station,
            0,
            font_size_mm = 4,
            alignment = alignment
            )
        draw_station_rectangle(
            x_station/25 + board_origin[0],
            -y_station/25 + board_origin[1],
            outline_width,
            outline_height,
            angle_station,
            line_width)

    for coastline in coastline_geometry:
        for i in range(1,len(coastline[0])):
            draw_line(
                coastline[0][i-1]/25 + board_origin[0],
                -coastline[1][i-1]/25 + board_origin[1],
                coastline[0][i]/25 + board_origin[0],
                -coastline[1][i]/25 + board_origin[1],
                width = 0.5
            )


    origin = (151.22289335, -33.8937485)
    yummy_pepper_house = (151.226780, -33.922423)

    x_YPH, yYPH = degrees_to_metres(*yummy_pepper_house, origin)

    draw_station_rectangle(
        (x_YPH)/25 + board_origin[0],
        -yYPH/25 + board_origin[1],
        outline_width,
        outline_height,
        0,
        line_width)

    board.update_items(modified_components)
    board.create_items(text_to_add)    

    # print(f"Moved C1 to ({x1} mm, {y1} mm)")
    
    x1, y1 = 10, 10
    x2, y2 = 30, 10
    width = from_mm(1)
    arcTrack = Track()
    arcTrack.start = Vector2.from_xy_mm(x1, y1)
    arcTrack.end = Vector2.from_xy_mm(x2, y2)
    arcTrack.width = 1
    # arcTrack.attributes.stroke.style = StrokeLineStyle.SLS_SOLID
    arcTrack.layer = 'BL_B_Cu'
    board.create_items(arcTrack)