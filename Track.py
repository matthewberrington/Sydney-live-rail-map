from shapely.geometry import LineString, Point
import MapProjection
import math

class Track:
    def __init__(self, name, longitudes, latitudes, projection: MapProjection):
        self.name = name
        self.longitudes = longitudes
        self.latitudes = latitudes
        self.projection = projection
        
        # Build geometry using the shared projection
        self.map_x, self.map_y = self.projection.geo_to_map(longitudes, latitudes)
        self.line_cartesian = LineString(list(zip(self.map_x, self.map_y)))
        self.line_spherical = LineString(list(zip(longitudes, latitudes)))
        self.stations = []

    def get_tangent_at_dist(self, dist):
        """Calculates rotation at a specific distance along the track."""
        p1 = self.line_cartesian.interpolate(dist)
        p2 = self.line_cartesian.interpolate(min(dist + 0.1, self.line_cartesian.length))
        return math.degrees(math.atan2(p2.y - p1.y, p2.x - p1.x))

# from utils import spherical_to_cartesian
# from shapely.geometry import LineString, Point

# class Track:
#     def __init__(self, name, longitudes, latitudes, map_origin, scale=1.0):
#         self.name = name
#         self.latitudes = latitudes
#         self.longitudes = longitudes
#         self.map_origin = map_origin
#         self.scale = scale
#         self.line_spherical = self.get_line_spherical()
#         self.line_cartesian = self.get_line_cartesian()

#     def get_displacements(self):
#         x, y = spherical_to_cartesian(
#             self.longitudes, 
#             self.latitudes, 
#             self.map_origin
#         )
#         return x, y
    
#     def get_line_spherical(self):
#         line = LineString(list(zip(self.longitudes, self.latitudes)))
#         return line

#     def get_line_cartesian(self):
#         line = LineString(list(zip(*self.get_displacements())))
#         return line

#     def distance_along(self,station):
#         pt = Point(*station.get_displacement())
#         length = self.line_cartesian.project(pt)
#         return length

#     def get_pcb_positions(self):
#         """
#         Calculates the PCB coordinates (x, y) based on the station's 
#         location relative to the map origin and scale.
#         """
#         displacement_m = spherical_to_cartesian(
#             self.longitudes, 
#             self.latitudes, 
#             self.map_origin
#         )
        
#         pcb_x = displacement_m[0] * self.scale
#         pcb_y = displacement_m[1] * self.scale
        
#         return pcb_x, pcb_y
    
