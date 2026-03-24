from kipy import KiCad
import kipy
from kipy.board_types import BoardText, BoardSegment, BoardArc, Via, Net, Track, ArcTrack, BoardSegment, Zone
from kipy.geometry import Vector2, Angle, PolygonWithHoles, PolyLineNode, PolyLine
from kipy.util import from_mm
import json
import matplotlib.pyplot as plt
import math
import pickle
from matplotlib import colormaps

def board_edge(x0, x1, y0, y1, scale):
    arcTrack = BoardSegment()
    arcTrack.start = Vector2.from_xy_mm(x0/scale*1000, -y0/scale*1000)
    arcTrack.end = Vector2.from_xy_mm(x1/scale*1000, -y1/scale*1000)
    arcTrack.width = 1
    arcTrack.layer = 'BL_Edge_Cuts'
    return arcTrack

if __name__=='__main__':
    try:
        kicad = KiCad()
        print(f"Connected to KiCad {kicad.get_version()}")
    except BaseException as e:
        print(f"Not connected to KiCad: {e}")

    kicad = KiCad()
    board = kicad.get_board()
    width_metres = 5000
    height_metres = 8000
    scale = 25000

    ### CREATE COASTLINE ###


    clark_island_geometry = "clark_island_geometry.pckl"
    with open('clark_island_geometry.pckl', 'rb') as file:
        clark_island_geometry = pickle.load(file)
    island = PolyLine()
    points = list(zip(*clark_island_geometry))
    points.reverse()  # flip winding direction
    for x, y in points:
        island.append(PolyLineNode.from_xy(from_mm(x/scale*1000), from_mm(-y/scale*1000)))
    coastline_geometry = "coastline_gerometry.pckl"
    with open('coastline_geometry.pckl', 'rb') as file:
        coastline_geometry_ROI = pickle.load(file)
    outline = PolyLine()
    points = zip(*coastline_geometry_ROI)
    for x, y in points:
        outline.append(PolyLineNode.from_xy(from_mm(x/scale*1000), from_mm(-y/scale*1000)))
    outline.append(PolyLineNode.from_xy(from_mm(200), from_mm(-200)))
    outline.closed = True
    polygon =  PolygonWithHoles()
    polygon.outline = outline
    polygon.add_hole(island)
    zone = Zone()
    zone.layers = ['BL_F_Cu']
    zone.outline = polygon    
    board.create_items(zone)

    ### BOARD EDGES ###

    edges = []   
    edges.append(board_edge(-width_metres/2, +width_metres/2, +height_metres/2, +height_metres/2, scale))
    edges.append(board_edge(-width_metres/2, +width_metres/2, -height_metres/2, -height_metres/2, scale))
    edges.append(board_edge(+width_metres/2, +width_metres/2, +height_metres/2, -height_metres/2, scale))
    edges.append(board_edge(-width_metres/2, -width_metres/2, +height_metres/2, -height_metres/2, scale))
    board.create_items(edges)

    ### COASTLINE ###
    # coastline_geometry = "coastline_gerometry.pckl"

    # with open('coastline_geometry.pckl', 'rb') as file:
    #     coastline_geometry_ROI = pickle.load(file)
    # silkscreen_coastline = []

    # for [x0, x1], [y0, y1] in coastline_geometry_ROI:
    #     boardSegment = BoardSegment()
    #     boardSegment.start = Vector2.from_xy_mm(x0/scale*1000, -y0/scale*1000)
    #     boardSegment.end = Vector2.from_xy_mm(x1/scale*1000, -y1/scale*1000)
    #     boardSegment.attributes.stroke.width = from_mm(1)
    #     # arcTrack.attributes.stroke.style = StrokeLineStyle.SLS_SOLID
    #     boardSegment.layer = 'BL_F_SilkS'
    #     silkscreen_coastline.append(boardSegment)
    # board.create_items(silkscreen_coastline)

    # zone = Zone()
    # zone.layers = ['BL_F_Cu']
    # zone.clearance = 0
    # zone.outline([0,0,1,1])


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
    
