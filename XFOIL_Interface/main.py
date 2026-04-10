import os
import shutil
import tempfile
import tkinter.filedialog as filedialog
from matplotlib import pyplot as plt
from xfoil_interface import run_xfoil_study, restart_xfoil, init_xfoil
from utils import (get_airfoil_input, get_flow_type, get_reynolds_number, parse_pacc_all,
                   get_mach_number, get_moment_center, get_aoa_range,
                   get_max_iterations, write_filtered_pacc,
                   append_pacc, display_results, load_experimental_data,
                   load_cp_experimental_data, root)
from airfoil_geometry import read_airfoil_coords
from plotting import (plot_liftvsAoA, plot_dragpolar, plot_Cp_distribution,
                      plot_liftvsAoA_multi, plot_dragpolar_multi, plot_Cp_multi,
                      get_airfoil_label)

if __name__ == "__main__":
    '''Main function to run the XFOIL study. This includes getting user inputs, running the study, and displaying/saving results.'''

    
    init_xfoil()

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
            results, coord_path, desired_aoas, exit_reason = run_xfoil_study(airfoil, flow_type, reynolds, mach,
                                ncrit, aoa_range, max_iter,
                                moment_center, re_pacc_path, re_cpwr_paths, tmpdir) # run the XFOIL study for this Reynolds number, get results and file paths

            filtered_pacc_path = write_filtered_pacc(re_pacc_path, desired_aoas, tmpdir, i) # write a filtered version of the PACC file that only includes our desired AoA points, get the path to that file

            display_results(results, flow_type) # pass flow_type so the table only shows columns relevant to this run

            # store everything in our dictionaries keyed by Reynolds number so we can access it later for plotting and saving
            all_results[reynolds] = results
            all_desired_aoas[reynolds] = desired_aoas
            all_cpwr_paths[reynolds] = re_cpwr_paths
            all_filtered_pacc_paths[reynolds] = filtered_pacc_path

            if exit_reason == "timeout":
                re_str_disp = f"Re = {reynolds:.2e}" if reynolds is not None else "Inviscid"
                print(f"\nXFOIL timed out or went numerically unstable on {re_str_disp} — partial results shown above.")
                if i < len(re_list) - 1:
                    print("Restarting XFOIL and continuing to next Re.")

            if exit_reason == "q":
                break
            elif exit_reason == "n":
                if i < len(re_list) - 1:
                    restart_xfoil()
                continue
            else:  # "done" or "timeout" — restart XFOIL if more Re runs remain
                if i < len(re_list) - 1:
                    restart_xfoil()

        # read the airfoil coordinates from the saved file so plots match what XFOIL
        # actually analyzed (XFOIL may have reordered or resampled the panels via PANE).
        # if XFOIL timed out before saving, coord_path is None or the file doesn't exist —
        # in that case we fall back to empty coords so Cp plots just skip the airfoil outline.
        if airfoil.lower().startswith("naca") and (coord_path is None or not os.path.exists(coord_path)):
            x_coords, y_coords = [], []
        else:
            x_coords, y_coords = read_airfoil_coords(airfoil, coord_path)
        airfoil_label = get_airfoil_label(airfoil) # get a nice label for the airfoil to use in plot titles and saved file names. This will extract the name from the file path and remove extensions, so "naca0012.dat" becomes "NACA 0012".

        # generate lift curve, drag polar, and Cp distribution plots for each Reynolds number, and store the figure objects in dictionaries keyed by Reynolds number so we can access them later for saving. If inviscid flow was selected, we will only have one set of results without a Reynolds number, and we will just use "inviscid" as the key in our dictionaries.
        cp_figs = {}

        for reynolds, results in all_results.items(): # loop through our results for each Reynolds number, extract the data we need for plotting, and generate the plots. We will also pass the results data to the plotting functions so they can annotate the plots with CL, CD, CM, etc. at each AoA point.
            aoas = sorted(results.keys())
            cls = [results[aoa]['CL'] for aoa in aoas]
            cds = [results[aoa]['CD'] for aoa in aoas]

            cp_figs[reynolds] = {} # initialize before the loop so the key always exists, even if all AoAs failed to converge

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

                                    # detect full AoA range now in the file
                                    all_file_results = parse_pacc_all(saved_polar_path, flow_type)
                                    available_aoas = sorted(all_file_results.keys())
                                    print(f"File now contains AoA range: {available_aoas[0]}° to {available_aoas[-1]}°")

                                    # update all_results with the full merged data so any plots generated
                                    # after this point use the complete AoA range in the file, not just
                                    # the slice from the current run
                                    all_results[reynolds] = all_file_results

                                    while True:
                                        plot_choice = input("Plot from full polar file? (y/n): ").strip().lower()
                                        if plot_choice == "y":
                                            aoa_input = input("Enter AoA range to plot (start end, e.g. '-10 20') or 'all': ").strip().lower()
                                            if aoa_input == "all":
                                                plot_aoas = available_aoas
                                            else:
                                                try:
                                                    aoa_start, aoa_end = [float(x) for x in aoa_input.split()]
                                                    plot_aoas = [a for a in available_aoas if aoa_start <= a <= aoa_end]
                                                    if not plot_aoas:
                                                        print("No AoAs found in that range.")
                                                        break
                                                except ValueError:
                                                    print("Invalid input.")
                                                    break

                                            file_results = {aoa: all_file_results[aoa] for aoa in plot_aoas}
                                            file_aoas = sorted(file_results.keys())
                                            file_cls = [file_results[aoa]['CL'] for aoa in file_aoas]
                                            file_cds = [file_results[aoa]['CD'] for aoa in file_aoas]

                                            file_lift = plot_liftvsAoA(file_aoas, file_cls, airfoil, plot_aoas, aoa_range[2], file_results)
                                            file_drag = plot_dragpolar(file_cds, file_cls, airfoil) if flow_type == "visc" else None

                                            if save_dir:
                                                file_lift.savefig(os.path.join(save_dir, f"{airfoil_label}_full_polar_lift_curve.png"), dpi=300, bbox_inches='tight')
                                                if file_drag:
                                                    file_drag.savefig(os.path.join(save_dir, f"{airfoil_label}_full_polar_drag_polar.png"), dpi=300, bbox_inches='tight')
                                            break
                                        elif plot_choice == "n":
                                            break
                                        else:
                                            print("Please enter 'y' or 'n'.")
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
                                results = all_results[reynolds]
                                aoas = sorted(results.keys())
                                cls = [results[aoa]['CL'] for aoa in aoas]
                                cds = [results[aoa]['CD'] for aoa in aoas]

                                # ask axis limits only when actually saving
                                while True:
                                    lim_choice = input(f"Set custom axis limits for Re={re_str} plots? (y/n): ").strip().lower()
                                    if lim_choice == "y":
                                        try:
                                            lift_xlim = [float(x) for x in input("Lift curve x limits (min max): ").strip().split()]
                                            lift_ylim = [float(x) for x in input("Lift curve y limits (min max): ").strip().split()]
                                            drag_xlim = [float(x) for x in input("Drag polar x limits (min max): ").strip().split()]
                                            drag_ylim = [float(x) for x in input("Drag polar y limits (min max): ").strip().split()]
                                            break
                                        except ValueError:
                                            print("Invalid input. Enter two numbers separated by space.")
                                    elif lim_choice == "n":
                                        lift_xlim = lift_ylim = drag_xlim = drag_ylim = None
                                        break
                                    else:
                                        print("Please enter 'y' or 'n'.")

                                lift_fig = plot_liftvsAoA(aoas, cls, airfoil, all_desired_aoas[reynolds], aoa_range[2], results, reynolds, xlim=lift_xlim, ylim=lift_ylim)
                                drag_fig = plot_dragpolar(cds, cls, airfoil, reynolds, xlim=drag_xlim, ylim=drag_ylim) if flow_type == "visc" else None

                                if lift_fig:
                                    lift_fig.savefig(os.path.join(save_dir, f"{airfoil_label}_Re_{re_str}_lift_curve.png"), dpi=300, bbox_inches='tight')
                                if drag_fig:
                                    drag_fig.savefig(os.path.join(save_dir, f"{airfoil_label}_Re_{re_str}_drag_polar.png"), dpi=300, bbox_inches='tight')
                                plt.close('all')
                        break
                    elif choice == "n":
                        break
                    else:
                        print("Please select 'y' or 'n'.")

                # multi-Re comparison plots
                while True:
                    choice = input("Save multi-Re comparison plots? (y/n): ").strip().lower()
                    if choice == "y":
                        # always start from the current run — extra polar files get added on top,
                        # same idea as the experimental data step. copy so we don't mutate all_results.
                        plot_results = dict(all_results)

                        # optionally add more polar files — each added as an extra line on the plot
                        while True:
                            more_polars = input("Add additional polar file(s) to this plot? (y/n): ").strip().lower()
                            if more_polars == "y":
                                while True:
                                    root.lift()
                                    root.attributes('-topmost', True)
                                    polar_file = filedialog.askopenfilename(
                                        title="Select polar file",
                                        filetypes=[("Data files", "*.dat *.txt *.csv"), ("All files", "*.*")]
                                    )
                                    root.attributes('-topmost', False)
                                    if not polar_file:
                                        break
                                    re_label = input("Enter Re number or label for this file (e.g. 3e5): ").strip()
                                    try:
                                        re_val = float(re_label)
                                    except ValueError:
                                        re_val = re_label
                                    file_data = parse_pacc_all(polar_file, flow_type)
                                    if not file_data:
                                        print(f"No valid data found in {os.path.basename(polar_file)}. Make sure it's an XFOIL polar file.")
                                        continue
                                    plot_results[re_val] = file_data
                                    more = input("Add another file? (y/n): ").strip().lower()
                                    if more == "n":
                                        break
                                break
                            elif more_polars == "n":
                                break
                            else:
                                print("Please enter 'y' or 'n'.")

                        # experimental data
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

                        # ask axis limits for multi-Re plots
                        while True:
                            lim_choice = input("Set custom axis limits for multi-Re plots? (y/n): ").strip().lower()
                            if lim_choice == "y":
                                try:
                                    multi_lift_xlim = [float(x) for x in input("Lift curve x limits (min max): ").strip().split()]
                                    multi_lift_ylim = [float(x) for x in input("Lift curve y limits (min max): ").strip().split()]
                                    multi_drag_xlim = [float(x) for x in input("Drag polar x limits (min max): ").strip().split()]
                                    multi_drag_ylim = [float(x) for x in input("Drag polar y limits (min max): ").strip().split()]
                                    break
                                except ValueError:
                                    print("Invalid input. Enter two numbers separated by space.")
                            elif lim_choice == "n":
                                multi_lift_xlim = multi_lift_ylim = multi_drag_xlim = multi_drag_ylim = None
                                break
                            else:
                                print("Please enter 'y' or 'n'.")

                        multi_lift = plot_liftvsAoA_multi(plot_results, airfoil, exp_data_lift, xlim=multi_lift_xlim, ylim=multi_lift_ylim)
                        multi_drag = plot_dragpolar_multi(plot_results, airfoil, exp_data_drag, xlim=multi_drag_xlim, ylim=multi_drag_ylim)

                        if save_dir:
                            multi_lift.savefig(os.path.join(save_dir, f"{airfoil_label}_multi_Re_lift_curve.png"), dpi=300, bbox_inches='tight')
                            multi_drag.savefig(os.path.join(save_dir, f"{airfoil_label}_multi_Re_drag_polar.png"), dpi=300, bbox_inches='tight')
                        plt.close('all')
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
                            # ask for experimental Cp data once before selecting AoAs — same
                            # dataset gets overlaid on every plot saved in this batch
                            while True:
                                exp_choice = input("Overlay experimental Cp data on these plots? (y/n): ").strip().lower()
                                if exp_choice == "y":
                                    cp_exp_data = load_cp_experimental_data()
                                    break
                                elif exp_choice == "n":
                                    cp_exp_data = None
                                    break
                                else:
                                    print("Please enter 'y' or 'n'.")

                            saved = False
                            while True:
                                chooseplot = input("Save (1) all  (2) enter specific AoAs  (3) select from list  (4) Back: ").strip()

                                # build a flat list of (reynolds, aoa) pairs to save based on user choice,
                                # then handle the actual save in one shared block below
                                pairs_to_save = []
                                if chooseplot == "1":
                                    for reynolds in re_list:
                                        for aoa in all_cpwr_paths[reynolds]:
                                            pairs_to_save.append((reynolds, aoa))
                                elif chooseplot in ("2", "3"):
                                    if chooseplot == "3":
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
                                            if aoa in all_cpwr_paths[reynolds]:
                                                pairs_to_save.append((reynolds, aoa))
                                            else:
                                                print(f"No Cp data for Re={re_str} AoA={aoa}.")
                                elif chooseplot == "4":
                                    break
                                else:
                                    print("Invalid selection. Please enter 1, 2, 3 or 4.")
                                    continue

                                # save each plot — if experimental data was loaded, re-read the
                                # cpwr file and regenerate with the overlay. otherwise use the
                                # pre-generated figure directly.
                                for reynolds, aoa in pairs_to_save:
                                    re_str = f"{reynolds:.2e}" if reynolds is not None else "inviscid"
                                    if cp_exp_data:
                                        path = all_cpwr_paths[reynolds].get(aoa)
                                        data = all_results[reynolds].get(aoa)
                                        if not path or not data:
                                            continue
                                        cp_x_i, cp_vals_i = [], []
                                        try:
                                            with open(path, 'r') as f:
                                                for line in f:
                                                    parts = line.strip().split()
                                                    if len(parts) >= 3:
                                                        try:
                                                            cp_x_i.append(float(parts[0]))
                                                            cp_vals_i.append(float(parts[2]))
                                                        except ValueError:
                                                            continue
                                        except FileNotFoundError:
                                            print(f"CPWR file not found for AoA {aoa}. Skipping.")
                                            continue
                                        fig = plot_Cp_distribution(
                                            cp_x_i, cp_vals_i, (x_coords, y_coords), airfoil, aoa,
                                            data.get('CL'), data.get('CD'), data.get('CM'), data.get('CDp'),
                                            reynolds, experimental_data=cp_exp_data)
                                        if fig:
                                            fig.savefig(os.path.join(save_dir, f"{airfoil_label}_Re_{re_str}_Cp_{aoa}.png"), dpi=300, bbox_inches='tight')
                                            plt.close(fig)
                                    else:
                                        if aoa in cp_figs[reynolds]:
                                            cp_figs[reynolds][aoa].savefig(os.path.join(save_dir, f"{airfoil_label}_Re_{re_str}_Cp_{aoa}.png"), dpi=300, bbox_inches='tight')

                                saved = True
                                break

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
                            aoa_input = input("Enter AoAs to include (comma separated), 'all', or 'none' to skip: ").strip().lower()
                            if aoa_input == "none":
                                continue
                            elif aoa_input == "all":
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

                            # ask for experimental Cp data per Re — different Re studies
                            # may have different experimental datasets
                            while True:
                                exp_choice = input("Overlay experimental Cp data on this plot? (y/n): ").strip().lower()
                                if exp_choice == "y":
                                    cp_exp_data = load_cp_experimental_data()
                                    break
                                elif exp_choice == "n":
                                    cp_exp_data = None
                                    break
                                else:
                                    print("Please enter 'y' or 'n'.")

                            multi_cp = plot_Cp_multi(cp_data, (x_coords, y_coords), airfoil, reynolds, experimental_data=cp_exp_data)

                            if multi_cp is not None and save_dir:
                                multi_cp.savefig(os.path.join(save_dir, f"{airfoil_label}_Re_{re_str}_multi_AoA_Cp.png"), dpi=300, bbox_inches='tight')
                            elif multi_cp is None:
                                print(f"No Cp data available for Re={re_str}. Skipping.")
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
