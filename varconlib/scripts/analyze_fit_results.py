#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 12 14:33:52 2019

@author: dberke

A script to create transition pairs from lists of transition fits and return
information about them (via plots or otherwise).
"""

import argparse
import csv
import datetime as dt
from glob import glob
import lzma
import os
from pathlib import Path
import pickle
import re

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from tqdm import tqdm
import unyt as u

import varconlib as vcl
from varconlib.miscellaneous import wavelength2velocity as wave2vel
from varconlib.miscellaneous import date2index


# Where the analysis results live:
output_dir = Path(vcl.config['PATHS']['output_dir'])

# Set up CL arguments.
desc = """A script to analyze fitted absorption features.
          Requires a directory where results for an object are stored to be
          given, and the suffix to use."""
parser = argparse.ArgumentParser(description=desc)

parser.add_argument('object_dir', action='store', type=str,
                    help='Object directory to search in')

parser.add_argument('suffix', action='store', type=str,
                    help='Suffix to add to directory names to search for.')

parser.add_argument('--use-tex', action='store_true', default=False,
                    help='Use TeX rendering for fonts in plots (slow!).')

parser.add_argument('--create-plots', action='store_true', default=False,
                    help='Create plots of the offsets for each pair.')

parser.add_argument('--create-fit-plots', action='store_true', default=False,
                    help='Create plots of the fits for each transition.')

parser.add_argument('--link-fit-plots', action='store_true', default=False,
                    help='Hard-link fit plots by transition into new folders.')

parser.add_argument('--write-csv', action='store_true', default=False,
                    help='Create a CSV file of offsets for each pair.')

parser.add_argument('-v', '--verbose', action='store_true', default=False,
                    help='Print more information about the process.')

args = parser.parse_args()

if args.use_tex or args.create_plots:
    plt.rc('text', usetex=True)

if args.create_plots:

    # Define some important date for plots.
    # Define some dates when various changes were made to HARPS.
    dates_of_change = {"Secondary mirror unit changed":
                       {'x': dt.date(year=2004, month=8, day=8),
                        'color': 'MediumSeaGreen', 'linestyle': '--'},
                       "Flat field lamp changed":
                       {'x': dt.date(year=2008, month=8, day=22),
                        'color': 'OliveDrab', 'linestyle': '-'},
                       "Fibers changed":
                       {'x': dt.date(year=2015, month=6, day=1),
                        'color': 'SeaGreen', 'linestyle': '-.'}}

    date_plot_range = {'left': dt.date(year=2003, month=10, day=1),
                       'right': dt.date(year=2017, month=6, day=1)}
    folded_date_range = {'left': dt.date(year=2000, month=1, day=1),
                         'right': dt.date(year=2000, month=12, day=31)}

    style_params = {'marker': 'o', 'color': 'Chocolate',
                    'markeredgecolor': 'Black', 'ecolor': 'BurlyWood',
                    'linestyle': '', 'alpha': 0.7, 'markersize': 8}
    weighted_mean_params = {'color': 'RoyalBlue', 'linestyle': '--'}
    weighted_err_params = {'color': 'SteelBlue', 'linestyle': ':'}

# Define a list of good "blend numbers" for chooosing which blends to look at.
blends_of_interest = ((0, 0), (0, 1), (0, 2), (1, 1), (1, 2), (2, 2))

# Find the data in the given directory.
data_dir = Path(args.object_dir)
if not data_dir.exists():
    print(data_dir)
    raise RuntimeError('The given directory does not exist.')

# Read the list of chosen transitions.
with open(vcl.final_selection_file, 'r+b') as f:
    transitions_list = pickle.load(f)

tqdm.write(f'Found {len(transitions_list)} individual transitions.')

# Read the list of chosen pairs.
with open(vcl.final_pair_selection_file, 'r+b') as f:
    pairs_list = pickle.load(f)

tqdm.write(f'Found {len(pairs_list)} transition pairs (total) in list.')


# Search for pickle files in the given directory.
search_str = str(data_dir) + '/*/pickles_{}/*fits.lzma'.format(args.suffix)
tqdm.write(search_str)
pickle_files = [Path(path) for path in glob(search_str)]


# dictionary with entries per observation
# entries consist of dictionary with entries of pairs made from fits

# Set up the master dictionary to contain sub-entries per observation.
master_star_dict = {}

obs_name_re = re.compile('HARPS.*_e2ds_A')

# Create some lists to hold all the results for saving out as a CSV file:
master_star_list = []
master_fits_list = []
for pickle_file in tqdm(pickle_files[:]):

    # Match the part of the pickle filename that is the observation name.
    obs_name = obs_name_re.match(pickle_file.stem).group()

    tqdm.write('Analyzing results from {}'.format(obs_name))
    with lzma.open(pickle_file, 'rb') as f:
        fits_list = pickle.loads(f.read())

    # Set up a dictionary to map fits in this observation to transitions:
    fits_dict = {fit.transition.label: fit for fit in fits_list}
    if args.write_csv:
        master_fits_list.append(fits_dict)

    if args.create_fit_plots:
        closeup_dir = data_dir /\
            '{}/plots_{}/close_up'.format(obs_name, args.suffix)
        context_dir = data_dir /\
            '{}/plots_{}/context'.format(obs_name, args.suffix)
        tqdm.write('Creating plots of fits.')

        for transition in tqdm(transitions_list):
            plot_closeup = closeup_dir / '{}_{}_close.png'.format(
                    obs_name, transition.label)
            plot_context = context_dir / '{}_{}_context.png'.format(
                    obs_name, transition.label)
            if args.verbose:
                tqdm.write('Creating plots at:')
                tqdm.write(str(plot_closeup))
                tqdm.write(str(plot_context))
            fits_dict[transition.label].plotFit(plot_closeup, plot_context)

    pairs_dict = {}
    separations_list = [obs_name, fits_list[0].dateObs.
                        isoformat(timespec='milliseconds')]

    column_names = ['Observation', 'Time']
    for pair in pairs_list:
        column_names.extend([pair.label, pair.label + '_err'])
        try:
            fits_pair = [fits_dict[pair._higherEnergyTransition.label],
                         fits_dict[pair._lowerEnergyTransition.label]]
        except KeyError:
            # Measurement of one or the other transition doesn't exist, so
            # skip it (but fill in the list to prevent getting out of sync).
            separations_list.extend(['N/A', ' N/A'])
            continue

        if np.isnan(fits_pair[0].meanErrVel) or \
           np.isnan(fits_pair[1].meanErrVel):
            # Similar to above, fill in list with placeholder value.
            tqdm.write('{} in {} has a NaN velocity offset!'.format(
                    fits_pair.label, obs_name))
            tqdm.write(str(fits_pair[0].meanErrVel))
            tqdm.write(str(fits_pair[1].meanErrVel))
            separations_list.extend(['NaN', ' NaN'])
            continue

        pairs_dict[pair.label] = fits_pair
        error = np.sqrt(fits_pair[0].meanErrVel ** 2 +
                        fits_pair[1].meanErrVel ** 2)
        velocity_separation = wave2vel(fits_pair[0].mean, fits_pair[1].mean)
        separations_list.extend([velocity_separation.value, error.value])

    # This is for the script to use.
    master_star_dict[obs_name] = pairs_dict
    if args.write_csv:
        # This is to be written out.
        master_star_list.append(separations_list)

# Write out a CSV file containing the pair separation values for all
# observations of this star.
if args.write_csv:
    csv_filename = data_dir / 'pair_separations_{}.csv'.format(data_dir.stem)
    if args.verbose:
        tqdm.write(f'Creating CSV file of separations for {data_dir.stem} '
                   f'at {csv_filename}')

    assert len(master_star_list[0]) == len(column_names)

    with open(csv_filename, 'w') as csvfile:
        csv_writer = csv.writer(csvfile, delimiter=',')
        csv_writer.writerow(column_names)
        for row in tqdm(master_star_list):
            csv_writer.writerow(row)

    # Write out a series of CSV files containing information on the fits of
    # individual transitions for each star.
    column_names = ['ObsDate', 'Amplitude', 'Amplitude_err (A)', 'Mean (A)',
                    'Mean_err (A)', 'Mean_err_vel (m/s)', 'Sigma (A)',
                    'Sigma_err (A)', 'Offset (m/s)', 'Offset_err (m/s)',
                    'FWHM (m/s)', 'FWHM_err (m/s)', 'Chi-squared-nu',
                    'Order', 'Mean_airmass']

    csv_fits_dir = data_dir / 'fits_info_csv'
    if not csv_fits_dir.exists():
        os.mkdir(csv_fits_dir)
    if args.verbose:
        tqdm.write('Writing information on fits to files in {}'.format(
                   csv_fits_dir))
    for transition in tqdm(transitions_list):
        csv_filename = csv_fits_dir / '{}_{}.csv'.format(transition.label,
                                                         data_dir.stem)

        with open(csv_filename, 'w') as csvfile:
            csv_writer = csv.writer(csvfile, delimiter=',')
            csv_writer.writerow(column_names)
            for fits_dict in master_fits_list:
                csv_writer.writerow(fits_dict[transition.label].
                                    getFitInformation())


# Create the plots for each pair of transitions
if args.create_plots:
    for pair in tqdm(pairs_list):
        if args.verbose:
            tqdm.write(f'Creating plot for pair {pair.label}')
        fitted_pairs = []
        date_obs = []
        for key, pair_dict in master_star_dict.items():
            try:
                # Grab the associated pair from each observation.
                fitted_pairs.append(pair_dict[pair.label])
                # Grab the observation date.
                date_obs.append(pair_dict[pair.label][0].dateObs)
            except KeyError:
                # If a particular pair isn't available, just continue.
                continue

        offsets, errors = [], []
        for fit_pair in fitted_pairs:
            offsets.append(wave2vel(fit_pair[0].mean, fit_pair[1].mean))
            error = np.sqrt(fit_pair[0].meanErrVel ** 2 +
                            fit_pair[1].meanErrVel ** 2)
            if np.isnan(error):
                print(fit_pair[0].meanErrVel)
                print(fit_pair[1].meanErrVel)
                raise ValueError
            errors.append(error)

        offsets = np.array(offsets) * u.m / u.s
        errors = np.array(errors) * u.m / u.s
        folded_dates = [obs_date.replace(year=2000) for obs_date in date_obs]

        weights = 1 / errors ** 2
        weighted_mean = np.average(offsets, weights=weights)

        tqdm.write('Weighted mean for {} is {:.2f}'.format(pair.label,
                   weighted_mean))

        normalized_offsets = offsets - weighted_mean
        chi_squared = sum((normalized_offsets / errors) ** 2)

        weighted_mean_err = 1 / np.sqrt(sum(weights))

        date_indices = []
        for value in dates_of_change.values():
            date_indices.append(date2index(value['x'], date_obs))

        chi_squared = sum((normalized_offsets / errors) ** 2)
        chi_squared_nu = chi_squared / (len(normalized_offsets) - 1)

        plot_dir = data_dir / 'offset_plots'
        if not plot_dir.exists():
            os.mkdir(plot_dir)
        plot_name = plot_dir / '{}.png'.format(pair.label)

        fig, axes = plt.subplots(ncols=2, nrows=2,
                                 tight_layout=True,
                                 figsize=(10, 8),
                                 sharey='all')  # Share y-axis among all.
        fig.autofmt_xdate()
        (ax1, ax2), (ax3, ax4) = axes
        for ax in (ax1, ax2, ax3, ax4):
            ax.set_ylabel(r'$\Delta v_{\textrm{sep}}\textrm{ (m/s)}$')
            ax.axhline(y=0, **weighted_mean_params)
            ax.axhline(y=weighted_mean_err,
                       **weighted_err_params)
            ax.axhline(y=-weighted_mean_err,
                       **weighted_err_params)
        for key, value in dates_of_change.items():
            ax3.axvline(label=key, **value)

        # Set up axis 1.
        ax1.errorbar(x=range(len(offsets)),
                     y=normalized_offsets,
                     yerr=errors,
                     label=r'$\chi^2_\nu=${:.3f}'.format(chi_squared_nu.value),
                     **style_params)
        for index, key in zip(date_indices, dates_of_change.keys()):
            if index is not None:
                ax1.axvline(x=index+0.5,
                            linestyle=dates_of_change[key]['linestyle'],
                            color=dates_of_change[key]['color'])
        ax1.legend(loc='upper right')

        # Set up axis 2.
        ax2.set_xlabel('Count')
        try:
            ax2.hist(normalized_offsets.value,
                     orientation='horizontal', color='White',
                     edgecolor='Black')
        except ValueError:
            print(fit_pair[0].meanErrVel)
            print(fit_pair[1].meanErrVel)
            print(offsets)
            print(errors)
            print(weights)
            raise

        # Set up axis 3.
        ax3.set_xlim(**date_plot_range)
        ax3.errorbar(x=date_obs, y=normalized_offsets,
                     yerr=errors, **style_params)

        # Set up axis 4.
        ax4.set_xlim(**folded_date_range)
        ax4.xaxis.set_major_locator(mdates.MonthLocator())
        ax4.xaxis.set_major_formatter(mdates.DateFormatter('%m'))
        ax4.errorbar(x=folded_dates, y=normalized_offsets,
                     yerr=errors, **style_params)

        fig.savefig(str(plot_name))
        plt.close(fig)

# Create hard links to all the fit plots by transition (across star) in their
# own directory, to make it easier to compare transitions across observations.
if args.link_fit_plots:
    tqdm.write('Linking fit plots to cross-observation directories.')
    transition_plots_dir = data_dir / 'plots_by_transition'
    if not transition_plots_dir.exists():
        os.mkdir(transition_plots_dir)
    for transition in tqdm(transitions_list):

        wavelength_str = '{:.3f}'.format(transition.wavelength.to(u.angstrom)
                                         .value)
        transition_dir = transition_plots_dir / wavelength_str
        close_up_dir = transition_dir / 'close_up'
        context_dir = transition_dir / 'context'

        for directory in (transition_dir, close_up_dir, context_dir):
            if not directory.exists():
                os.mkdir(directory)

        for plot_type, directory in zip(('close_up', 'context'),
                                        (close_up_dir, context_dir)):

            search_str = str(data_dir) +\
                          '/HARPS*/plots_{}/{}/*{}*.png'.format(args.suffix,
                                                                plot_type,
                                                                wavelength_str)

            files_to_link = [Path(path) for path in glob(search_str)]
            for file_to_link in files_to_link:
                dest_name = directory / file_to_link.name
                if not dest_name.exists():
                    os.link(file_to_link, dest_name)
