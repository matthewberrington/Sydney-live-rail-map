from utils import degrees_to_metres
class Station:
    def __init__(self, name):
        self.name = name
    
    def set_coordinates(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude
    
    def set_orientation(self, orientation):
        self.orientation = orientation

    def set_pcb_position(self, origin, scale):
        # Convert degrees to meters north and east of origin
        displacement_m = degrees_to_metres(self.longitudes, self.latitudes, origin)
        # Convert latitude and longitude to PCB coordinates
        self.pcb_x = displacement_m[0] * scale
        self.pcb_y = displacement_m[1] * scale