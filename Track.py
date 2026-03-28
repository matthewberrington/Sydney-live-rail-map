from utils import spherical_to_cartesian
from shapely.geometry import LineString, Point

class Track:
    def __init__(self, name, longitudes, latitudes, map_origin, scale=1.0):
        self.name = name
        self.latitudes = latitudes
        self.longitudes = longitudes
        self.map_origin = map_origin
        self.scale = scale
        self.line_spherical = self.get_line_spherical()
        self.line_cartesian = self.get_line_cartesian()

    def get_displacements(self):
        x, y = spherical_to_cartesian(
            self.longitudes, 
            self.latitudes, 
            self.map_origin
        )
        return x, y
    
    def get_line_spherical(self):
        line = LineString(list(zip(self.longitudes, self.latitudes)))
        return line

    def get_line_cartesian(self):
        line = LineString(list(zip(*self.get_displacements())))
        return line

    def distance_along(self,station):
        pt = Point(*station.get_displacement())
        length = self.line_cartesian.project(pt)
        return length

    def get_pcb_positions(self):
        """
        Calculates the PCB coordinates (x, y) based on the station's 
        location relative to the map origin and scale.
        """
        displacement_m = spherical_to_cartesian(
            self.longitudes, 
            self.latitudes, 
            self.map_origin
        )
        
        pcb_x = displacement_m[0] * self.scale
        pcb_y = displacement_m[1] * self.scale
        
        return pcb_x, pcb_y
    
