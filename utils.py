import math
import numpy as np

def degrees_to_metres(longitudes, latitudes, origin):
    latitudes = np.array(latitudes)
    longitudes = np.array(longitudes)
    # equatorial radius (m)
    a = 6378137
    # eccentricity
    e = 0.081819191

    phi0, theta0 = origin

    deg_to_m_latitude = math.pi * a * (1 - e**2) / (180 * ((1 - e**2 * math.sin(math.radians(theta0))**2))**(3/2))
    deg_to_m_longitude = math.pi * a * math.cos(math.radians(theta0)) / (180 * ((1 - e**2 * math.sin(math.radians(theta0))**2))**(1/2))
    y = deg_to_m_latitude * (latitudes - theta0)
    x = deg_to_m_longitude * (longitudes - phi0)
    return x, y

def get_total_length(xs, ys):
    xs, ys = np.array(xs), np.array(ys)
    dx = np.diff(xs)
    dy = np.diff(ys)
    seg_lengths = np.sqrt(dx**2 + dy**2)
    cumulative = np.insert(np.cumsum(seg_lengths), 0, 0)
    total_length = cumulative[-1]
    return total_length