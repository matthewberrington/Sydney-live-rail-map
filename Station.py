from utils import cartesian_to_spherical, spherical_to_cartesian

class Station:
    def __init__(self, name, line, longitude, latitude, map_origin, scale=1.0):
        self.name = name
        self.line = line
        self.longitude = longitude
        self.latitude = latitude
        self.map_origin = map_origin
        self.scale = scale

    @classmethod
    def spherical(cls, name, line, longitude, latitude, map_origin, scale=1.0):
        """Standard constructor using geographic coordinates."""
        return cls(name, line, longitude, latitude, map_origin, scale)

    @classmethod
    def cartesian(cls, name, line, x, y, map_origin, scale=1.0):
        """Alternative constructor using meters from an origin."""
        # Convert meters back to lat/lon so the internal state is consistent
        lon, lat = cartesian_to_spherical(x, y, map_origin)
        return cls(name, line, lon, lat, map_origin, scale)
    
    def get_displacement(self):
        """Returns (x, y) relative to origin."""
        return spherical_to_cartesian(self.longitude, self.latitude, self.map_origin)
    
    def get_pcb_position(self):
        """Calculates scaled PCB coordinates (x, y)."""
        x, y = self.get_displacement()
        return x * self.scale, y * self.scale

    def __repr__(self):
        return f"Station(name='{self.name}', lon={self.longitude:.4f}, lat={self.latitude:.4f})"