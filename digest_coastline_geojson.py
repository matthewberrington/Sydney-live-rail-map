from shapely.geometry import LineString, Point
from shapely.ops import linemerge, unary_union
import json
import matplotlib.pyplot as plt
import numpy as np
from utils import degrees_to_metres
import pickle


def to_ordered_coords(segments):
    merged = linemerge(unary_union(segments))
    if merged.geom_type == "MultiLineString":
        ordered_coords = [list(ls.coords) for ls in merged.geoms]
    else:
        ordered_coords = list(merged.coords)
    return ordered_coords


if __name__ == '__main__':
    with open("coastline.geojson") as f:
        data = json.load(f)

    segments = []

    
    for feature in data['features']:
        geom = feature['geometry']
        if geom['type'] == 'LineString':
            segments.append(LineString(geom["coordinates"]))


            
    origin = (151.22289335, -33.8937485)
    ordered_segments = to_ordered_coords(segments)
    coastline_geometry = []
    
    plt.figure()
    for seg in ordered_segments:
        xs_coastline, ys_coastline = degrees_to_metres(*zip(*seg), origin)
        coastline_geometry.append((xs_coastline, ys_coastline))
        plt.plot(xs_coastline, ys_coastline)
    plt.gca().axis('equal')

    with open('coastline_geometry.pckl', 'wb') as file:
        pickle.dump(coastline_geometry, file)

    plt.fill_between([-100*25, 100*25], -160*25, 160*25, color='lightgray', alpha=0.5) 
    plt.show()
