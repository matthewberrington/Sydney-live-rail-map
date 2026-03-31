# from utils import spherical_to_cartesian, cartesian_to_spherical
import numpy as np

class MapProjection:
    """The 'Single Source of Truth' for map math."""
    def __init__(self, origin_lon, origin_lat, scale=1.0, pcb_origin_mm=(0.0, 0.0)):
        self.origin = (origin_lon, origin_lat)
        self.scale = scale
        self.pcb_origin_mm = pcb_origin_mm

        # equatorial radius (m)
        self.a = 6378137
        # eccentricity
        self.e = 0.081819191

    def geo_to_map(self, lon, lat):
        """Converts GPS to meters (x, y) from origin."""
        latitudes = np.array(lat)
        longitudes = np.array(lon)

        phi0, theta0 = self.origin
        M = np.pi * self.a * (1 - self.e**2) / (180 * ((1 - self.e**2 * np.sin(np.deg2rad(theta0))**2))**(3/2))
        N = np.pi * self.a * np.cos(np.deg2rad(theta0)) / (180 * ((1 - self.e**2 * np.sin(np.deg2rad(theta0))**2))**(1/2))
        y = M * (latitudes - theta0)
        x = N * (longitudes - phi0)
        return x, y
    
    def geo_to_map(self, lon, lat):
        """Converts GPS to map meters (x, y) from origin."""
        latitudes = np.array(lat)
        longitudes = np.array(lon)

        phi0, theta0 = self.origin
        M = np.pi * self.a * (1 - self.e**2) / (180 * ((1 - self.e**2 * np.sin(np.deg2rad(theta0))**2))**(3/2))
        N = np.pi * self.a * np.cos(np.deg2rad(theta0)) / (180 * ((1 - self.e**2 * np.sin(np.deg2rad(theta0))**2))**(1/2))
        y = M * (latitudes - theta0)
        x = N * (longitudes - phi0)
        return x, y
    
    def map_to_geo(self, x, y):
        """Converts map meters (x, y) from origin.to GPS"""
        x = np.array(x)
        y = np.array(y)

        phi0, theta0 = self.origin
        M = np.pi * self.a * (1 - self.e**2) / (180 * ((1 - self.e**2 * np.sin(np.deg2rad(theta0))**2))**(3/2))
        N = np.pi * self.a * np.cos(np.deg2rad(theta0)) / (180 * ((1 - self.e**2 * np.sin(np.deg2rad(theta0))**2))**(1/2))
        latitudes  = y / M + theta0
        longitudes = x / N + phi0
        return longitudes, latitudes

    def map_to_pcb(self, map_x, map_y):
        """Converts map coordinates to PCB coordinates."""
        origin_x, origin_y = self.pcb_origin_mm
        pcb_x = origin_x + map_x * self.scale * 1000
        pcb_y = origin_y - map_y * self.scale * 1000
        return pcb_x, pcb_y

    def pcb_to_map(self, pcb_x, pcb_y):
        """Converts PCB coordinates to map coordinates."""
        origin_x, origin_y = self.pcb_origin_mm
        map_x = (pcb_x - origin_x) / self.scale / 1000
        map_y = (origin_y - pcb_y) / self.scale / 1000
        return map_x, map_y
    
    def geo_to_pcb(self, lon, lat):
        """Converts GPS coordinates to PCB coordinates."""
        map_x, map_y = self.geo_to_map(lon, lat)
        pcb_x, pcb_y = self.map_to_pcb(map_x, map_y)
        return pcb_x, pcb_y

    def pcb_to_geo(self, pcb_x, pcb_y):
        """Converts PCB coordinates to GPS coordinates."""
        map_x, map_y = self.pcb_to_map(pcb_x, pcb_y)
        lon, lat = self.map_to_geo(map_x, map_y)
        return lon, lat
