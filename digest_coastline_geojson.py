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

    xs, ys = coastline_geometry[0]
    plt.plot(xs[500:3000],ys[500:3000], c='k')
    plt.gca().axis('equal')
    coastline_geometry_ROI = [xs[500:3000],ys[500:3000]]

    with open('coastline_geometry.pckl', 'wb') as file:
        pickle.dump(coastline_geometry_ROI, file)

    clark_island_geometry = coastline_geometry[14]
    plt.plot(*clark_island_geometry, c='k')
    with open('clark_island_geometry.pckl', 'wb') as file:
        pickle.dump(clark_island_geometry, file)

    plt.fill_between([-width_metres/2, width_metres/2], -height_metres/2, height_metres/2, color='lightgray', alpha=0.5)
    plt.show()