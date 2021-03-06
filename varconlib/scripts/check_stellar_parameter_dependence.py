#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon May 25 16:41:51 2020

@author: dberke

A script to check if sigma_sys changes as a function of stellar parameters or
not.

"""

import argparse
from inspect import signature
from itertools import tee
from pathlib import Path
import pickle
import sys

import h5py
import hickle
from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import numpy.ma as ma
from scipy.optimize import curve_fit
from tqdm import tqdm
import unyt as u

import varconlib as vcl
import varconlib.fitting.fitting as fit
from varconlib.scripts.multi_fit_stars import plot_data_points


def pairwise(iterable):
    """Return successive pairs from an iterable.

    E.g., s -> (s0,s1), (s1,s2), (s2, s3), ...

    """

    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def create_comparison_figure(ylims=None,
                             temp_lims=(5400 * u.K, 6300 * u.K),
                             mtl_lims=(-0.75, 0.4),
                             logg_lims=(4.1, 4.6)):
    """Create and returns a figure with pre-set subplots.

    This function creates the background figure and subplots for use with the
    --compare-stellar-parameter-* flags.

    Optional
    ----------
    ylims : 2-tuple of floats or ints
        A tuple of length 2 containing the upper and lower limits of the
        subplots in the figure.
    temp_lims : 2-tuple of floats or ints (optional dimensions of temperature)
        A tuple of length containing upper and lower limits for the x-axis of
        the temperature subplot.
    mtl_lims : 2-tuple of floats or ints
        A tuple of length containing upper and lower limits for the x-axis of
        the metallicity subplot.
    logg_lims : 2-tuple of floats or ints
        A tuple of length containing upper and lower limits for the x-axis of
        the log(g) subplot.

    Returns
    -------
    tuple
        A tuple containing the figure itself and the various axes of the
        subplots within it.

    """

    comp_fig = plt.figure(figsize=(12, 8), tight_layout=True)
    gs = GridSpec(ncols=3, nrows=2, figure=comp_fig,
                  width_ratios=(5, 5, 5))

    temp_ax_pre = comp_fig.add_subplot(gs[0, 0])
    temp_ax_pre.set_ylim(bottom=-1, top=80)
    temp_ax_post = comp_fig.add_subplot(gs[1, 0],
                                        sharex=temp_ax_pre,
                                        sharey=temp_ax_pre)
    mtl_ax_pre = comp_fig.add_subplot(gs[0, 1],
                                      sharey=temp_ax_pre)
    mtl_ax_post = comp_fig.add_subplot(gs[1, 1],
                                       sharex=mtl_ax_pre,
                                       sharey=mtl_ax_pre)
    logg_ax_pre = comp_fig.add_subplot(gs[0, 2],
                                       sharey=temp_ax_pre)
    logg_ax_post = comp_fig.add_subplot(gs[1, 2],
                                        sharex=logg_ax_pre,
                                        sharey=logg_ax_pre)

    all_axes = (temp_ax_pre, temp_ax_post, mtl_ax_pre, mtl_ax_post,
                logg_ax_pre, logg_ax_post)
    # Set the plot limits here. The y-limits for temp_ax1 are
    # used for all subplots.
    if ylims is not None:
        temp_ax_pre.set_ylim(bottom=ylims[0],
                             top=ylims[1])
    temp_ax_pre.set_xlim(left=temp_lims[0],
                         right=temp_lims[1])
    mtl_ax_pre.set_xlim(left=mtl_lims[0],
                        right=mtl_lims[1])
    logg_ax_pre.set_xlim(left=logg_lims[0],
                         right=logg_lims[1])

    # Axis styles for all subplots.
    for ax in all_axes:
        ax.yaxis.set_major_locator(ticker.AutoLocator())
        ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
        ax.axhline(y=0, color='Black', linestyle='--')
        ax.yaxis.grid(which='major', color='Gray',
                      linestyle='--', alpha=0.65)
        ax.yaxis.grid(which='minor', color='Gray',
                      linestyle=':', alpha=0.5)
        ax.xaxis.grid(which='major', color='Gray',
                      linestyle='--', alpha=0.65)

    for ax in (temp_ax_pre, temp_ax_post):
        ax.set_xlabel('Temperature (K)')
        ax.xaxis.set_major_locator(ticker.MultipleLocator(base=200))
        ax.xaxis.set_minor_locator(ticker.MultipleLocator(base=100))
    for ax in (mtl_ax_pre, mtl_ax_post):
        ax.set_xlabel('Metallicity [Fe/H]')
        ax.xaxis.set_major_locator(ticker.MultipleLocator(base=0.2))
        ax.xaxis.set_minor_locator(ticker.MultipleLocator(base=0.1))
    for ax in (logg_ax_pre, logg_ax_post):
        ax.set_xlabel(r'log($g$) (cm/s$^2$)')
        ax.xaxis.set_major_locator(ticker.MultipleLocator(base=0.1))
        ax.xaxis.set_minor_locator(ticker.MultipleLocator(base=0.05))

    # Just label the left-most two subplots' y-axes.
    for ax, era in zip((temp_ax_pre, temp_ax_post),
                       ('Pre', 'Post')):
        ax.set_ylabel(f'{era}-fiber change '
                      r'$\sigma_\mathrm{sys}$ (m/s)')

    axes_dict = {'temp_pre': temp_ax_pre, 'temp_post': temp_ax_post,
                 'mtl_pre': mtl_ax_pre, 'mtl_post': mtl_ax_post,
                 'logg_pre': logg_ax_pre, 'logg_post': logg_ax_post}

    return comp_fig, axes_dict


def main():
    """Run the main routine for the script."""

    # Define the limits to plot in the various stellar parameters.
    temp_lims = (5400, 6300) * u.K
    mtl_lims = (-0.75, 0.45)
    logg_lims = (4.1, 4.6)

    tqdm.write('Unpickling transitions list...')
    with open(vcl.final_selection_file, 'r+b') as f:
        transitions_list = pickle.load(f)
    vprint(f'Found {len(transitions_list)} transitions.')

    # Define the model to use.
    if args.linear:
        model_func = fit.linear_model
    elif args.quadratic:
        model_func = fit.quadratic_model
    elif args.cross_term:
        model_func = fit.cross_term_model
    elif args.quadratic_magnitude:
        model_func = fit.quadratic_mag_model

    # model_func = fit.quadratic_model
    model_name = '_'.join(model_func.__name__.split('_')[:-1])
    tqdm.write(f'Using {model_name} model.')

    db_file = vcl.databases_dir / f'stellar_db_{model_name}_params.hdf5'
    # Load data from HDF5 database file.
    tqdm.write('Reading data from stellar database file...')
    star_transition_offsets = u.unyt_array.from_hdf5(
            db_file, dataset_name='star_transition_offsets')
    star_transition_offsets_EotWM = u.unyt_array.from_hdf5(
            db_file, dataset_name='star_transition_offsets_EotWM')
    star_transition_offsets_EotM = u.unyt_array.from_hdf5(
            db_file, dataset_name='star_transition_offsets_EotM')
    star_temperatures = u.unyt_array.from_hdf5(
            db_file, dataset_name='star_temperatures')

    with h5py.File(db_file, mode='r') as f:

        star_metallicities = hickle.load(f, path='/star_metallicities')
        star_magnitudes = hickle.load(f, path='/star_magnitudes')
        star_gravities = hickle.load(f, path='/star_gravities')
        column_dict = hickle.load(f, path='/transition_column_index')
        star_names = hickle.load(f, path='/star_row_index')

    # Handle various fitting and plotting setup:
    eras = {'pre': 0, 'post': 1}
    param_dict = {'temp': 0, 'mtl': 1, 'logg': 2}
    plot_types = ('temp', 'mtl', 'logg')

    params_list = []
    # Figure out how many parameters the model function takes, so we know how
    # many to dynamically give it later.
    num_params = len(signature(model_func).parameters)
    for i in range(num_params - 1):
        params_list.append(0.)

    # Set up the figure with subplots.
    comp_fig, axes_dict = create_comparison_figure(ylims=None)

    if args.label:
        labels = (args.label, )

    else:
        # labels = ['4219.893V1_16', '4490.998Fe1_25', '4492.660Fe2_25',
        #           '4500.398Fe1_25', '4589.484Cr2_28', '4653.460Cr1_29',]
                  # '4738.098Fe1_32', '4767.190Mn1_33', '4811.877Zn1_34',
                  # '4940.192Fe1_37', '5138.510Ni1_42', '5178.000Ni1_43',
                  # '5200.158Fe1_43', '5571.164Fe1_50', '5577.637Fe1_50',
                  # '6067.161Fe1_59', '6123.910Ca1_60', '6144.183Si1_60',
                  # '6155.928Na1_61', '6162.452Na1_61', '6178.520Ni1_61',
                  # '6192.900Ni1_61']
        labels = []
        for transition in tqdm(transitions_list):
            for order_num in transition.ordersToFitIn:
                label = '_'.join([transition.label, str(order_num)])
                labels.append(label)

        tqdm.write(f'Analyzing {len(labels)} transitions.')

    if not args.nbins:
        bin_dict = {}
        # Set bins manually.
        # bin_dict[name] = np.linspace(5457, 6257, 5)
        bin_dict['temp'] = [5377, 5477, 5577, 5677,
                            5777, 5877, 5977, 6077,
                            6177, 6277]
        # bin_dict[name] = np.linspace(-0.75, 0.45, 5)
        bin_dict['mtl'] = [-0.75, -0.6, -0.45, -0.3,
                           -0.15, 0, 0.15, 0.3, 0.45]
        # bin_dict[name] = np.linspace(4.1, 4.6, 5)
        bin_dict['logg'] = [4.04, 4.14, 4.24,
                            4.34, 4.44, 4.54, 4.64]

        for time in eras.keys():
            for plot_type, lims in zip(plot_types,
                                       (temp_lims, mtl_lims, logg_lims)):
                ax = axes_dict[f'{plot_type}_{time}']
                for limit in bin_dict[plot_type]:
                    ax.axvline(x=limit, color='Green',
                               alpha=0.6, zorder=1)

    # Create an array to store all the individual sigma_sys values in in order
    # to get the means and STDs for each bin.
    row_len = len(labels)
    temp_col_len = len(bin_dict['temp']) - 1
    metal_col_len = len(bin_dict['mtl']) - 1
    logg_col_len = len(bin_dict['logg']) - 1

    # First axis is for pre- and post- fiber change values: 0 = pre, 1 = post
    temp_array = np.full([2, row_len, temp_col_len], np.nan)
    metal_array = np.full([2, row_len, metal_col_len], np.nan)
    logg_array = np.full([2, row_len, logg_col_len], np.nan)
    full_arrays_dict = {key: value for key, value in zip(plot_types,
                                                         (temp_array,
                                                          metal_array,
                                                          logg_array))}

    for label_num, label in tqdm(enumerate(labels), total=len(labels)):

        vprint(f'Analyzing {label}...')
        # The column number to use for this transition:
        try:
            col = column_dict[label]
        except KeyError:
            print(f'Incorrect key given: {label}')
            sys.exit(1)

        for time in tqdm(eras.keys()):

            vprint(20 * '=')
            vprint(f'Working on {time}-change era.')
            mean = np.nanmean(star_transition_offsets[eras[time],
                              :, col])

            # First, create a masked version to catch any missing entries:
            m_offsets = ma.masked_invalid(star_transition_offsets[
                        eras[time], :, col])
            m_offsets = m_offsets.reshape([len(m_offsets), 1])
            # Then create a new array from the non-masked data:
            offsets = u.unyt_array(m_offsets[~m_offsets.mask],
                                   units=u.m/u.s)
            vprint(f'Median of offsets is {np.nanmedian(offsets)}')

            m_eotwms = ma.masked_invalid(star_transition_offsets_EotWM[
                    eras[time], :, col])
            m_eotwms = m_eotwms.reshape([len(m_eotwms), 1])
            eotwms = u.unyt_array(m_eotwms[~m_eotwms.mask],
                                  units=u.m/u.s)

            m_eotms = ma.masked_invalid(star_transition_offsets_EotM[
                    eras[time], :, col])
            m_eotms = m_eotms.reshape([len(m_eotms), 1])
            # Use the same mask as for the offsets.
            eotms = u.unyt_array(m_eotms[~m_offsets.mask],
                                 units=u.m/u.s)
            # Create an error array which uses the greater of the error on
            # the mean or the error on the weighted mean.
            err_array = np.maximum(eotwms, eotms)

            vprint(f'Mean is {np.mean(offsets)}')
            weighted_mean = np.average(offsets, weights=err_array**-2)
            vprint(f'Weighted mean is {weighted_mean}')

            # Mask the various stellar parameter arrays with the same mask
            # so that everything stays in sync.
            temperatures = ma.masked_array(star_temperatures)
            temps = temperatures[~m_offsets.mask]
            metallicities = ma.masked_array(star_metallicities)
            metals = metallicities[~m_offsets.mask]
            magnitudes = ma.masked_array(star_magnitudes)
            mags = magnitudes[~m_offsets.mask]
            gravities = ma.masked_array(star_gravities)
            loggs = gravities[~m_offsets.mask]

            stars = ma.masked_array([key for key in
                                     star_names.keys()]).reshape(
                                         len(star_names.keys()), 1)
            names = stars[~m_offsets.mask]

            # Stack the stellar parameters into vertical slices
            # for passing to model functions.
            x_data = np.stack((temps, metals, loggs), axis=0)

            # Create the parameter list for this run of fitting.
            params_list[0] = float(mean)

            beta0 = tuple(params_list)
            vprint(beta0)

            # Iterate over binned segments of the data to find what additional
            # systematic error is needed to get a chi^2 of ~1.
            arrays_dict = {name: array for name, array in
                           zip(plot_types,
                               (temps, metals, loggs))}

            popt, pcov = curve_fit(model_func, x_data, offsets.value,
                                   sigma=err_array.value,
                                   p0=beta0,
                                   absolute_sigma=True,
                                   method='lm', maxfev=10000)

            model_values = model_func(x_data, *popt)
            residuals = offsets.value - model_values

            if args.nbins:
                nbins = int(args.nbins)
                # Use quantiles to get bins with the same number of elements
                # in them.
                vprint(f'Generating {args.nbins} bins.')
                bins = np.quantile(arrays_dict[name],
                                   np.linspace(0, 1, nbins+1),
                                   interpolation='nearest')
                bin_dict[name] = bins

            min_bin_size = 7
            sigma_sys_dict = {}
            num_params = 1
            for name in tqdm(plot_types):
                sigma_sys_list = []
                sigma_list = []
                bin_mid_list = []
                bin_num = -1
                for bin_lims in pairwise(bin_dict[name]):
                    bin_num += 1
                    lower, upper = bin_lims
                    bin_mid_list.append((lower + upper) / 2)
                    mask_array = ma.masked_outside(arrays_dict[name], *bin_lims)
                    num_points = mask_array.count()
                    vprint(f'{num_points} values in bin ({lower},{upper})')
                    if num_points < min_bin_size:
                        vprint('Skipping this bin!')
                        sigma_list.append(np.nan)
                        sigma_sys_list.append(np.nan)
                        continue
                    temps_copy = temps[~mask_array.mask]
                    metals_copy = metals[~mask_array.mask]
                    mags_copy = mags[~mask_array.mask]
                    residuals_copy = residuals[~mask_array.mask]
                    errs_copy = err_array[~mask_array.mask].value
                    x_data_copy = np.stack((temps_copy, metals_copy, mags_copy),
                                           axis=0)

                    chi_squared_nu = fit.calc_chi_squared_nu(residuals_copy,
                                                             errs_copy,
                                                             num_params)
                    sigma_sys_delta = 0.01
                    sigma_sys = -sigma_sys_delta
                    chi_squared_nu = np.inf
                    variances = np.square(errs_copy)
                    while chi_squared_nu > 1.0:
                        sigma_sys += sigma_sys_delta
                        variance_sys = np.square(sigma_sys)
                        variances_iter = variances + variance_sys
                        # err_iter = np.sqrt(np.square(errs_copy) +
                        #                    np.square(sigma_sys))
                        weights = 1 / variances_iter
                        wmean, sum_weights = np.average(residuals_copy,
                                                        weights=weights,
                                                        returned=True)

                        chi_squared_nu = fit.calc_chi_squared_nu(
                            residuals_copy - wmean, np.sqrt(variances_iter),
                            num_params)

                    sigma_sys_list.append(sigma_sys)
                    sigma = np.std(residuals_copy)
                    sigma_list.append(sigma)
                    # tqdm.write(f'sigma_sys is {sigma_sys:.3f}')
                    # tqdm.write(f'chi^2_nu is {chi_squared_nu}')
                    if sigma_sys / sigma > 1.2:
                        print('---')
                        print(bin_lims)
                        print(mask_array)
                        print(metals)
                        print(residuals)
                        print(n_params)
                        print(num_params)
                        print(residuals_copy)
                        print(errs_copy)
                        print(sigma)
                        print(sigma_sys)
                        sys.exit()

                    # Store the result in the appropriate full array.
                    full_arrays_dict[name][eras[time],
                                           label_num, bin_num] = sigma_sys

                sigma_sys_dict[f'{name}_sigma_sys'] = sigma_sys_list
                sigma_sys_dict[f'{name}_sigma'] = sigma_list
                sigma_sys_dict[f'{name}_bin_mids'] = bin_mid_list

            # sigma = np.nanstd(residuals)

            for plot_type, lims in zip(plot_types,
                                       (temp_lims, mtl_lims, logg_lims)):
                ax = axes_dict[f'{plot_type}_{time}']
                ax.plot(sigma_sys_dict[f'{plot_type}_bin_mids'],
                        sigma_sys_dict[f'{plot_type}_sigma_sys'],
                        color='Black', alpha=0.15,
                        zorder=2)
                        # label=r'$\sigma_\mathrm{sys}$')
                # ax.plot(sigma_sys_dict[f'{plot_type}_bin_mids'],
                #         sigma_sys_dict[f'{plot_type}_sigma'],
                #         color='Blue', alpha=0.3,
                #         label=r'$\sigma$')
                if args.label:
                    ax.legend()

                # ax.annotate(r'$\sigma_\mathrm{sys}$:'
                #             f' {sys_err:.2f}',
                #             (0.01, 0.99),
                #             xycoords='axes fraction',
                #             verticalalignment='top')
                # ax.annotate(fr'$\chi^2_\nu$: {chi_squared_nu.value:.4f}'
                #             '\n'
                #             fr'$\sigma$: {sigma:.2f}',
                #             (0.99, 0.99),
                #             xycoords='axes fraction',
                #             horizontalalignment='right',
                #             verticalalignment='top')
                # data = np.array(ma.masked_invalid(residuals).compressed())

    for time in eras.keys():
        for name in plot_types:
            ax = axes_dict[f'{name}_{time}']
            means = []
            stds = []
            arr = full_arrays_dict[name]
            for i in range(0, np.size(arr, 2)):
                means.append(np.nanmean(arr[eras[time], :, i]))
                stds.append(np.nanstd(arr[eras[time], :, i]))
            ax.errorbar(sigma_sys_dict[f'{name}_bin_mids'], means,
                        yerr=stds, color='Red', alpha=1,
                        marker='o', markersize=4, capsize=4,
                        elinewidth=2, zorder=3,
                        label='Mean and stddev')
            ax.legend()

    plot_path = Path('/Users/dberke/Pictures/'
                     f'sigma_sys_stellar_parameter_dependance')
    if args.label:
        file_name = plot_path / f'{args.label}.png'
    elif args.nbins:
        file_name = plot_path / f'Combined_{model_name}_quantiles.png'
    else:
        file_name = plot_path / f'Combined_{model_name}_fixed_bins.png'
    # plt.show()
    comp_fig.savefig(str(file_name))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Calculate the additional'
                                     ' error needed to reach a chi-squared'
                                     ' value of 1 as a function of various'
                                     ' stellar parameters.')
    parser.add_argument('--label', action='store', type=str,
                        help='The label of the transition to plot (e.g. '
                        "'4589.484Cr2_28'.")
    parser.add_argument('--nbins', action='store', type=int,
                        help='The number of bins to use (default: 5).')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print out more information about the script.')

    func = parser.add_mutually_exclusive_group(required=True)
    func.add_argument('--linear', action='store_true',
                      help='Use a function linear in all three variables.')
    func.add_argument('--quadratic', action='store_true',
                      help='Use a function quadratic in all three variables.')
    func.add_argument('--cross-term', action='store_true',
                      help='Use a linear model with cross term ([Fe/H]/Teff).')
    func.add_argument('--quadratic-magnitude', action='store_true',
                      help='Use a cross term with quadratic magnitude.')

    args = parser.parse_args()

    vprint = vcl.verbose_print(args.verbose)

    main()
