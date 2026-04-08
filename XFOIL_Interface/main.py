import os
import shutil
import tempfile
import tkinter.filedialog as filedialog
from matplotlib import pyplot as plt
from xfoil_interface import run_xfoil_study, restart_xfoil
from utils import (get_airfoil_input, get_flow_type, get_reynolds_number,
                   get_mach_number, get_moment_center, get_aoa_range,
                   get_max_iterations, write_filtered_pacc,
                   append_pacc, display_results, load_experimental_data, root)
from airfoil_geometry import read_airfoil_coords
from plotting import (plot_liftvsAoA, plot_dragpolar, plot_Cp_distribution,
                      plot_liftvsAoA_multi, plot_dragpolar_multi, plot_Cp_multi,
                      get_airfoil_label)

# ======= Main Function ========
if __name__ == "__main__":
    '''Main function to run the XFOIL study. This includes getting user inputs, running the study, and displaying/saving results.'''

    airfoil = get_airfoil_input()
    flow_type, ncrit = get_flow_type()
    mach = get_mach_number()
    moment_center = get_moment_center()
    aoa_range = get_aoa_range()
    max_iter = get_max_iterations()

    re_list = []
    '''If viscous flow is selected, prompt the user to enter one or more Reynolds numbers to analyze. If inviscid flow is selected, we will just run one study without a Reynolds number.'''
    if flow_type == "visc":
        while True:
            reynolds = get_reynolds_number()
            re_list.append(reynolds)
            while True:
                more = input("Add another Reynolds number? (y/n): ").strip().lower()
                if more == "y":
                    break
                elif more == "n":
                    break
                else:
                    print("Please enter 'y' or 'n'.")
            if more == "n":
                break
    else:
        re_list = [None]



    with tempfile.TemporaryDirectory() as tmpdir:
        '''Dictionaries to store results, desired AoA points, CPWR file paths, and filtered PACC file paths for each Reynolds number. This allows us to keep all the data organized and easily accessible for plotting and saving later on.'''
        all_results = {}
        all_desired_aoas = {}
        all_cpwr_paths = {}
        all_filtered_pacc_paths = {}

        for i, reynolds in enumerate(re_list):
            re_pacc_path = os.path.join(tmpdir, f"p{i}.txt")
            re_cpwr_paths = {}
            results, coord_path, desired_aoas = run_xfoil_study(airfoil, flow_type, reynolds, mach, 
                                ncrit, aoa_range, max_iter, 
                                moment_center, re_pacc_path, re_cpwr_paths, tmpdir) # run the XFOIL study for this Reynolds number, get results and file paths

            filtered_pacc_path = write_filtered_pacc(re_pacc_path, desired_aoas, tmpdir, i) # write a filtered version of the PACC file that only includes our desired AoA points, get the path to that file
            
            display_results(results) # display the results in the terminal so the user can see them immediately without having to open files or look at plots


            # store everything in our dictionaries keyed by Reynolds number so we can access it later for plotting and saving
            all_results[reynolds] = results 
            all_desired_aoas[reynolds] = desired_aoas
            all_cpwr_paths[reynolds] = re_cpwr_paths
            all_filtered_pacc_paths[reynolds] = filtered_pacc_path

            # restart XFOIL for next Re if there is one
            if i < len(re_list) - 1:
                restart_xfoil()
        
        x_coords, y_coords = read_airfoil_coords(airfoil, coord_path) # read the airfoil coordinates from the saved file, so we can use them for plotting later. We have to read from the saved file because XFOIL may have modified the coordinates (e.g. reordering, resampling) and we want to make sure our plots match what XFOIL actually analyzed.
        airfoil_label = get_airfoil_label(airfoil) # get a nice label for the airfoil to use in plot titles and saved file names. This will extract the name from the file path and remove extensions, so "naca0012.dat" becomes "NACA 0012".
        
        # generate lift curve, drag polar, and Cp distribution plots for each Reynolds number, and store the figure objects in dictionaries keyed by Reynolds number so we can access them later for saving. If inviscid flow was selected, we will only have one set of results without a Reynolds number, and we will just use "inviscid" as the key in our dictionaries.
        lift_curves = {}
        drag_polars = {}
        cp_figs = {}

        for reynolds, results in all_results.items(): # loop through our results for each Reynolds number, extract the data we need for plotting, and generate the plots. We will also pass the results data to the plotting functions so they can annotate the plots with CL, CD, CM, etc. at each AoA point.
            aoas = sorted(results.keys())
            cls = [results[aoa]['CL'] for aoa in aoas]
            cds = [results[aoa]['CD'] for aoa in aoas]
            
            # generate the plots for this Reynolds number and store the figure objects in our dictionaries keyed by Reynolds number. We will use the same desired AoA points for the lift curve and drag polar.
            lift_curves[reynolds] = plot_liftvsAoA(aoas, cls, airfoil, all_desired_aoas[reynolds], aoa_range[2], results, reynolds)
            drag_polars[reynolds] = plot_dragpolar(cds, cls, airfoil, reynolds) if flow_type == "visc" else None

            for aoa, cpwr_path in all_cpwr_paths[reynolds].items(): # loop through the CPWR files for each AoA point, read the Cp distribution data, and generate the Cp distribution plot for this AoA. We will also annotate the plot with CL, CD, CM, etc. from our results dictionary for this AoA point. We will store the figure objects in a nested dictionary keyed by Reynolds number and then AoA, so we can access them later for saving.
                data = results.get(aoa)
                if data is None:
                    continue
                cp_x, cp_values = [], []
                try:
                    with open(cpwr_path, 'r') as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) >= 3:
                                try:
                                    cp_x.append(float(parts[0]))
                                    cp_values.append(float(parts[2]))
                                except ValueError:
                                    continue
                except FileNotFoundError:
                    print(f"CPWR file not found for AoA {aoa}. Skipping Cp plot for this angle.")
                    continue

                if reynolds not in cp_figs: # initialize nested dictionary for this Reynolds number if it doesn't exist yet
                    cp_figs[reynolds] = {}
                cp_figs[reynolds][aoa] = plot_Cp_distribution(cp_x, cp_values,(x_coords, y_coords),airfoil, aoa,data.get('CL'), data.get('CD'),data.get('CM'), data.get('CDp'), reynolds)

    
            
        # plt.show()

        while True:
            '''Save logic for all results. We will ask the user if they want to save, and if so, 
            we will prompt them to select a folder and choose which files to save. 
            We will also ask them which format they want to save in (e.g. .dat, .txt, .csv for data files, and .png or .jpg for plots). 
            The user can choose to save all files, or select specific Reynolds numbers and AoA points to save. 
            We will handle saving the filtered PACC files, the CPWR files, and the generated plots, and we will make sure to name 
            the saved files in a clear and organized way that includes the airfoil label, Reynolds number, AoA, and type of file.'''
            save_choice = input("Save any results? (y/n): ").strip().lower()
            if save_choice == "y":
                root.lift()
                root.attributes('-topmost', True)
                save_dir = filedialog.askdirectory(title="Select folder to save results")
                root.attributes('-topmost', False)
                
                fmt = input("Save files as (1) .dat  (2) .txt  (3) .csv  [default 1]: ").strip()
                if fmt == "2":
                    ext = ".txt"
                elif fmt == "3":
                    ext = ".csv"
                else:
                    ext = ".dat"

                # polar files — one per Re
                while True:
                    choice = input("Save polar file(s)? (y/n): ").strip().lower()
                    if choice == "y":
                        for reynolds in re_list:
                            re_str = f"{reynolds:.2e}" if reynolds is not None else "inviscid"
                            polar_name = input(f"Enter name for polar file Re={re_str} (without extension, default={airfoil_label}_Re_{re_str}_polar): ").strip()
                            if polar_name == "":
                                polar_name = f"{airfoil_label}_Re_{re_str}_polar"
                            if save_dir:
                                saved_polar_path = os.path.join(save_dir, f"{polar_name}{ext}")
                                if os.path.isfile(saved_polar_path):
                                    append_pacc(saved_polar_path, all_filtered_pacc_paths[reynolds], all_desired_aoas[reynolds])
                                    print(f"Appended to: {polar_name}{ext}")
                                else:
                                    shutil.copy(all_filtered_pacc_paths[reynolds], saved_polar_path)
                                    print(f"Saved: {polar_name}{ext}")
                        break
                    elif choice == "n":
                        break
                    else:
                        print("Please select 'y' or 'n'.")

                # cpwr files — one set per Re
                while True:
                    choice = input("Save Cp distribution files? (y/n): ").strip().lower()
                    if choice == "y":
                        if save_dir:
                            saved = False
                            while True:
                                chooseplot = input("Save (1) all  (2) enter specific AoAs  (3) select from list  (4) Back: ").strip()
                                if chooseplot == "1":
                                    for reynolds in re_list:
                                        re_str = f"{reynolds:.2e}" if reynolds is not None else "inviscid"
                                        for aoa, path in all_cpwr_paths[reynolds].items():
                                            shutil.copy(path, os.path.join(save_dir, f"{airfoil_label}_Re_{re_str}_cpwr_{aoa}{ext}"))
                                    saved = True
                                    break
                                elif chooseplot == "2":
                                    aoa_input = input("Enter AoAs to save (comma separated): ").strip()
                                    aoas_to_save = [round(float(a.strip()), 2) for a in aoa_input.split(",")]
                                    for reynolds in re_list:
                                        re_str = f"{reynolds:.2e}" if reynolds is not None else "inviscid"
                                        for aoa in aoas_to_save:
                                            if aoa in all_cpwr_paths[reynolds]:
                                                shutil.copy(all_cpwr_paths[reynolds][aoa], os.path.join(save_dir, f"{airfoil_label}_Re_{re_str}_cpwr_{aoa}{ext}"))
                                            else:
                                                print(f"No cpwr file for Re={re_str} AoA={aoa}.")
                                    saved = True
                                    break
                                elif chooseplot == "3":
                                    for reynolds in re_list:
                                        re_str = f"{reynolds:.2e}" if reynolds is not None else "inviscid"
                                        print(f"\nRe = {re_str}:")
                                        for aoa in all_cpwr_paths[reynolds].keys():
                                            print(f"  {aoa}°")
                                    aoa_input = input("Enter AoAs to save (comma separated): ").strip()
                                    aoas_to_save = [round(float(a.strip()), 2) for a in aoa_input.split(",")]
                                    for reynolds in re_list:
                                        re_str = f"{reynolds:.2e}" if reynolds is not None else "inviscid"
                                        for aoa in aoas_to_save:
                                            if aoa in all_cpwr_paths[reynolds]:
                                                shutil.copy(all_cpwr_paths[reynolds][aoa], os.path.join(save_dir, f"{airfoil_label}_Re_{re_str}_cpwr_{aoa}{ext}"))
                                            else:
                                                print(f"No cpwr file for Re={re_str} AoA={aoa}.")
                                    saved = True
                                    break
                                elif chooseplot == "4":
                                    break
                                else:
                                    print("Invalid selection. Please enter 1, 2, 3 or 4.")
                            if saved:
                                break
                        else:
                            break
                    elif choice == "n":
                        break
                    else:
                        print("Please select 'y' or 'n'.")

                # individual lift and drag plots per Re
                while True:
                    choice = input("Save individual lift vs AoA and drag polar plots? (y/n): ").strip().lower()
                    if choice == "y":
                        if save_dir:
                            for reynolds in re_list:
                                re_str = f"{reynolds:.2e}" if reynolds is not None else "inviscid"
                                if lift_curves.get(reynolds):
                                    lift_curves[reynolds].savefig(os.path.join(save_dir, f"{airfoil_label}_Re_{re_str}_lift_curve.png"), dpi=300, bbox_inches='tight')
                                if drag_polars.get(reynolds):
                                    drag_polars[reynolds].savefig(os.path.join(save_dir, f"{airfoil_label}_Re_{re_str}_drag_polar.png"), dpi=300, bbox_inches='tight')
                        break
                    elif choice == "n":
                        break
                    else:
                        print("Please select 'y' or 'n'.")

                # multi-Re comparison plots
                if len(re_list) > 1:
                    while True:
                        choice = input("Save multi-Re comparison plots? (y/n): ").strip().lower()
                        if choice == "y":
                            # ask for experimental data
                            exp_data_lift = None
                            exp_data_drag = None
                            while True:
                                exp_choice = input("Add experimental data? (y/n): ").strip().lower()
                                if exp_choice == "y":
                                    exp_data_lift, exp_data_drag = load_experimental_data()
                                    break
                                elif exp_choice == "n":
                                    break
                                else:
                                    print("Please enter 'y' or 'n'.")
                            
                            multi_lift = plot_liftvsAoA_multi(all_results, airfoil, exp_data_lift)
                            multi_drag = plot_dragpolar_multi(all_results, airfoil, exp_data_drag)
                            
                            
                            if save_dir:
                                multi_lift.savefig(os.path.join(save_dir, f"{airfoil_label}_multi_Re_lift_curve.png"), dpi=300, bbox_inches='tight')
                                multi_drag.savefig(os.path.join(save_dir, f"{airfoil_label}_multi_Re_drag_polar.png"), dpi=300, bbox_inches='tight')
                            break
                        elif choice == "n":
                            break
                        else:
                            print("Please enter 'y' or 'n'.")

                # individual Cp plots per Re
                while True:
                    choice = input("Save Cp distribution plots? (y/n): ").strip().lower()
                    if choice == "y":
                        if save_dir:
                            saved = False
                            while True:
                                chooseplot = input("Save (1) all  (2) enter specific AoAs  (3) select from list  (4) Back: ").strip()
                                if chooseplot == "1":
                                    for reynolds in re_list:
                                        re_str = f"{reynolds:.2e}" if reynolds is not None else "inviscid"
                                        for aoa, fig in cp_figs[reynolds].items():
                                            fig.savefig(os.path.join(save_dir, f"{airfoil_label}_Re_{re_str}_Cp_{aoa}.png"), dpi=300, bbox_inches='tight')
                                    saved = True
                                    break
                                elif chooseplot == "2":
                                    aoa_input = input("Enter AoAs to save (comma separated): ").strip()
                                    aoas_to_save = [round(float(a.strip()), 2) for a in aoa_input.split(",")]
                                    for reynolds in re_list:
                                        re_str = f"{reynolds:.2e}" if reynolds is not None else "inviscid"
                                        for aoa in aoas_to_save:
                                            if aoa in cp_figs[reynolds]:
                                                cp_figs[reynolds][aoa].savefig(os.path.join(save_dir, f"{airfoil_label}_Re_{re_str}_Cp_{aoa}.png"), dpi=300, bbox_inches='tight')
                                            else:
                                                print(f"No Cp plot for Re={re_str} AoA={aoa}.")
                                    saved = True
                                    break
                                elif chooseplot == "3":
                                    for reynolds in re_list:
                                        re_str = f"{reynolds:.2e}" if reynolds is not None else "inviscid"
                                        print(f"\nRe = {re_str}:")
                                        for aoa in cp_figs[reynolds].keys():
                                            print(f"  {aoa}°")
                                    aoa_input = input("Enter AoAs to save (comma separated): ").strip()
                                    aoas_to_save = [round(float(a.strip()), 2) for a in aoa_input.split(",")]
                                    for reynolds in re_list:
                                        re_str = f"{reynolds:.2e}" if reynolds is not None else "inviscid"
                                        for aoa in aoas_to_save:
                                            if aoa in cp_figs[reynolds]:
                                                cp_figs[reynolds][aoa].savefig(os.path.join(save_dir, f"{airfoil_label}_Re_{re_str}_Cp_{aoa}.png"), dpi=300, bbox_inches='tight')
                                            else:
                                                print(f"No Cp plot for Re={re_str} AoA={aoa}.")
                                    saved = True
                                    break
                                elif chooseplot == "4":
                                    break
                                else:
                                    print("Invalid selection. Please enter 1, 2, 3 or 4.")
                            if saved:
                                break
                        else:
                            break
                    elif choice == "n":
                        break
                    else:
                        print("Please select 'y' or 'n'.")

                

            

                # multi-AoA Cp plots per Re
                while True:
                    choice = input("Save multi-AoA Cp plots? (y/n): ").strip().lower()
                    if choice == "y":
                        for reynolds in re_list:
                            re_str = f"{reynolds:.2e}" if reynolds is not None else "inviscid"
                            print(f"\nAvailable AoAs for Re = {re_str}:")
                            for aoa in sorted(all_cpwr_paths[reynolds].keys()):
                                print(f"  {aoa}°")
                            aoa_input = input("Enter AoAs to include (comma separated) or 'all': ").strip().lower()
                            
                            if aoa_input == "all":
                                selected_aoas = sorted(all_cpwr_paths[reynolds].keys())
                            else:
                                selected_aoas = [round(float(a.strip()), 2) for a in aoa_input.split(",")]
                            
                            cp_data = {}
                            for aoa in selected_aoas:
                                if aoa not in all_cpwr_paths[reynolds]:
                                    continue
                                cp_x, cp_values = [], []
                                try:
                                    with open(all_cpwr_paths[reynolds][aoa], 'r') as f:
                                        for line in f:
                                            parts = line.strip().split()
                                            if len(parts) >= 3:
                                                try:
                                                    cp_x.append(float(parts[0]))
                                                    cp_values.append(float(parts[2]))
                                                except ValueError:
                                                    continue
                                except FileNotFoundError:
                                    continue
                                cp_data[aoa] = (cp_x, cp_values)
                            
                            multi_cp = plot_Cp_multi(cp_data, (x_coords, y_coords), airfoil, reynolds)
                            
                            if save_dir:
                                multi_cp.savefig(os.path.join(save_dir, f"{airfoil_label}_Re_{re_str}_multi_AoA_Cp.png"), dpi=300, bbox_inches='tight')
                        break
                    elif choice == "n":
                        break
                    else:
                        print("Please enter 'y' or 'n'.")
                
                break

            elif save_choice == "n":
                break
            else:
                print("Please select 'y' or 'n'.")
                            