import math
import numpy as np
# equatorial radius (m)
a = 6378137
# eccentricity
e = 0.081819191

# def spherical_to_cartesian(longitudes, latitudes, origin):
#     latitudes = np.array(latitudes)
#     longitudes = np.array(longitudes)

#     phi0, theta0 = origin
#     M = math.pi * a * (1 - e**2) / (180 * ((1 - e**2 * math.sin(math.radians(theta0))**2))**(3/2))
#     N = math.pi * a * math.cos(math.radians(theta0)) / (180 * ((1 - e**2 * math.sin(math.radians(theta0))**2))**(1/2))
#     y = M * (latitudes - theta0)
#     x = N * (longitudes - phi0)
#     return x, y

# def cartesian_to_spherical(x, y, origin):
#     x = np.array(x)
#     y = np.array(y)

#     phi0, theta0 = origin
#     M = math.pi * a * (1 - e**2) / (180 * ((1 - e**2 * math.sin(math.radians(theta0))**2))**(3/2))
#     N = math.pi * a * math.cos(math.radians(theta0)) / (180 * ((1 - e**2 * math.sin(math.radians(theta0))**2))**(1/2))
#     latitudes  = y / M + theta0
#     longitudes = x / N + phi0
#     return longitudes, latitudes
