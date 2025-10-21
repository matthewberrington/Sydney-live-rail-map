import json
import matplotlib.pyplot as plt

# Path to your GeoJSON file
geojson_file = "export.geojson"

# Load the GeoJSON file
with open(geojson_file, "r") as f:
    data = json.load(f)

# Create a plot
plt.figure(figsize=(12, 8))


lines_to_show = ("L2", "L3")
# Loop through features and plot based on geometry type
for feature in data["features"]:
    geom = feature["geometry"]
    geom_type = geom["type"]
    coords = geom["coordinates"]
    properties = feature["properties"]

    if geom_type == "Point":
        
        if "railway" in properties.keys():
            if '@relations' in properties.keys():
                if properties["@relations"][0]["reltags"]["ref"] in lines_to_show:
                    if properties["@relations"][0]["reltags"]["to"] == 'Circular Quay':
                        if properties["railway"] == 'stop':
                            x, y = coords
                            plt.scatter(x, y, color="black", s=10)
                            plt.text(x, y, properties["name"])

    if geom_type == "LineString":
        if '@relations' in properties.keys():
            if properties["@relations"][0]["reltags"]["ref"] in lines_to_show:
                xs, ys = zip(*coords)
                plt.plot(xs, ys, color=properties["@relations"][0]["reltags"]["colour"])

    # elif geom_type == "Polygon":
    #     for ring in coords:
    #         xs, ys = zip(*ring)
    #         plt.plot(xs, ys, color="green")

    # if geom_type == "MultiLineString":
    #     if properties['@id'] == 'relation/10411681':
    #         if properties["ref"] == "L1":
    #             color = 'red'
    #         elif properties["ref"] == "L2":
    #             color = 'blue'
    #         elif properties["ref"] == "L3":
    #             color = 'green'
    #         for line in coords:
    #             xs, ys = zip(*line)
    #             plt.plot(xs, ys, color=color)



    # elif geom_type == "MultiPolygon":
    #     for poly in coords:
    #         for ring in poly:
    #             xs, ys = zip(*ring)
    #             plt.plot(xs, ys, color="orange")

plt.title("GeoJSON Geometry Plot")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.axis("equal")
xlim = plt.gca().get_xlim()
ylim = plt.gca().get_ylim()
print((xlim[0] + xlim[1])/2)
print((ylim[0] + ylim[1])/2)
plt.show()
