import os
import matplotlib.pyplot as plt

def read_airfoil_coords(airfoil, coord_path):
    '''Read airfoil coordinates from a file. If the airfoil is a NACA 4-digit series, we will read the coordinates from the specified coord_path.
    If it's a custom airfoil, we will read the coordinates from the file path provided in the airfoil variable (after stripping any "load " prefix).
    The coordinate files are expected to have two columns: x and y, which represent the normalized chordwise and thickness coordinates of the airfoil shape.
    We will return two lists: x_coords and y_coords, which contain the x and y coordinates of the airfoil shape, respectively.

    Arguments: - airfoil: a string identifier for the airfoil, which can be a NACA 4-digit series (e.g. "NACA 2412") or a custom airfoil with a file path (e.g. "load custom_airfoil.dat")
               - coord_path: the file path to the coordinate file for NACA airfoils (e.g. "naca2412.dat")

    Returns: - x_coords: a list of x coordinates of the airfoil shape
             - y_coords: a list of y coordinates of the airfoil shape'''
    x_coords = []
    y_coords = []

    if airfoil.lower().startswith("naca"):
        filepath = coord_path
    else:
        filepath = airfoil.replace("load ", "").strip()


    try:
        with open(filepath, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        x = float(parts[0])
                        y = float(parts[1])
                        x_coords.append(x)
                        y_coords.append(y)
                    except ValueError:
                        continue
    except FileNotFoundError:
        print(f"Coordinate file not found: {filepath}")

    return x_coords, y_coords

def plot_airfoil(x_coords, y_coords, airfoil_name):
    '''Plot the airfoil geometry using the provided x and y coordinates. We will create a simple line plot of the airfoil shape, with appropriate labels and title.

    Arguments: - x_coords: a list of x coordinates of the airfoil shape
               - y_coords: a list of y coordinates of the airfoil shape
               - airfoil_name: a string identifier for the airfoil (used for labeling)

    Returns: - fig: the matplotlib figure object containing the plot, which can be saved or displayed later.'''
    if not x_coords:
        print("No coordinates found. Cannot plot airfoil.")
        return

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(x_coords, y_coords, 'k-', linewidth=1.5)
    ax.set_aspect('equal')
    ax.set_xlabel('x/c')
    ax.set_ylabel('y/c')
    ax.set_title(f'Airfoil Geometry: {airfoil_name.upper()}')
    ax.grid(True)
    plt.tight_layout()
    return fig
