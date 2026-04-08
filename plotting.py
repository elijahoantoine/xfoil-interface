import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

#======== Plotting Functions ========
def get_airfoil_label(airfoil):
    '''Extracts a clean label for the airfoil from the input string, handling both NACA designations and file paths. 
    For NACA airfoils, it returns the uppercase designation. For file paths, it extracts the base name without extension and returns it in uppercase. 
    This ensures consistent labeling across different input formats.
    
    Arguments: - airfoil: a string that is either a NACA designation (e.g. "naca2412") or a file path to an airfoil coordinate file (e.g. "path/to/airfoil.dat").
    
    Returns: - A clean, uppercase label for the airfoil that can be used in plot titles and legends.'''
    if airfoil.lower().startswith("naca"):
        return airfoil.upper()
    else:
        return os.path.splitext(os.path.basename(airfoil.replace("load ", "").strip()))[0].upper()

def plot_liftvsAoA(aoa_values, lift_coeffs, airfoil_name, desired_aoas, aoa_step, results, reynolds=None):
    '''Plots the lift coefficient (CL) versus angle of attack (AoA) curve for a given airfoil, with annotations for stall and selected AoA points.

    Arguments: - aoa_values: list of AoA values (degrees) for which CL was computed
               - lift_coeffs: corresponding list of CL values 
               - airfoil_name: string identifier for the airfoil (used for labeling)
               - desired_aoas: list of AoA values that were specifically selected for analysis (used for highlighting points on the plot)
               - aoa_step: the step size used in the AoA sweep (used to determine whether to plot the selected AoA points)
               - results: the full results dictionary containing CL values for all AoA (used to extract CL for the selected AoA points)
               - reynolds: the Reynolds number for this dataset (used for labeling)
               
    Returns: - fig: the matplotlib figure object containing the plot, which can be saved or displayed later.'''
    
    if not aoa_values or not lift_coeffs:
        print("No data available to plot Lift vs AoA.")
        return

    label = get_airfoil_label(airfoil_name)
    fig, ax = plt.subplots(figsize=(10, 5))
    
    ax.plot(aoa_values, lift_coeffs, 'g-', linewidth=1.5, label='CL curve')

    max_cl = max(lift_coeffs)
    max_idx = lift_coeffs.index(max_cl)
    if max_idx < len(lift_coeffs) - 1:
        stall_aoa = aoa_values[max_idx]
        ax.axvline(x=stall_aoa, color='r', linestyle='--', linewidth=1.2,
                   label=f'Stall (α = {stall_aoa}°)')

    if aoa_step > 0.2:
        desired_cls = [results[aoa]['CL'] for aoa in desired_aoas if aoa in results and results[aoa] is not None]
        desired_aoas_clean = [aoa for aoa in desired_aoas if aoa in results and results[aoa] is not None]
        ax.plot(desired_aoas_clean, desired_cls, 'go', markersize=5, label='Selected AoA points')

    ax.set_xlabel('Angle of Attack (degrees)')
    ax.set_ylabel('Lift Coefficient (CL)')
    re_str = f" - Re = {reynolds:.2e}" if reynolds is not None else ""
    ax.set_title(f'CL vs Angle of Attack: {label}{re_str}')
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    return fig

def plot_dragpolar(drag_coeffs, lift_coeffs, airfoil_name, reynolds=None):
    '''Plots the drag polar (CL vs CD) for a given airfoil, with annotations for Reynolds number.
    
    Arguments: - drag_coeffs: list of drag coefficient (CD) values corresponding to the AoA sweep
               - lift_coeffs: list of lift coefficient (CL) values corresponding to the AoA sweep
               - airfoil_name: string identifier for the airfoil (used for labeling)
               - reynolds: the Reynolds number for this dataset (used for labeling)
               
    Returns: - fig: the matplotlib figure object containing the plot, which can be saved or displayed later.'''
    if not lift_coeffs or not drag_coeffs:
        print("No data available to plot drag polar.")
        return

    label = get_airfoil_label(airfoil_name)
    fig, ax = plt.subplots(figsize=(6, 8))
    ax.plot(drag_coeffs, lift_coeffs, 'r-', linewidth=1.5)
    ax.set_xlabel('Drag Coefficient (CD)')
    ax.set_ylabel('Lift Coefficient (CL)')
    re_str = f" - Re = {reynolds:.2e}" if reynolds is not None else ""
    ax.set_title(f'Drag Polar: {label}{re_str}')
    ax.grid(True)
    plt.tight_layout()
    return fig

def plot_Cp_distribution(cp_x, cp_values, airfoil_coords, airfoil_name, aoa, cl, cd, cm, cdp, reynolds=None):
    '''Plots the Cp distribution along the airfoil surface for a given angle of attack, with annotations for CL, CD, CM, CDp, and Reynolds number.
    
    Arguments: - cp_x: list of x/c positions along the chord where Cp was computed
               - cp_values: list of Cp values corresponding to the cp_x positions
                - airfoil_coords: tuple of (x_coords, y_coords) for the airfoil shape (used for plotting the airfoil outline)
                - airfoil_name: string identifier for the airfoil (used for labeling)
                - aoa: the angle of attack for which to plot the Cp distribution
                - cl: the lift coefficient for the given angle of attack
                - cd: the drag coefficient for the given angle of attack
                - cm: the moment coefficient for the given angle of attack
                - cdp: the parasitic drag coefficient for the given angle of attack
                - reynolds: the Reynolds number for this dataset (used for labeling)
        
    Returns: - fig: the matplotlib figure object containing the plot, which can be saved or displayed later.'''

    if not cp_x or not cp_values:
        print("No data available to plot Cp distribution.")
        return

    label = get_airfoil_label(airfoil_name)
    fig, (ax_cp, ax_af) = plt.subplots(2, 1, figsize=(10, 8),
                                        gridspec_kw={'height_ratios': [3, 1]})

    ax_cp.plot(cp_x, cp_values, 'b-', linewidth=1.5)
    ax_cp.invert_yaxis()
    ax_cp.set_xlabel('x/c')
    ax_cp.set_ylabel('Cp')
    re_str = f" - Re = {reynolds:.2e}" if reynolds is not None else ""
    ax_cp.set_title(f'Cp Distribution: {label} — α = {aoa}°{re_str}')
    ax_cp.grid(True)

    cl_str  = f"{cl:.4f}"  if cl  is not None else "N/A"
    cd_str  = f"{cd:.5f}"  if cd  is not None else "N/A"
    cm_str  = f"{cm:.4f}"  if cm  is not None else "N/A"
    cdp_str = f"{cdp:.5f}" if cdp is not None else "N/A"

    info = f"α = {aoa}°\nCL = {cl_str}\nCD = {cd_str}\nCM = {cm_str}\nCDp = {cdp_str}"
    ax_cp.text(0.98, 0.98, info, transform=ax_cp.transAxes,
               fontsize=9, verticalalignment='top', horizontalalignment='right',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    if airfoil_coords and len(airfoil_coords[0]) > 0:
        ax_af.plot(airfoil_coords[0], airfoil_coords[1], 'k-', linewidth=1.5)
        ax_af.set_aspect('equal')
        ax_af.set_xlabel('x/c')
        ax_af.set_ylabel('y/c')
        ax_af.grid(True)

    plt.tight_layout()
    return fig

def plot_liftvsAoA_multi(all_results, airfoil_name, experimental_data=None):
    '''Plots the lift coefficient (CL) versus angle of attack (AoA) curves for multiple Reynolds numbers on the same plot for comparison, 
    with annotations for stall and optional experimental data points.
    
    Arguments: - all_results: a dictionary where keys are Reynolds numbers (or None for inviscid) and values are the results dictionaries containing CL values for each AoA
               - airfoil_name: string identifier for the airfoil (used for labeling)
               - experimental_data: optional dictionary of experimental data points to overlay on the plot, where keys are labels for the experimental datasets and values are tuples of (aoa_values, cl_values)
               
    Returns: - fig: the matplotlib figure object containing the plot, which can be saved or displayed later.'''

    label = get_airfoil_label(airfoil_name)
    fig, ax = plt.subplots(figsize=(10, 5))
    
    colors = plt.cm.tab10.colors  # up to 10 distinct colors
    
    for i, (reynolds, results) in enumerate(all_results.items()):
        if not results:
            continue
        aoas = sorted(results.keys())
        cls = [results[aoa]['CL'] for aoa in aoas]
        re_str = f"Re = {reynolds:.2e}" if reynolds is not None else "Inviscid"
        color = colors[i % len(colors)]
        ax.plot(aoas, cls, linewidth=1.5, label=re_str, color=color)

        # stall detection per Re
        max_cl = max(cls)
        max_idx = cls.index(max_cl)
        if max_idx < len(cls) - 1:
            stall_aoa = aoas[max_idx]
            ax.axvline(x=stall_aoa, color=color, linestyle='--', linewidth=1.0, alpha=0.7)

    if experimental_data is not None:
        for label_exp, (exp_aoas, exp_cls) in experimental_data.items():
            ax.scatter(exp_aoas, exp_cls, marker='x', s=20, label=f"Exp: {label_exp}")

    ax.set_xlabel('Angle of Attack (degrees)')
    ax.set_ylabel('Lift Coefficient (CL)')
    ax.set_title(f'CL vs Angle of Attack: {label} — Multi-Re Comparison')
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    return fig

#======== Multi Plotting Functions ========
def plot_dragpolar_multi(all_results, airfoil_name, experimental_data=None):
    '''Plots the drag polar (CL vs CD) curves for multiple Reynolds numbers on the same plot for comparison, with optional experimental data points.
    
    Arguments: - all_results: a dictionary where keys are Reynolds numbers (or None for inviscid) and values are the results dictionaries containing CL and CD values for each AoA
               - airfoil_name: string identifier for the airfoil (used for labeling)
               - experimental_data: optional dictionary of experimental data points to overlay on the plot, where keys are labels for the experimental datasets and values are tuples of (cd_values, cl_values)
               
    Returns: - fig: the matplotlib figure object containing the plot, which can be saved or displayed later.'''

    label = get_airfoil_label(airfoil_name)
    fig, ax = plt.subplots(figsize=(6, 8))
    
    colors = plt.cm.tab10.colors

    for i, (reynolds, results) in enumerate(all_results.items()):
        if not results:
            continue
        aoas = sorted(results.keys())
        cls = [results[aoa]['CL'] for aoa in aoas]
        cds = [results[aoa]['CD'] for aoa in aoas]
        re_str = f"Re = {reynolds:.2e}" if reynolds is not None else "Inviscid"
        ax.plot(cds, cls, linewidth=1.5, label=re_str, color=colors[i % len(colors)])

    if experimental_data is not None:
        for label_exp, (exp_cds, exp_cls) in experimental_data.items():
            ax.scatter(exp_cds, exp_cls, marker='x', s=20, label=f"Exp: {label_exp}")

    ax.set_xlabel('Drag Coefficient (CD)')
    ax.set_ylabel('Lift Coefficient (CL)')
    ax.set_title(f'Drag Polar: {label} — Multi-Re Comparison')
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    return fig

def plot_Cp_multi(cp_data, airfoil_coords, airfoil_name, reynolds, experimental_data=None):
    '''Plot the Cp distribution for multiple AoA on the same plot for comparison, with annotations for Reynolds number and optional experimental data points.
    
    Arguments: - cp_data: a dictionary where keys are AoA values and values are tuples of (cp_x, cp_values) for that AoA
               - airfoil_coords: tuple of (x_coords, y_coords) for the airfoil shape (used for plotting the airfoil outline)
               - airfoil_name: string identifier for the airfoil (used for labeling)
               - reynolds: Reynolds number for the plot annotation
               - experimental_data: optional dictionary of experimental data points to overlay on the plot, where keys are labels for the experimental datasets and values are tuples of (cp_x, cp_values)
               
    Returns: - fig: the matplotlib figure object containing the plot, which can be saved or displayed later.'''
    # cp_data is a dict of {aoa: (cp_x, cp_values)}
    if not cp_data:
        print("No Cp data to plot.")
        return

    label = get_airfoil_label(airfoil_name)
    re_str = f"Re = {reynolds:.2e}" if reynolds is not None else "Inviscid"
    colors = plt.cm.tab10.colors

    fig, (ax_cp, ax_af) = plt.subplots(2, 1, figsize=(10, 8),
                                        gridspec_kw={'height_ratios': [3, 1]})

    for i, (aoa, (cp_x, cp_values)) in enumerate(sorted(cp_data.items())):
        ax_cp.plot(cp_x, cp_values, linewidth=1.5,
                   label=f'α = {aoa}°', color=colors[i % len(colors)])

    if experimental_data is not None:
        for label_exp, (exp_x, exp_cp) in experimental_data.items():
            ax_cp.scatter(exp_x, exp_cp, marker='x', s=50, label=f"Exp: {label_exp}")

    ax_cp.invert_yaxis()
    ax_cp.set_xlabel('x/c')
    ax_cp.set_ylabel('Cp')
    ax_cp.set_title(f'Cp Distribution: {label} — {re_str} — Multi-AoA')
    ax_cp.legend()
    ax_cp.grid(True)

    if airfoil_coords and len(airfoil_coords[0]) > 0:
        ax_af.plot(airfoil_coords[0], airfoil_coords[1], 'k-', linewidth=1.5)
        ax_af.set_aspect('equal')
        ax_af.set_xlabel('x/c')
        ax_af.set_ylabel('y/c')
        ax_af.grid(True)

    plt.tight_layout()
    return fig