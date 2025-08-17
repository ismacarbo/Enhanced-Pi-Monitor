import numpy as np
import occupancyGrid as ogmod


X_MIN, X_MAX = -50, 50
Y_MIN, Y_MAX = -50, 50
RESOLUTION   = 5

_grid = ogmod.OccupancyGrid(X_MIN, X_MAX, Y_MIN, Y_MAX, RESOLUTION)

def update_from_points(points):
    """
    points: list di dict {"angle": gradi, "distance": valore}
    """
    scan = [(np.deg2rad(pt['angle']), pt['distance']) for pt in points]
    robot_pose = (0.0, 0.0, 0.0)
    _grid.inverse_sensor_update(robot_pose, scan)
    _grid.clampLogOdds()

def get_probability_map():
    return _grid.getProbabilityMap().tolist()
