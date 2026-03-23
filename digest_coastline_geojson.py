from shapely.geometry import LineString, Point
from shapely.ops import linemerge, unary_union
import json
import matplotlib.pyplot as plt
from utils import get_total_length, degrees_to_metres
import pickle


def to_ordered_coords(segments):
    merged = linemerge(unary_union(segments))
    if merged.geom_type == "MultiLineString":
        ordered_coords = [list(ls.coords) for ls in merged.geoms]
    else:
        ordered_coords = list(merged.coords)
    return ordered_coords

def within_boundary(x, y, width, height):
    within_width = (-width / 2 < x) and (x < width/2)
    within_height = (-height / 2 < y) and (y < height/2)
    return within_width and within_height

if __name__ == '__main__':
    with open("coastline.geojson") as f:
        data = json.load(f)

    segments = []

    
    for feature in data['features']:
        geom = feature['geometry']
        if geom['type'] == 'LineString':
            segments.append(LineString(geom["coordinates"]))
            
    origin = (151.22289335, -33.8937485)
    width_metres = 5000
    height_metres = 8000
    ordered_segments = to_ordered_coords(segments)
    coastline_geometry = []
    coastline_geometry_ROI = []
    
    plt.figure()
    for seg in ordered_segments:
        xs_coastline, ys_coastline = degrees_to_metres(*zip(*seg), origin)
        coastline_geometry.append((xs_coastline, ys_coastline))
        plt.plot(xs_coastline, ys_coastline)

    for seg in ordered_segments:
        xs_coastline, ys_coastline = degrees_to_metres(*zip(*seg), origin)
        xy = zip(xs_coastline, ys_coastline)
        for i in range(len(xs_coastline)-1):
            x0 = xs_coastline[i]
            y0 = ys_coastline[i]
            x1 = xs_coastline[i+1]
            y1 = ys_coastline[i+1]
            if within_boundary(x0, y0, width_metres, height_metres) or within_boundary(x1, y1, width_metres, height_metres):
                coastline_geometry_ROI.append(([x0, x1], [y0, y1]))

    for [x0, x1], [y0, y1] in coastline_geometry_ROI:
        plt.plot([x0, x1], [y0, y1], 'k')
    plt.gca().axis('equal')

    with open('coastline_geometry.pckl', 'wb') as file:
        pickle.dump(coastline_geometry_ROI, file)

    plt.fill_between([-width_metres/2, width_metres/2], -height_metres/2, height_metres/2, color='lightgray', alpha=0.5)
    plt.show()
