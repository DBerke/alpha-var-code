#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug 13 16:38:30 2020

@author: dberke

A script to plot the per-star pair-wise velocity separations for each pair of
tansitions by various parameters.

"""

import argparse
import csv
from inspect import signature
from itertools import tee
import os
from pathlib import Path
import pickle
from pprint import pprint
import sys

from astropy.coordinates import SkyCoord
import astropy.units as units
import cmasher as cmr
import matplotlib
from matplotlib.gridspec import GridSpec
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as ticker
import numpy as np
import numpy.ma as ma
from numpy import cos, sin
import pandas as pd
from scipy.stats import norm
from tqdm import tqdm
import unyt as u

import varconlib as vcl
from varconlib.fitting import (calc_chi_squared_nu, constant_model,
                               find_sys_scatter)
from varconlib.miscellaneous import (remove_nans, get_params_file,
                                     weighted_mean_and_error)
from varconlib.star import Star
from varconlib.transition_line import roman_numerals

import varconlib.fitting

params_dict = {'temperature': 'Teff (K)',
               'metallicity': '[Fe/H]',
               'logg': 'log(g)'}


types_dict = {'#star_name': str,
              'delta(v)_pair (m/s)': np.float,
              'err_stat_pair (m/s)': np.float,
              'err_sys_pair (m/s)': np.float,
              'transition1 (m/s)': np.float,
              't_stat_err1 (m/s)': np.float,
              't_sys_err1 (m/s)': np.float,
              'chi^2_nu1': np.float,
              'transition2 (m/s)': np.float,
              't_stat_err2 (m/s)': np.float,
              't_sys_err2 (m/s)': np.float,
              'chi^2_nu2': np.float}


plot_axis_labels = {'temperature': r'$\mathrm{T}_\mathrm{eff}\,$(K)',
                    'metallicity': r'$\mathrm{[Fe/H]}$',
                    'logg': r'$\log(g),\mathrm{cm\,s}^{-2}$'}


def pairwise(iterable):
    """Return pairs of results from iterable:

    s -> (s0,s1), (s1,s2), (s2, s3), ...

    """
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def read_csv_file(pair_label, csv_dir, era):
    """
    Import data on a pair from a CSV file.

    Parameters
    ----------
    pair_label : str
        The label of a pair for which the data is to be read.
    csv_dir : `pathlib.Path`
        The path to the main directory where the data files are kept.
    era : str, ['pre', 'post']
        A string denoting whether to read the data for the pre- or post-fiber
        change era.

    Returns
    -------
    None.

    """

    infile = csv_dir / f'{era}/{pair_label}_pair_separations_{era}.csv'
    return pd.read_csv(infile)


def parameter_plot(parameter, passed_ax):
    """
    Plot pairs for a given parameter upon a given axis.

    Parameters
    ----------
    parameter : str, ('temperature', 'metallicity', 'logg')
        The parameter to plot against
    passed_ax : `matplotlib.axis.Axes`
        An `Axes` object on which to plot the values.

    Returns
    -------
    None.

    """


def plot_vs(parameter):
    """
    Plot pair-wise velocity separations as a function of the given parameter.

    Parameters
    ----------
    parameter : str
        The name of the parameter to plot against.

    Returns
    -------
    None.

    """

    tqdm.write('Writing out data for each pair.')
    for pair in tqdm(pairs_list):
        for order_num in pair.ordersToMeasureIn:
            pair_label = "_".join([pair.label, str(order_num)])
            vprint(f'Collecting data for {pair_label}.')

            pair_plots_dir = vcl.output_dir / f'pair_result_plots/{parameter}'
            if not pair_plots_dir.exists():
                os.mkdir(pair_plots_dir)
            data_pre = read_csv_file(pair_label, csv_dir, 'pre')
            data_pre = data_pre.astype(types_dict)
            data_post = read_csv_file(pair_label, csv_dir, 'post')
            data_post = data_post.astype(types_dict)

        fig = plt.figure(figsize=(10, 8), tight_layout=True)
        ax_pre = fig.add_subplot(2, 1, 1)
        ax_post = fig.add_subplot(2, 1, 2,
                                  sharex=ax_pre,
                                  sharey=ax_pre)

        ax_pre.set_xlabel(f'${plot_axis_labels[parameter]}$')
        ax_post.set_xlabel(f'${plot_axis_labels[parameter]}$')
        ax_pre.set_ylabel(r'$\Delta V$ (pair, m/s)')
        ax_post.set_ylabel(r'$\Delta V$ (pair, m/s)')

        for ax in (ax_pre, ax_post):
            ax.yaxis.set_major_locator(ticker.AutoLocator())
            ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
            ax.xaxis.set_major_locator(ticker.AutoLocator())
            ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
            ax.yaxis.grid(which='major', color='Gray',
                          linestyle='-', alpha=0.65)
            ax.yaxis.grid(which='minor', color='Gray',
                          linestyle=':', alpha=0.5)
            ax.xaxis.grid(which='major', color='Gray',
                          linestyle='-', alpha=0.65)
            ax.xaxis.grid(which='minor', color='Gray',
                          linestyle=':', alpha=0.5)

        ax_pre.errorbar(star_data[params_dict[parameter]],
                        data_pre['delta(v)_pair (m/s)'],
                        yerr=np.sqrt(data_pre['err_stat_pair (m/s)']**2 +
                                     data_pre['err_sys_pair (m/s)']**2),
                        color='Chocolate',
                        markeredgecolor='Black', marker='o',
                        linestyle='')
        ax_post.errorbar(star_data[params_dict[parameter]],
                         data_post['delta(v)_pair (m/s)'],
                         yerr=np.sqrt(data_post['err_stat_pair (m/s)']**2 +
                                      data_post['err_sys_pair (m/s)']**2),
                         color='DodgerBlue',
                         markeredgecolor='Black', marker='o',
                         linestyle='')

        outfile = pair_plots_dir / f'{pair_label}.png'

        fig.savefig(str(outfile))
        plt.close('all')


def plot_distance():
    """Plot pair separations as a function of distance from the Sun."""

    tqdm.write('Making plots for each pair as a function of heliocentric'
               ' distance.')
    for pair in tqdm(pairs_list):
        for order_num in pair.ordersToMeasureIn:
            pair_label = "_".join([pair.label, str(order_num)])
            vprint(f'Collecting data for {pair_label}.')

            pair_plots_dir = vcl.output_dir /\
                f'pair_result_plots/heliocentric_distance'
            if not pair_plots_dir.exists():
                os.mkdir(pair_plots_dir)
            data_pre = read_csv_file(pair_label, csv_dir, 'pre')
            data_pre = data_pre.astype(types_dict)
            data_post = read_csv_file(pair_label, csv_dir, 'post')
            data_post = data_post.astype(types_dict)

        fig = plt.figure(figsize=(10, 8), tight_layout=True)
        ax_pre = fig.add_subplot(2, 1, 1)
        ax_post = fig.add_subplot(2, 1, 2,
                                  sharex=ax_pre,
                                  sharey=ax_pre)
        ax_pre.set_xlim(left=-1, right=54)
        ax_pre.set_xlabel('Heliocentric distance (pc)')
        ax_post.set_xlabel('Heliocentric distance (pc)')
        ax_pre.set_ylabel(r'$\Delta v$ (m/s, pre)')
        ax_post.set_ylabel(r'$\Delta v$ (m/s, post)')

        for ax in (ax_pre, ax_post):
            ax.yaxis.set_major_locator(ticker.AutoLocator())
            ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
            ax.xaxis.set_major_locator(ticker.AutoLocator())
            ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
            ax.axhline(0, color='Black')
            ax.yaxis.grid(which='major', color='Gray',
                          linestyle='-', alpha=0.65)
            ax.yaxis.grid(which='minor', color='Gray',
                          linestyle=':', alpha=0.5)
            ax.xaxis.grid(which='major', color='Gray',
                          linestyle='-', alpha=0.65)
            ax.xaxis.grid(which='minor', color='Gray',
                          linestyle=':', alpha=0.5)

        ax_pre.errorbar(star_data['distance (pc)'],
                        data_pre['delta(v)_pair (m/s)'],
                        yerr=np.sqrt(data_pre['err_stat_pair (m/s)']**2 +
                                     data_pre['err_sys_pair (m/s)']**2),
                        color='Chocolate',
                        markeredgecolor='Black', marker='o',
                        linestyle='')
        ax_post.errorbar(star_data['distance (pc)'],
                         data_post['delta(v)_pair (m/s)'],
                         yerr=np.sqrt(data_post['err_stat_pair (m/s)']**2 +
                                      data_post['err_sys_pair (m/s)']**2),
                         color='DodgerBlue',
                         markeredgecolor='Black', marker='o',
                         linestyle='')

        outfile = pair_plots_dir / f'{pair_label}.png'

        fig.savefig(str(outfile))
        plt.close('all')


def plot_galactic_distance():
    """Plot pair separations as a function of distance from the Galactic center.


    Returns
    -------
    None

    """

    RA = star_data['RA'][:-1]
    DEC = star_data['DEC'][:-1]
    dist = star_data['distance (pc)'][:-1]

    coordinates = SkyCoord(ra=RA, dec=DEC, distance=dist,
                           unit=(units.hourangle, units.degree,
                                 units.pc))
    # for c in coordinates:
    #     print(c.galactocentric.x, c.galactocentric.y)
    # exit()

    distances = [np.sqrt(c.galactocentric.x**2 + c.galactocentric.y**2 +
                         c.galactocentric.z**2).value
                 for c in coordinates]
    # Add Sun's galactocentric distance at the end manually.
    distances.append(8300)
    # distances *= u.pc
    # distances = [c.galactocentric.z.value for c in coordinates]
    # distances.append(0)
    # distances *= u.pc

    tqdm.write('Making plots for each pair as a function of galactocentric'
               ' distance.')
    for pair in tqdm(pairs_list):
        for order_num in pair.ordersToMeasureIn:
            pair_label = "_".join([pair.label, str(order_num)])
            vprint(f'Collecting data for {pair_label}.')

            pair_plots_dir = vcl.output_dir /\
                f'pair_result_plots/galactocentric_distance'
            if not pair_plots_dir.exists():
                os.mkdir(pair_plots_dir)
            data_pre = read_csv_file(pair_label, csv_dir, 'pre')
            data_pre = data_pre.astype(types_dict)
            data_post = read_csv_file(pair_label, csv_dir, 'post')
            data_post = data_post.astype(types_dict)

        fig = plt.figure(figsize=(10, 8), tight_layout=True)
        ax_pre = fig.add_subplot(2, 1, 1)
        ax_post = fig.add_subplot(2, 1, 2,
                                  sharex=ax_pre,
                                  sharey=ax_pre)
        ax_pre.set_xlim(left=8245, right=8340)
        ax_pre.set_xlabel('Galactocentric distance (pc)')
        ax_post.set_xlabel('Galactocentric distance (pc)')
        ax_pre.set_ylabel(r'$\Delta v$ (m/s, pre)')
        ax_post.set_ylabel(r'$\Delta v$ (m/s, post)')

        diffs_pre = ma.masked_invalid(data_pre['delta(v)_pair (m/s)'])
        errs_pre = ma.masked_invalid(
            np.sqrt(data_pre['err_stat_pair (m/s)']**2 +
                    data_pre['err_sys_pair (m/s)']**2))

        diffs_post = ma.masked_invalid(data_post['delta(v)_pair (m/s)'])
        errs_post = ma.masked_invalid(
            np.sqrt(data_post['err_stat_pair (m/s)']**2 +
                    data_post['err_sys_pair (m/s)']**2))

        weighted_mean_pre, weight_sum_pre = ma.average(diffs_pre,
                                                       weights=errs_pre**-2,
                                                       returned=True)
        eotwm_pre = 1 / np.sqrt(weight_sum_pre)
        weighted_mean_post, weight_sum_post = ma.average(diffs_post,
                                                         weights=errs_post**-2,
                                                         returned=True)
        eotwm_post = 1 / np.sqrt(weight_sum_post)

        vprint(f'EotWM_pre for {pair_label} is {eotwm_pre}')
        vprint(f'EotWM_post for {pair_label} is {eotwm_post}')

        for ax in (ax_pre, ax_post):
            ax.yaxis.set_major_locator(ticker.AutoLocator())
            ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
            ax.xaxis.set_major_locator(ticker.AutoLocator())
            ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
            ax.yaxis.grid(which='major', color='Gray',
                          linestyle='-', alpha=0.65)
            ax.yaxis.grid(which='minor', color='Gray',
                          linestyle=':', alpha=0.5)
            ax.xaxis.grid(which='major', color='Gray',
                          linestyle='-', alpha=0.65)
            ax.xaxis.grid(which='minor', color='Gray',
                          linestyle=':', alpha=0.5)
            ax.axhline(0, color='Black')

        ax_pre.axhline(weighted_mean_pre, color='Black', linestyle='--')
        ax_pre.fill_between([8245, 8340], weighted_mean_pre+eotwm_pre,
                            y2=weighted_mean_pre-eotwm_pre,
                            color='Gray', alpha=0.4)
        ax_post.axhline(weighted_mean_post, color='Black', linestyle='--')
        ax_post.fill_between([8245, 8340], weighted_mean_post+eotwm_post,
                             y2=weighted_mean_post-eotwm_post,
                             color='Gray', alpha=0.4)

        ax_pre.errorbar(distances,
                        data_pre['delta(v)_pair (m/s)'],
                        yerr=np.sqrt(data_pre['err_stat_pair (m/s)']**2 +
                                     data_pre['err_sys_pair (m/s)']**2),
                        color='Chocolate',
                        markeredgecolor='Black', marker='o',
                        linestyle='')
        ax_post.errorbar(distances,
                         data_post['delta(v)_pair (m/s)'],
                         yerr=np.sqrt(data_post['err_stat_pair (m/s)']**2 +
                                      data_post['err_sys_pair (m/s)']**2),
                         color='DodgerBlue',
                         markeredgecolor='Black', marker='o',
                         linestyle='')

        outfile = pair_plots_dir / f'{pair_label}.png'

        fig.savefig(str(outfile))
        plt.close('all')


def plot_pair_stability(star, pair_label):
    """
    Plot the stability of a single pair for a single star over time.

    Parameters
    ----------
    star : `varconlib.star.Star`
        A Star object.
    pair_label : str
        The pair label for the pair to use.

    Returns
    -------
    None.

    """

    try:
        col_num = star.p_index(pair_label)
    except KeyError:
        raise

    pre_slice = slice(None, star.fiberSplitIndex)
    post_slice = slice(star.fiberSplitIndex, None)

    fig = plt.figure(figsize=(10, 7), tight_layout=True)
    gs = GridSpec(2, 1, figure=fig)
    ax_pre = fig.add_subplot(gs[0, 0])
    ax_post = fig.add_subplot(gs[1, 0])
    for ax in (ax_pre, ax_post):
        ax.set_xlabel('BERV (km/s)')
    ax_pre.set_ylabel('Pair difference (m/s) (pre)')
    ax_post.set_ylabel('Pair difference (m/s) (post)')

    separation_limits = [i for i in range(-25, 30, 5)]

    if star.hasObsPre:
        bervs = star.bervArray[pre_slice]
        diffs = star.pairModelOffsetsArray[pre_slice, col_num]
        errs_stat = star.pairModelErrorsArray[pre_slice, col_num]

        diffs_no_nans, nan_mask = remove_nans(diffs, return_mask=True)
        # print(diffs_no_nans)
        m_diffs = ma.array(diffs_no_nans.to(u.m/u.s).value)
        # print(m_diffs)
        m_errs = ma.array(errs_stat[nan_mask].value)
        bervs_masked = bervs[nan_mask]

        weighted_mean = np.average(m_diffs, weights=m_errs**-2)
        # print(weighted_mean)

        sigma = np.std(diffs_no_nans).to(u.m/u.s)

        results = find_sys_scatter(constant_model, bervs_masked,
                                   m_diffs,
                                   m_errs, (weighted_mean,),
                                   n_sigma=3, tolerance=0.001,
                                   verbose=False)

        sys_err = results['sys_err_list'][-1] * u.m / u.s
        # print(results['chi_squared_list'][-1])

        # vprint(np.std(diffs))

        # ax.axvline(x=star.fiberSplitIndex, linestyle='--', color='Black')
        ax_pre.errorbar(bervs_masked, m_diffs, yerr=m_errs,
                        linestyle='', marker='o',
                        color='Chocolate',
                        # ecolor='Black',
                        markeredgecolor='Black',
                        label=r'$\sigma:$'
                        f' {sigma:.3f},'
                        r' $\sigma_\mathrm{sys}:$'
                        f' {sys_err:.3f}')

        midpoints, w_means, eotwms = [], [], []
        bin_num = len(separation_limits) - 1
        for i, lims in zip(range(bin_num),
                           pairwise(separation_limits)):
            mask = np.where((bervs_masked > lims[0]) &
                            (bervs_masked < lims[1]))
            if len(m_diffs[mask]) == 0:
                midpoints.append(np.nan)
                w_means.append(np.nan)
                eotwms.append(np.nan)
                continue
            midpoints.append((lims[1] + lims[0]) / 2)
            w_mean, eotwm = weighted_mean_and_error(m_diffs[mask],
                                                    m_errs[mask])
            chisq = calc_chi_squared_nu(m_diffs[mask],
                                        m_errs[mask], 1)
            w_means.append(w_mean)
            eotwms.append(eotwm)
            ax_pre.annotate(f'{chisq:.2f}', (midpoints[i], w_means[i]),
                            xytext=(i * bin_num/100 + bin_num/200, -0.02),
                            color='SaddleBrown',
                            textcoords='axes fraction',
                            horizontalalignment='center',
                            verticalalignment='top')

        midpoints = np.array(midpoints)
        w_means = np.array(w_means)
        eotwms = np.array(eotwms)

        # sigma_values = model_offsets_pre / full_errs_pre

        # ax_sigma_pre.errorbar(average_separations_pre,
        #                       sigma_values,
        #                       color='Chocolate', linestyle='',
        #                       marker='.')
        ax_pre.errorbar(midpoints, w_means, yerr=eotwms,
                        linestyle='-', color='Red',
                        marker='')
        # ax_sigma_pre.errorbar(midpoints, w_means / eotwms,
        #                       linestyle=':', marker='o',
        #                       color='ForestGreen')
        # ax_sigma_hist_pre.hist(sigma_values,
        #                        bins=[x for x in np.linspace(-5, 5, num=50)],
        #                        color='Black', histtype='step',
        #                        orientation='horizontal')

    if star.hasObsPost:
        bervs = star.bervArray[post_slice]
        diffs = star.pairModelOffsetsArray[post_slice, col_num]
        errs_stat = star.pairModelErrorsArray[post_slice, col_num]

        diffs_no_nans, nan_mask = remove_nans(diffs, return_mask=True)
        # print(diffs_no_nans)
        m_diffs = ma.array(diffs_no_nans.to(u.m/u.s).value)
        # print(m_diffs)
        m_errs = ma.array(errs_stat[nan_mask].value)
        bervs_masked = bervs[nan_mask]

        weighted_mean = np.average(m_diffs, weights=m_errs**-2)
        # print(weighted_mean)

        sigma = np.std(diffs_no_nans).to(u.m/u.s)

        results = find_sys_scatter(constant_model, bervs_masked,
                                   m_diffs,
                                   m_errs, (weighted_mean,),
                                   n_sigma=3, tolerance=0.001,
                                   verbose=False)

        sys_err = results['sys_err_list'][-1] * u.m / u.s
        # print(results['chi_squared_list'][-1])

        # vprint(np.std(diffs))

        # ax.axvline(x=star.fiberSplitIndex, linestyle='--', color='Black')
        ax_post.errorbar(bervs_masked, m_diffs, yerr=m_errs,
                         linestyle='', marker='o',
                         color='DodgerBlue',
                         # ecolor='Black',
                         markeredgecolor='Black',
                         label=r'$\sigma:$'
                         f' {sigma:.3f},'
                         r' $\sigma_\mathrm{sys}:$'
                         f' {sys_err:.3f}')

        midpoints, w_means, eotwms = [], [], []
        bin_num = len(separation_limits) - 1
        for i, lims in zip(range(bin_num),
                           pairwise(separation_limits)):
            mask = np.where((bervs_masked > lims[0]) &
                            (bervs_masked < lims[1]))
            if len(m_diffs[mask]) == 0:
                midpoints.append(np.nan)
                w_means.append(np.nan)
                eotwms.append(np.nan)
                continue
            midpoints.append((lims[1] + lims[0]) / 2)
            w_mean, eotwm = weighted_mean_and_error(m_diffs[mask],
                                                    m_errs[mask])
            chisq = calc_chi_squared_nu(m_diffs[mask],
                                        m_errs[mask], 1)
            w_means.append(w_mean)
            eotwms.append(eotwm)
            ax_post.annotate(f'{chisq:.2f}', (midpoints[i], w_means[i]),
                             xytext=(i * bin_num/100 + bin_num/200, -0.02),
                             color='RoyalBlue',
                             textcoords='axes fraction',
                             horizontalalignment='center',
                             verticalalignment='top')

        midpoints = np.array(midpoints)
        w_means = np.array(w_means)
        eotwms = np.array(eotwms)

        # sigma_values = model_offsets_pre / full_errs_pre

        # ax_sigma_pre.errorbar(average_separations_pre,
        #                       sigma_values,
        #                       color='Chocolate', linestyle='',
        #                       marker='.')
        ax_post.errorbar(midpoints, w_means, yerr=eotwms,
                         linestyle='-', color='Red',
                         marker='')
        # ax_sigma_pre.errorbar(midpoints, w_means / eotwms,
        #                       linestyle=':', marker='o',
        #                       color='ForestGreen')
        # ax_sigma_hist_pre.hist(sigma_values,
        #                        bins=[x for x in np.linspace(-5, 5, num=50)],
        #                        color='Black', histtype='step',
        #                        orientation='horizontal')

        # ax.legend()
    plt.show()


def plot_sigma_sys_vs_pair_separation(star):
    """
    Plot the sigma_sys for each pair as a function of the average separation.

    Parameters
    ----------
    star : `varconlib.star.Star`
        A `Star` for which to do the plotting.

    Returns
    -------
    None.

    """

    print(f'{star.name} has {star.numObs} observations.')
    n_sigma = 3

    plots_dir = Path('/Users/dberke/Pictures/'
                     'pair_separation_investigation/vs_sigma_sys')

    average_seps_pre = []
    average_seps_post = []
    sigma_sys_list_pre = []
    sigma_sys_list_post = []

    model_seps = []
    model_sigma_sys = []

    for pair, col_num in tqdm(star._pair_bidict.items()):

        x = ma.array([i for i in range(star.numObs)])
        separations = star.pairSeparationsArray[:, col_num]
        errs_stat = star.pairSepErrorsArray[:, col_num]

        seps_no_nans, mask = remove_nans(separations, return_mask=True)
        m_seps = ma.array(seps_no_nans.to(u.m/u.s).value)
        m_errs = ma.array(errs_stat[mask].value)

        weighted_mean = np.average(m_seps, weights=m_errs**-2)

        sigma = np.std(seps_no_nans).to(u.m/u.s)

        results = find_sys_scatter(constant_model, x,
                                   m_seps,
                                   m_errs, (weighted_mean,),
                                   n_sigma=n_sigma, tolerance=0.001,
                                   verbose=False)

        sys_err = results['sys_err_list'][-1] * u.m / u.s
        average_seps_pre.append((weighted_mean * u.m/u.s).to(u.km/u.s))
        sigma_sys_list_pre.append(sys_err)

        model_values = star.pairModelArray[:, col_num]
        model_errs = star.pairModelErrorsArray[:, col_num]
        print(model_values.shape)
        print(model_errs.shape)
        weighted_mean2 = np.average(model_values, weights=model_errs**-2)

        model_results = find_sys_scatter(constant_model, x,
                                         model_values,
                                         model_errs, (weighted_mean2,),
                                         n_sigma=n_sigma, tolerance=0.001,
                                         verbose=False)
        model_seps.append((weighted_mean2 * u.m/u.s).to(u.km/u.s))
        model_sigma_sys.append(model_results['sys_err_list'[-1]] * u.m / u.s)

    fig = plt.figure(figsize=(10, 7), tight_layout=True)
    ax = fig.add_subplot(1, 1, 1)
    ax.set_xlabel('Weighted mean pair separation (km/s)')
    ax.set_ylabel(r'$\sigma_\mathrm{sys}$ (m/s)')
    ax.plot(average_seps_pre, sigma_sys_list_pre,
            linestyle='', marker='o', color='DarkOrange')
    ax.plot(model_seps, model_sigma_sys,
            linestyle='', marker='x', color='MediumAquaMarine')

    filepath = plots_dir / f'{star.name}_{star.numObs}_obs_{n_sigma}sigma.png'
    fig.savefig(str(filepath))
    # plt.show()


def plot_model_diff_vs_pair_separation(star, model, n_sigma=5.0):
    """
    Create a plot showing the difference from a model vs. the pair separation.

    Parameters
    ----------
    star : `varconlib.star.Star`
        The star to analyze.
    model : str
        The name of the model to test against.
    n_sigma : float
        The number of sigma to use for culling outliers in the pair model
        fitting.

    Returns
    -------
    tuple
        A tuple containing the star name, then the number of observations, the
        reduced chi-squared, and the weighted mean and error on the weighted
        mean for both the pre- and post- fiber change eras, with NaNs instead
        if there were no relevant values for an era.

    """

    tqdm.write(f'{star.name} has {star.numObs} observations'
               f' ({star.numObsPre} pre, {star.numObsPost} post)')

    plots_dir = Path('/Users/dberke/Pictures/'
                     'pair_separation_investigation')

    # Get the star pair corrections arrays for the given model.
    if n_sigma != 4.0:
        star.createPairModelCorrectedArrays(model_func=model, n_sigma=n_sigma)

    # model_func = getattr(varconlib.fitting, f'{model}_model')
    # num_params = len(signature(model_func).parameters) - 1
    num_params = 1

    filename = vcl.output_dir /\
        f'fit_params/{model}_pairs_{n_sigma:.1f}sigma_params.hdf5'
    fit_results_dict = get_params_file(filename)
    sigma_sys_dict = fit_results_dict['sigmas_sys']

    pre_slice = slice(None, star.fiberSplitIndex)
    post_slice = slice(star.fiberSplitIndex, None)

    average_separations_pre = []
    model_offsets_pre = []
    pair_sep_errs_pre = []
    average_separations_post = []
    model_offsets_post = []
    pair_sep_errs_post = []

    sigmas_sys_pre = []
    sigmas_sys_post = []

    # Initialize these variables as NaN so as not to break the code returning
    # them if the star only has observations from one era:
    chi_squared_nu_pre, w_mean_pre, eotwm_pre = np.nan, np.nan, np.nan
    chi_squared_nu_post, w_mean_post, eotwm_post = np.nan, np.nan, np.nan

    for pair_label, col_num in tqdm(star._pair_bidict.items()):

        if star.hasObsPre:
            separations = star.pairSeparationsArray[pre_slice, col_num]
            errs_stat = star.pairSepErrorsArray[pre_slice, col_num]

            # If all separations are non-existent for this pair, continue.
            if np.isnan(separations).all():
                continue

            # Now get the weighted mean of the remaining offset from the model.
            corrected_separations = star.pairModelOffsetsArray[pre_slice,
                                                               col_num]
            corrected_errs_stat = star.pairModelErrorsArray[pre_slice,
                                                            col_num]

            if np.isnan(corrected_separations).all():
                continue

            sigmas_sys_pre.append(sigma_sys_dict[pair_label + '_pre'])
            seps_no_nans, mask = remove_nans(separations, return_mask=True)
            m_seps = ma.array(seps_no_nans.to(u.m/u.s).value)
            m_errs = ma.array(errs_stat[mask].value)

            try:
                weighted_mean, error_on_weighted_mean = weighted_mean_and_error(
                    m_seps, m_errs)
            except ZeroDivisionError:
                print(separations)
                print(errs_stat)
                raise

            average_separations_pre.append((weighted_mean
                                            * u.m/u.s).to(u.km/u.s))
            pair_sep_errs_pre.append(error_on_weighted_mean * u.m/u.s)

            seps_no_nans, mask = remove_nans(corrected_separations,
                                             return_mask=True)
            m_c_seps = ma.array(seps_no_nans.to(u.m/u.s).value)
            m_c_errs = ma.array(errs_stat[mask].value)

            try:
                weighted_c_mean, weight_c_sum = np.average(m_c_seps,
                                                           weights=m_c_errs**-2,
                                                           returned=True)
            except ZeroDivisionError:
                print(separations, errs_stat)
                print(corrected_separations, corrected_errs_stat)
                print(m_c_seps, m_c_errs)
                raise

            model_offsets_pre.append(weighted_c_mean * u.m/u.s)

        if star.hasObsPost:
            separations = star.pairSeparationsArray[post_slice, col_num]
            errs_stat = star.pairSepErrorsArray[post_slice, col_num]

            if np.isnan(separations).all():
                continue

            # Now get the weighted mean of the remaining offset from the model.
            corrected_separations = star.pairModelOffsetsArray[post_slice,
                                                               col_num]
            corrected_errs_stat = star.pairModelErrorsArray[post_slice,
                                                            col_num]

            if np.isnan(corrected_separations).all():
                continue

            sigmas_sys_post.append(sigma_sys_dict[pair_label + '_post'])
            seps_no_nans, mask = remove_nans(separations, return_mask=True)
            m_seps = ma.array(seps_no_nans.to(u.m/u.s).value)
            m_errs = ma.array(errs_stat[mask].value)

            weighted_mean, error_on_weighted_mean = weighted_mean_and_error(
                m_seps, m_errs)

            average_separations_post.append((weighted_mean
                                            * u.m/u.s).to(u.km/u.s))
            pair_sep_errs_post.append(error_on_weighted_mean * u.m/u.s)

            seps_no_nans, mask = remove_nans(corrected_separations,
                                             return_mask=True)
            m_c_seps = ma.array(seps_no_nans.to(u.m/u.s).value)
            m_c_errs = ma.array(errs_stat[mask].value)

            weighted_c_mean, weight_c_sum = np.average(m_c_seps,
                                                       weights=m_c_errs**-2,
                                                       returned=True)

            model_offsets_post.append(weighted_c_mean * u.m/u.s)

    # Plot the results.
    fig = plt.figure(figsize=(14, 10), tight_layout=True)
    gs = GridSpec(ncols=2, nrows=5, figure=fig,
                  width_ratios=(8.5, 1),
                  height_ratios=(2.1, 1, 0.4, 2.1, 1), hspace=0)
    ax_pre = fig.add_subplot(gs[0, 0])
    ax_post = fig.add_subplot(gs[3, 0], sharex=ax_pre, sharey=ax_pre)
    ax_hist_pre = fig.add_subplot(gs[0, -1], sharey=ax_pre)
    ax_hist_post = fig.add_subplot(gs[3, -1], sharey=ax_post)
    ax_sigma_pre = fig.add_subplot(gs[1, 0], sharex=ax_pre)
    ax_sigma_post = fig.add_subplot(gs[4, 0], sharex=ax_pre,
                                    sharey=ax_sigma_pre)
    ax_sigma_hist_pre = fig.add_subplot(gs[1, 1])
    ax_sigma_hist_post = fig.add_subplot(gs[4, 1],
                                         sharey=ax_sigma_hist_pre)

    ax_pre.set_xlim(left=0, right=800)
    ax_pre.set_ylim(bottom=-60, top=60)
    ax_sigma_hist_pre.set_ylim(bottom=-3, top=3)
    for ax in (ax_sigma_pre, ax_sigma_post,
               ax_sigma_hist_pre, ax_sigma_hist_post):
        ax.yaxis.grid(which='major', color='Gray', alpha=0.7,
                      linestyle='-')
        ax.yaxis.grid(which='minor', color='Gray', alpha=0.6,
                      linestyle='--')
        ax.yaxis.set_major_locator(ticker.AutoLocator())
        ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    for ax in (ax_pre, ax_post, ax_hist_pre, ax_hist_post):
        plt.setp(ax.get_xticklabels(), visible=False)
    ax_post.set_xlabel('Weighted mean pair separation (km/s)')
    ax_pre.set_ylabel('Offset from model\nvalue (pre) (m/s)')
    ax_post.set_ylabel('Offset from model\nvalue (post) (m/s)')
    ax_sigma_pre.set_ylabel('Binned weighted means/\n'
                            r'$\sigma$-offsets (m/s)/$\sigma$')
    ax_sigma_post.set_ylabel('Binned weighted means/\n'
                             r'$\sigma$-offsets (m/s)/$\sigma$')
    for ax in (ax_pre, ax_post, ax_hist_pre, ax_hist_post,
               ax_sigma_pre, ax_sigma_post,
               ax_sigma_hist_pre, ax_sigma_hist_post):
        ax.axhline(y=0, linestyle='--', color='Gray')

    # Add some information about the star to the figure:
    information = [r'T$_\mathrm{eff}$:' + f' {star.temperature}',
                   f'[Fe/H]: {star.metallicity}',
                   r'$\log{g}$:' + f' {star.logg}']
    for key, value in star.specialAttributes.items():
        information.append(f'{key}: {value}')

    info = '      '.join(information)
    ax_pre.annotate(info, (0.07, 0.5),
                    xycoords='figure fraction')

    if star.hasObsPre:
        full_errs_pre = np.sqrt(u.unyt_array(pair_sep_errs_pre,
                                             units='m/s') ** 2 +
                                u.unyt_array(sigmas_sys_pre,
                                             units='m/s') ** 2)
        chi_squared_nu_pre = calc_chi_squared_nu(model_offsets_pre,
                                                 full_errs_pre,
                                                 num_params).value

        label = r'$\chi^2_\nu$:' +\
            f' {chi_squared_nu_pre:.2f}, {star.numObsPre} obs'

        ax_pre.errorbar(average_separations_pre, model_offsets_pre,
                        yerr=full_errs_pre,
                        linestyle='', marker='o',
                        color='Chocolate',
                        markeredgecolor='Black',
                        label=label)
        ax_pre.legend(loc='upper right')
    if star.hasObsPost:
        full_errs_post = np.sqrt(u.unyt_array(pair_sep_errs_post,
                                              units='m/s') ** 2 +
                                 u.unyt_array(sigmas_sys_post,
                                              units='m/s') ** 2)
        chi_squared_nu_post = calc_chi_squared_nu(model_offsets_post,
                                                  full_errs_post,
                                                  num_params).value

        label = r'$\chi^2_\nu$:' +\
            f' {chi_squared_nu_post:.2f}, {star.numObsPost} obs'

        ax_post.errorbar(average_separations_post, model_offsets_post,
                         yerr=full_errs_post,
                         linestyle='', marker='o',
                         color='DodgerBlue',
                         markeredgecolor='Black',
                         label=label)
        ax_post.legend(loc='upper right')

    # Plot on the separation histogram axes.
    gaussians_pre = []
    gaussians_post = []
    if star.hasObsPre:
        for offset, err in zip(model_offsets_pre, full_errs_pre):
            gaussians_pre.append(norm(loc=0, scale=err))
    if star.hasObsPost:
        for offset, err in zip(model_offsets_post, full_errs_post):
            gaussians_post.append(norm(loc=0, scale=err))

    bottom, top = ax_pre.get_ylim()
    bins = [x for x in range(int(bottom), int(top), 1)]

    pdf_pre = []
    pdf_post = []
    # Add up the PDFs for each point.
    for x in tqdm(bins):
        if star.hasObsPre:
            pdf_pre.append(np.sum([y.pdf(x) for y in gaussians_pre]))
        if star.hasObsPost:
            pdf_post.append(np.sum([y.pdf(x) for y in gaussians_post]))

    if star.hasObsPre:
        ax_hist_pre.hist(model_offsets_pre, bins=bins, color='Black',
                         histtype='step', orientation='horizontal')
        ax_hist_pre.step(pdf_pre, bins, color='Green',
                         where='mid', linestyle='-')
        w_mean_pre, eotwm_pre = weighted_mean_and_error(model_offsets_pre,
                                                        full_errs_pre)
        w_mean_pre = w_mean_pre.value
        eotwm_pre = eotwm_pre.value
        ax_hist_pre.annotate(f'{w_mean_pre:.2f}±\n'
                             f'{eotwm_pre:.2f} m/s',
                             (0.99, 0.99),
                             xycoords='axes fraction',
                             verticalalignment='top',
                             horizontalalignment='right')
    if star.hasObsPost:
        ax_hist_post.hist(model_offsets_post, bins=bins, color='Black',
                          histtype='step', orientation='horizontal')
        ax_hist_post.step(pdf_post, bins, color='Green',
                          where='mid', linestyle='-')
        w_mean_post, eotwm_post = weighted_mean_and_error(model_offsets_post,
                                                          full_errs_post)
        w_mean_post = w_mean_post.value
        eotwm_post = eotwm_post.value
        ax_hist_post.annotate(f'{w_mean_post:.2f}±\n'
                              f'{eotwm_post:.2f} m/s',
                              (0.99, 0.99),
                              xycoords='axes fraction',
                              verticalalignment='top',
                              horizontalalignment='right')

    # Do the binned checks.
    separation_limits = [i for i in range(0, 900, 100)]
    if star.hasObsPre:
        average_separations_pre = np.array(average_separations_pre)
        model_offsets_pre = np.array(model_offsets_pre)
    if star.hasObsPost:
        average_separations_post = np.array(average_separations_post)
        model_offsets_post = np.array(model_offsets_post)

    if star.hasObsPre:
        midpoints, w_means, eotwms = [], [], []
        for i, lims in zip(range(8), pairwise(separation_limits)):
            midpoints.append((lims[1] + lims[0]) / 2)
            mask = np.where((average_separations_pre > lims[0]) &
                            (average_separations_pre < lims[1]))
            w_mean, eotwm = weighted_mean_and_error(model_offsets_pre[mask],
                                                    full_errs_pre[mask])
            chisq = calc_chi_squared_nu(model_offsets_pre[mask],
                                        full_errs_pre[mask], 1).value
            w_means.append(w_mean)
            eotwms.append(eotwm)
            ax_sigma_pre.annotate(f'{chisq:.2f}', (midpoints[i], w_means[i]),
                                  xytext=(i * 0.125 + 0.0625, -0.02),
                                  color='SaddleBrown',
                                  textcoords='axes fraction',
                                  horizontalalignment='center',
                                  verticalalignment='top')

        midpoints = np.array(midpoints)
        w_means = np.array(w_means)
        eotwms = np.array(eotwms)

        sigma_values = model_offsets_pre / full_errs_pre

        ax_sigma_pre.errorbar(average_separations_pre,
                              sigma_values,
                              color='Chocolate', linestyle='',
                              marker='.')
        ax_sigma_pre.errorbar(midpoints, w_means, yerr=eotwms,
                              linestyle='-', color='Black',
                              marker='o')
        ax_sigma_pre.errorbar(midpoints, w_means / eotwms,
                              linestyle=':', marker='o',
                              color='ForestGreen')
        ax_sigma_hist_pre.hist(sigma_values,
                               bins=[x for x in np.linspace(-5, 5, num=50)],
                               color='Black', histtype='step',
                               orientation='horizontal')

    if star.hasObsPost:
        midpoints, w_means, eotwms, chiqs = [], [], [], []
        for i, lims in zip(range(8), pairwise(separation_limits)):
            midpoints.append((lims[1] + lims[0]) / 2)
            mask = np.where((average_separations_post > lims[0]) &
                            (average_separations_post < lims[1]))
            w_mean, eotwm = weighted_mean_and_error(model_offsets_post[mask],
                                                    full_errs_post[mask])
            chisq = calc_chi_squared_nu(model_offsets_post[mask],
                                        full_errs_post[mask], 1).value
            w_means.append(w_mean)
            eotwms.append(eotwm)
            ax_sigma_post.annotate(f'{chisq:.2f}', (midpoints[i], w_means[i]),
                                   xytext=(i * 0.125 + 0.0625, -0.02),
                                   color='RoyalBlue',
                                   textcoords='axes fraction',
                                   horizontalalignment='center',
                                   verticalalignment='top')

            if lims[0] == 500 and lims[1] == 600:
                print(w_mean)
                print(eotwm)
                # outfile = plots_dir /\
                #     f'{n_sigma}sigma_bin_values_{star.name}.csv'
                # with open(outfile, 'w', newline='') as f:
                #     datawriter = csv.writer(f)
                #     for value, err in zip(model_offsets_post[mask],
                #                           full_errs_post[mask].value):
                #         datawriter.writerow((value, err))

        midpoints = np.array(midpoints)
        w_means = np.array(w_means)
        eotwms = np.array(eotwms)

        sigma_values = model_offsets_post / full_errs_post

        ax_sigma_post.errorbar(average_separations_post,
                               sigma_values,
                               color='DodgerBlue', linestyle='',
                               marker='.')
        ax_sigma_post.errorbar(midpoints, w_means, yerr=eotwms,
                               linestyle='-', color='Black',
                               marker='o')
        ax_sigma_post.errorbar(midpoints, w_means / eotwms,
                               linestyle=':', marker='o',
                               color='ForestGreen')
        ax_sigma_hist_post.hist(sigma_values,
                                bins=[x for x in np.linspace(-5, 5, num=50)],
                                color='Black', histtype='step',
                                orientation='horizontal')

    # Save out the plot.
    plots_dir = plots_dir / f'{n_sigma}-sigma'
    if not plots_dir.exists():
        os.mkdir(plots_dir)
    filepath = plots_dir /\
        f'{star.name}_{star.numObs}_obs_{n_sigma}sigma_{model}_offsets.png'
    fig.savefig(str(filepath))
    plt.close('all')
    return (star.name,
            star.numObsPre, chi_squared_nu_pre,
            w_mean_pre, eotwm_pre,
            star.numObsPost, chi_squared_nu_post,
            w_mean_post, eotwm_post)


def plot_duplicate_pairs(star):
    """
    Create a plot comparing the duplicate pairs for the given star.

    Parameters
    ----------
    star : `varconlib.star.Star`
        The star to use for comparing its duplicate pairs.

    Returns
    -------
    None.

    """

    pair_sep_pre1, pair_model_pre1 = [], []
    pair_sep_err_pre1, pair_model_err_pre1 = [], []
    pair_sep_post1, pair_model_post1 = [], []
    pair_sep_err_post1, pair_model_err_post1 = [], []

    pair_sep_pre2, pair_model_pre2 = [], []
    pair_sep_err_pre2, pair_model_err_pre2 = [], []
    pair_sep_post2, pair_model_post2 = [], []
    pair_sep_err_post2, pair_model_err_post2 = [], []

    pair_order_numbers = []
    for pair in tqdm(star.pairsList):
        if len(pair.ordersToMeasureIn) == 2:
            pair_order_numbers.append(pair.ordersToMeasureIn[1])
            p_index1 = star.p_index('_'.join([pair.label,
                                              str(pair.ordersToMeasureIn[0])]))
            p_index2 = star.p_index('_'.join([pair.label,
                                              str(pair.ordersToMeasureIn[1])]))

            if star.hasObsPre:
                # Get the values for the first duplicate
                time_slice = slice(None, star.fiberSplitIndex)
                w_mean, eotwm = get_weighted_mean(
                    star.pairSeparationsArray,
                    star.pairSepErrorsArray,
                    time_slice,
                    p_index1)
                pair_sep_pre1.append(w_mean)
                pair_sep_err_pre1.append(eotwm)
                w_mean, eotwm = get_weighted_mean(
                    star.pairModelOffsetsArray,
                    star.pairModelErrorsArray,
                    time_slice,
                    p_index1)
                pair_model_pre1.append(w_mean)
                pair_model_err_pre1.append(eotwm)

                # Get the values for the second duplicate
                time_slice = slice(None, star.fiberSplitIndex)
                w_mean, eotwm = get_weighted_mean(
                    star.pairSeparationsArray,
                    star.pairSepErrorsArray,
                    time_slice,
                    p_index2)
                pair_sep_pre2.append(w_mean)
                pair_sep_err_pre2.append(eotwm)
                w_mean, eotwm = get_weighted_mean(
                    star.pairModelOffsetsArray,
                    star.pairModelErrorsArray,
                    time_slice,
                    p_index2)
                pair_model_pre2.append(w_mean)
                pair_model_err_pre2.append(eotwm)

            if star.hasObsPost:
                # Get the values for the first instance.
                time_slice = slice(star.fiberSplitIndex, None)
                w_mean, eotwm = get_weighted_mean(
                    star.pairSeparationsArray,
                    star.pairSepErrorsArray,
                    time_slice,
                    p_index1)
                pair_sep_post1.append(w_mean)
                pair_sep_err_post1.append(eotwm)
                w_mean, eotwm = get_weighted_mean(
                    star.pairModelOffsetsArray,
                    star.pairModelErrorsArray,
                    time_slice,
                    p_index1)
                pair_model_post1.append(w_mean)
                pair_model_err_post1.append(eotwm)

                # Get the values for the second instance.
                time_slice = slice(star.fiberSplitIndex, None)
                w_mean, eotwm = get_weighted_mean(
                    star.pairSeparationsArray,
                    star.pairSepErrorsArray,
                    time_slice,
                    p_index2)
                pair_sep_post2.append(w_mean)
                pair_sep_err_post2.append(eotwm)
                w_mean, eotwm = get_weighted_mean(
                    star.pairModelOffsetsArray,
                    star.pairModelErrorsArray,
                    time_slice,
                    p_index2)
                pair_model_post2.append(w_mean)
                pair_model_err_post2.append(eotwm)

    # pprint(pair_order_numbers)

    if star.hasObsPre:
        pair_sep_pre1 = np.array(pair_sep_pre1)
        pair_model_pre1 = np.array(pair_model_pre1)
        pair_sep_err_pre1 = np.array(pair_sep_err_pre1)
        pair_model_err_pre1 = np.array(pair_model_err_pre1)
        pair_sep_pre2 = np.array(pair_sep_pre2)
        pair_model_pre2 = np.array(pair_model_pre2)
        pair_sep_err_pre2 = np.array(pair_sep_err_pre2)
        pair_model_err_pre2 = np.array(pair_model_err_pre2)

    if star.hasObsPost:
        pair_sep_post1 = np.array(pair_sep_post1)
        pair_model_post1 = np.array(pair_model_post1)
        pair_sep_err_post1 = np.array(pair_sep_err_post1)
        pair_model_err_post1 = np.array(pair_model_err_post1)
        pair_sep_post2 = np.array(pair_sep_post2)
        pair_model_post2 = np.array(pair_model_post2)
        pair_sep_err_post2 = np.array(pair_sep_err_post2)
        pair_model_err_post2 = np.array(pair_model_err_post2)

    # Plot the results

    fig = plt.figure(figsize=(12, 9), tight_layout=True)
    gs = GridSpec(ncols=2, nrows=1, figure=fig,
                  width_ratios=(1, 1))
    ax_pre = fig.add_subplot(gs[0, 0])
    if (star.hasObsPre and star.hasObsPost):
        ax_post = fig.add_subplot(gs[0, 1],
                                  sharex=ax_pre)
    else:
        ax_post = fig.add_subplot(gs[0, 1])

    ax_pre.set_ylabel('Pair index')
    # ax_post.set_ylabel(r'$\Delta$(Separation) post')
    ax_pre.set_xlabel(f'(Instance 2 – Instance 1) {star.numObsPre} obs'
                      ' (pre, m/s)')
    ax_post.set_xlabel(f'(Instance 2 – Instance 1) {star.numObsPost} obs'
                       ' (post, m/s)')

    order_boundaries = []
    for i in range(len(pair_order_numbers)):
        if i == 0:
            continue
        if pair_order_numbers[i-1] != pair_order_numbers[i]:
            order_boundaries.append(i - 0.5)

    for ax in (ax_pre, ax_post):
        # ax.yaxis.grid(which='major', color='Gray', alpha=0.7,
        #               linestyle='-')
        # ax.yaxis.grid(which='minor', color='Gray', alpha=0.6,
        #               linestyle='--')
        ax.axvline(x=0, linestyle='-', color='Gray')
        ax.set_ylim(bottom=-1, top=56)
        for b in order_boundaries:
            ax.axhline(y=b, linestyle='--', color='DimGray')

    if star.hasObsPre:
        pair_indices = np.array([x for x in range(len(pair_sep_pre1))])
    else:
        pair_indices = np.array([x for x in range(len(pair_sep_post1))])
    model_pair_indices = pair_indices + 0.2

    if star.hasObsPre:
        pair_diffs = pair_sep_pre2 - pair_sep_pre1
        model_diffs = pair_model_pre2 - pair_model_pre1
        pair_errs = np.sqrt(pair_sep_err_pre1**2 + pair_sep_err_pre2**2)
        model_errs = np.sqrt(pair_model_err_pre1**2 + pair_model_err_pre2**2)

        pairs_chisq = calc_chi_squared_nu(remove_nans(pair_diffs),
                                          remove_nans(pair_errs), 1)
        model_chisq = calc_chi_squared_nu(remove_nans(model_diffs),
                                          remove_nans(model_errs), 1)
        pairs_sigma = np.nanstd(pair_diffs)
        model_sigma = np.nanstd(model_diffs)

        ax_pre.errorbar(pair_diffs, pair_indices,
                        xerr=pair_errs,
                        color='Chocolate', markeredgecolor='Black',
                        linestyle='', marker='o',
                        label=r'Pair $\chi^2_\nu$:'
                        f' {pairs_chisq:.2f}, RMS: {pairs_sigma:.2f}')
        ax_pre.errorbar(model_diffs, model_pair_indices,
                        xerr=model_errs,
                        color='SeaGreen', markeredgecolor='Black',
                        linestyle='', marker='o',
                        label=r'Model $\chi^2_\nu$:'
                        f' {model_chisq:.2f}, RMS: {model_sigma:.2f}')
        ax_pre.legend()

    if star.hasObsPost:
        pair_diffs = pair_sep_post2 - pair_sep_post1
        pair_errs = np.sqrt(pair_sep_err_post1**2 + pair_sep_err_post2**2)
        model_diffs = pair_model_post2 - pair_model_post1
        model_errs = np.sqrt(pair_model_err_post1**2 + pair_model_err_post2**2)

        pairs_chisq = calc_chi_squared_nu(remove_nans(pair_diffs),
                                          remove_nans(pair_errs), 1)
        model_chisq = calc_chi_squared_nu(remove_nans(model_diffs),
                                          remove_nans(model_errs), 1)
        pairs_sigma = np.std(pair_diffs)
        model_sigma = np.std(model_diffs)

        ax_post.errorbar(pair_diffs, pair_indices,
                         xerr=pair_errs,
                         color='DodgerBlue', markeredgecolor='Black',
                         linestyle='', marker='o',
                         label=r'Pair $\chi^2_\nu$:'
                         f' {pairs_chisq:.2f}, RMS: {pairs_sigma:.2f}')
        ax_post.errorbar(model_diffs, model_pair_indices,
                         xerr=model_errs,
                         color='GoldenRod', markeredgecolor='Black',
                         linestyle='', marker='o',
                         label=r'Model $\chi^2_\nu$:'
                         f' {model_chisq:.2f}, RMS: {model_sigma:.2f}')
        ax_post.legend()

    # plt.show(fig)
    output_dir = Path('/Users/dberke/Pictures/duplicate_pairs')
    outfile = output_dir /\
        f'{star.name}_{star.radialVelocity.value:.2f}kms.png'
    fig.savefig(str(outfile))
    plt.close('all')


def plot_pair_depth_differences(star):
    """
    Create a plot to investigate pair depth differences for systematics.

    Parameters
    ----------
    star : `varconlib.star.Star`
        The star to plot the differences for.

    Returns
    -------
    None.

    """

    tqdm.write(f'{star.name} has {star.numObs} observations'
               f' ({star.numObsPre} pre, {star.numObsPost} post)')

    plots_dir = Path('/Users/dberke/Pictures/'
                     'pair_depth_differences_investigation')
    if not plots_dir.exists():
        os.mkdir(plots_dir)

    filename = vcl.output_dir /\
        f'fit_params/quadratic_pairs_4.0sigma_params.hdf5'
    fit_results_dict = get_params_file(filename)
    sigma_sys_dict = fit_results_dict['sigmas_sys']

    pair_depth_diffs = []
    pair_depth_means = []
    pair_model_sep_pre, pair_model_sep_post = [], []
    pair_model_err_pre, pair_model_err_post = [], []

    sigmas_sys_pre = []
    sigmas_sys_post = []

    pre_slice = slice(None, star.fiberSplitIndex)
    post_slice = slice(star.fiberSplitIndex, None)

    for pair in star.pairsList:
        for order_num in pair.ordersToMeasureIn:
            pair_label = '_'.join([pair.label, str(order_num)])
            col_index = star._pair_bidict[pair_label]
            h_d = pair._higherEnergyTransition.normalizedDepth
            l_d = pair._lowerEnergyTransition.normalizedDepth
            # depth_diff = l_d - h_d
            pair_depth_means.append((l_d + h_d) / 2)
            pair_depth_diffs.append(abs(l_d - h_d))

            if star.hasObsPre:
                w_mean, eotwm = get_weighted_mean(star.pairModelOffsetsArray,
                                                  star.pairModelErrorsArray,
                                                  pre_slice, col_index)
                pair_model_sep_pre.append(w_mean)
                pair_model_err_pre.append(eotwm)
                sigmas_sys_pre.append(
                    sigma_sys_dict[pair_label + '_pre'].value)

            if star.hasObsPost:
                w_mean, eotwm = get_weighted_mean(star.pairModelOffsetsArray,
                                                  star.pairModelErrorsArray,
                                                  post_slice, col_index)
                pair_model_sep_post.append(w_mean)
                pair_model_err_post.append(eotwm)
                sigmas_sys_post.append(
                    sigma_sys_dict[pair_label + '_post'].value)

    pair_depth_diffs = np.array(pair_depth_diffs)
    pair_depth_means = np.array(pair_depth_means)
    pair_model_sep_pre = np.array(pair_model_sep_pre)
    pair_model_sep_post = np.array(pair_model_sep_post)
    pair_model_err_pre = np.array(pair_model_err_pre)
    pair_model_err_post = np.array(pair_model_err_post)
    sigmas_sys_pre = np.array(sigmas_sys_pre)
    sigmas_sys_post = np.array(sigmas_sys_post)

    fig = plt.figure(figsize=(10, 9), tight_layout=True)
    gs = GridSpec(ncols=2, nrows=4, figure=fig,
                  height_ratios=(5, 2, 5, 2),
                  width_ratios=(4.8, 1))
    ax_pre = fig.add_subplot(gs[0, :])
    ax_pre_sig = fig.add_subplot(gs[1, 0])
    ax_post = fig.add_subplot(gs[2, :])
    ax_post_sig = fig.add_subplot(gs[3, 0])

    ax_pre.set_ylabel('Model-corrected weighted\nmean pair separations (pre)')
    ax_post.set_ylabel('Model-corrected weighted\nmean pair separations (post)')
    ax_pre_sig.set_ylabel('Weighted mean\nper bin')
    ax_post_sig.set_ylabel('Weighted mean\nper bin')
    ax_post_sig.set_xlabel('Pair normalized depth difference')

    for ax in (ax_pre, ax_post, ax_pre_sig, ax_post_sig):
        ax.yaxis.grid(which='major', color='Gray',
                      linestyle='-', alpha=0.65)
        ax.yaxis.grid(which='minor', color='Gray',
                      linestyle=':', alpha=0.5)
        ax.set_xlim(left=-0.002, right=0.202)

    if star.hasObsPre:
        full_errs_pre = np.sqrt(pair_model_err_pre ** 2 +
                                sigmas_sys_pre ** 2)
        values, mask = remove_nans(pair_model_sep_pre, return_mask=True)
        chisq = calc_chi_squared_nu(values,
                                    full_errs_pre[mask], 1)
        ax_pre.errorbar(pair_depth_diffs, pair_model_sep_pre,
                        yerr=full_errs_pre,
                        linestyle='', marker='.',
                        color='Chocolate',
                        zorder=0,
                        label=r'$\chi^2_\nu$:'
                        f' {chisq:.2f}, {star.numObsPre} obs')
        clb_pre = ax_pre.scatter(pair_depth_diffs, pair_model_sep_pre,
                                 marker='o',
                                 c=pair_depth_means,
                                 cmap=cmr.get_sub_cmap('cmr.ember',
                                                       0.1, 0.85),
                                 zorder=2)
        fig.colorbar(clb_pre, ax=ax_pre, label='Mean pair depth')
        ax_pre.legend()

    if star.hasObsPost:
        full_errs_post = np.sqrt(pair_model_err_post ** 2 +
                                 sigmas_sys_post ** 2)
        values, mask = remove_nans(pair_model_sep_post, return_mask=True)
        chisq = calc_chi_squared_nu(values,
                                    full_errs_post[mask], 1)
        ax_post.errorbar(pair_depth_diffs, pair_model_sep_post,
                         yerr=full_errs_post,
                         linestyle='', marker='.',
                         color='DodgerBlue',
                         zorder=0)
        clb_post = ax_post.scatter(pair_depth_diffs, pair_model_sep_post,
                                   marker='o',
                                   c=pair_depth_means,
                                   cmap=cmr.get_sub_cmap('cmr.cosmic',
                                                         0.1, 0.85),
                                   zorder=2,
                                   label=r'$\chi^2_\nu$:'
                                   f' {chisq:.2f}, {star.numObsPost} obs')
        fig.colorbar(clb_post, ax=ax_post, label='Mean pair depth')
        ax_post.legend()

    # Get results for bins.
    bin_lims = np.linspace(0, 0.2, 9)

    if star.hasObsPre:
        midpoints, w_means, eotwms = [], [], []
        for i, lims in zip(range(8), pairwise(bin_lims)):
            midpoints.append((lims[1] + lims[0]) / 2)
            mask = np.where((pair_depth_diffs > lims[0]) &
                            (pair_depth_diffs < lims[1]))
            values, nan_mask = remove_nans(pair_model_sep_pre[mask],
                                           return_mask=True)
            errs = pair_model_err_pre[mask][nan_mask]
            w_mean, eotwm = weighted_mean_and_error(values, errs)
            w_means.append(w_mean)
            eotwms.append(eotwm)

        ax_pre_sig.errorbar(midpoints, w_means, yerr=eotwms,
                            color='Green')

    if star.hasObsPost:
        midpoints, w_means, eotwms = [], [], []
        for i, lims in zip(range(8), pairwise(bin_lims)):
            midpoints.append((lims[1] + lims[0]) / 2)
            mask = np.where((pair_depth_diffs > lims[0]) &
                            (pair_depth_diffs < lims[1]))
            values, nan_mask = remove_nans(pair_model_sep_post[mask],
                                           return_mask=True)
            errs = pair_model_err_post[mask][nan_mask]
            w_mean, eotwm = weighted_mean_and_error(values, errs)
            w_means.append(w_mean)
            eotwms.append(eotwm)

        ax_post_sig.errorbar(midpoints, w_means, yerr=eotwms,
                             color='Green')
    # plt.show(fig)
    outfile = plots_dir / f'{star.name}_{star.numObs}_obs.png'
    fig.savefig(str(outfile))
    plt.close('all')


def get_weighted_mean(values_array, errs_array, time_slice, col_index):
    """
    Get the weighted mean of a column in an array avoiding NaNs.

    This function is intended to get the weighted mean of the values for either
    a transition or pair from star, from a give time period using the given
    column index.

    It is CRITICAL that you check if the star has observations in the pre- or
    post-fiber change era before calling this function; due to a quirk, a star
    with observation only in the pre-fiber change era will return all of its
    observations if given a timeslice for its post-change observations, so only
    call this after checking a star actually has observations for the era in
    question.

    Parameters
    ----------
    values_array : array-like
        The array from which to get the values (specifically, some array from
        a `varconlib.star.Star` object).
    errs_array : array-like
        An array of the same shape as the array given to `values_array`.
    time_slice : Slice
        A Slice object.
    col_index : int
        The index of the column to get the values from.

    Returns
    -------
    tuple, length-2 of floats
        A tuple containing the weighted mean and error on the weighted mean for
        the given slice and era.

    """

    values, mask = remove_nans(values_array[time_slice, col_index],
                               return_mask=True)
    errs = errs_array[time_slice, col_index][mask]

    try:
        return weighted_mean_and_error(values, errs)
    except ZeroDivisionError:
        return (np.nan, np.nan)


def create_example_plots():
    """Create example plots."""

    pairs_of_interest = ('5571.164Fe1_5577.637Fe1_50',
                         '6123.910Ca1_6138.313Fe1_60',
                         '6138.313Fe1_6139.390Fe1_60')
    # manual_sys_errs = (7.04, 11.75, 3.31)  # In m/s.
    sys_errs = []
    num_pairs = len(pairs_of_interest)

    sys_err_file = vcl.output_dir /\
        'pair_separation_files/pair_excess_scatters.csv'
    with open(sys_err_file, 'r') as f:
        lines = f.readlines()
    for pair_label in pairs_of_interest:
        for line in lines:
            line = line.split(',')
            if line[0] == pair_label:
                sys_errs.append(float(line[1]))

    font = {'family': 'sans-serif',
            'weight': 'normal',
            'size': 14}
    matplotlib.rc('font', **font)

    RA = star_data['RA'][:-1]
    DEC = star_data['DEC'][:-1]
    dist = star_data['distance (pc)'][:-1]

    coordinates = SkyCoord(ra=RA, dec=DEC, distance=dist,
                           unit=(units.hourangle, units.degree,
                                 units.pc))

    distances = [np.sqrt(c.galactocentric.x**2 + c.galactocentric.y**2 +
                         c.galactocentric.z**2).value
                 for c in coordinates]
    # Add Sun's galactocentric distance at the end manually.
    distances.append(8300)

    # Galactocentric plot
    fig = plt.figure(figsize=(8, 10), constrained_layout=False)
    gs = fig.add_gridspec(nrows=len(pairs_of_interest), ncols=1, hspace=0.04,
                          left=0.11, right=0.96, bottom=0.06, top=0.99)

    axes_dict = {}
    for i in range(num_pairs):
        axes_dict[f'ax{i}'] = fig.add_subplot(gs[i, 0])

    for i in range(num_pairs - 1):
        axes_dict[f'ax{i}'].tick_params(which='both',
                                        labelbottom=False, bottom=False)
    axes_dict[f'ax{num_pairs - 1}'].set_xlabel(
        'Galactocentric distance (pc)')

    plots_dir = Path('/Users/dberke/Pictures/paper_plots_and_tables/plots')
    if not plots_dir.exists():
        os.mkdir(plots_dir)

    for pair_label, ax, err in zip(pairs_of_interest,
                                   axes_dict.values(),
                                   sys_errs):

        data_pre = read_csv_file(pair_label, csv_dir, 'pre')
        data_pre = data_pre.astype(types_dict)
        data_post = read_csv_file(pair_label, csv_dir, 'post')
        data_post = data_post.astype(types_dict)

        ax.set_xlim(left=8245, right=8340)
        ax.set_ylim(bottom=-65, top=65)
        ax.set_ylabel(r'$\Delta v_\mathrm{pair}$ (m/s)')
        ax.yaxis.set_major_locator(ticker.AutoLocator())
        ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
        ax.xaxis.set_major_locator(ticker.AutoLocator())
        ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
        # ax.yaxis.grid(which='major', color='Gray',
        #               linestyle='-', alpha=0.65)
        # ax.yaxis.grid(which='minor', color='Gray',
        #               linestyle=':', alpha=0.5)
        # ax.xaxis.grid(which='major', color='Gray',
        #               linestyle='-', alpha=0.65)
        # ax.xaxis.grid(which='minor', color='Gray',
        #               linestyle=':', alpha=0.5)
        ax.axhline(0, color='Black', linestyle='--')

        # diffs_pre = ma.masked_invalid(data_pre['delta(v)_pair (m/s)'])
        # errs_pre = ma.masked_invalid(data_pre['err_stat_pair (m/s)'])

        # diffs_post = ma.masked_invalid(data_post['delta(v)_pair (m/s)'])
        # errs_post = ma.masked_invalid(data_post['err_stat_pair (m/s)'])

        # diffs = pd.concat([data_pre['delta(v)_pair (m/s)'],
        #                   data_post['delta(v)_pair (m/s)']])
        # errs = pd.concat([data_pre['err_stat_pair (m/s)'],
        #                  data_post['err_stat_pair (m/s)']])

        # print(data_pre['err_stat_pair (m/s)'])

        # TODO: Figure out how to combine the pre- and post- data.

        ax.errorbar(distances,
                    data_pre['delta(v)_pair (m/s)'],
                    yerr=np.sqrt(data_pre['err_stat_pair (m/s)']**2 + err**2),
                    color='Black', markerfacecolor='DodgerBlue',
                    ecolor='DodgerBlue',
                    markeredgecolor='Black', marker='o',
                    linestyle='',
                    label=format_pair_label(pair_label, use_latex=True) +
                    f', Sys. Err: {err:.3f} (m/s)')
        # ax.annotate(format_pair_label(pair_label),
        #             (0.01, 0.11),
        #             xycoords='axes fraction',
        #             verticalalignment='top')
        ax.legend()

    outfile = plots_dir / 'Galactocentric_distance.png'
    fig.savefig(str(outfile))

    # Parameter plots

    for parameter in tqdm(('temperature', 'metallicity', 'logg')):
        fig = plt.figure(figsize=(8, 10), constrained_layout=False)
        gs = fig.add_gridspec(nrows=len(pairs_of_interest),
                              ncols=1, hspace=0.04,
                              left=0.11, right=0.96,
                              bottom=0.06, top=0.99)

        axes_dict = {}
        for i in range(num_pairs):
            axes_dict[f'ax{i}'] = fig.add_subplot(gs[i, 0])

        for i in range(num_pairs - 1):
            axes_dict[f'ax{i}'].tick_params(which='both',
                                            labelbottom=False, bottom=False)
        axes_dict[f'ax{num_pairs - 1}'].set_xlabel(
            plot_axis_labels[parameter])

        for pair_label, ax, err in zip(pairs_of_interest,
                                       axes_dict.values(),
                                       sys_errs):
            data_pre = read_csv_file(pair_label, csv_dir, 'pre')
            data_pre = data_pre.astype(types_dict)
            data_post = read_csv_file(pair_label, csv_dir, 'post')
            data_post = data_post.astype(types_dict)

            # ax.set_xlim(left=8245, right=8340)
            ax.set_ylim(bottom=-65, top=65)
            ax.set_ylabel(r'$\Delta v_\mathrm{pair}$ (m/s)')
            ax.yaxis.set_major_locator(ticker.AutoLocator())
            ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
            ax.xaxis.set_major_locator(ticker.AutoLocator())
            ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
            # ax.yaxis.grid(which='major', color='Gray',
            #               linestyle='-', alpha=0.65)
            # ax.yaxis.grid(which='minor', color='Gray',
            #               linestyle=':', alpha=0.5)
            # ax.xaxis.grid(which='major', color='Gray',
            #               linestyle='-', alpha=0.65)
            # ax.xaxis.grid(which='minor', color='Gray',
            #               linestyle=':', alpha=0.5)
            ax.axhline(0, color='Black', linestyle='--')
            y_errs = np.sqrt(data_pre['err_stat_pair (m/s)'] ** 2 +
                             err ** 2)

            vprint(f'Chi^2_nu for {parameter}, {pair_label} is')
            vprint(calc_chi_squared_nu(data_pre['delta(v)_pair (m/s)'],
                                       y_errs, 1))

            ax.errorbar(star_data[params_dict[parameter]],
                        data_pre['delta(v)_pair (m/s)'],
                        yerr=y_errs,
                        color='Black', markerfacecolor='DodgerBlue',
                        ecolor='DodgerBlue',
                        markeredgecolor='Black', marker='o',
                        linestyle='',
                        label=format_pair_label(pair_label, use_latex=True) +
                        f', Sys. Err: {err:.3f} (m/s)')
            # ax.annotate(format_pair_label(pair_label),
            #             (0.01, 0.11),
            #             xycoords='axes fraction',
            #             verticalalignment='top')
            ax.legend()

        outfile = plots_dir / f'{parameter}.png'
        fig.savefig(str(outfile))
        plt.close('all')


def format_pair_label(pair_label, use_latex=False):
    """Format a pair label for prettier printing.

    Parameters
    ----------
    pair_label : str
        A pair label of the form '6138.313Fe1_6139.390Fe1_60'.
    use_latex : bool, Default : *False*
        Whether to return a string with LaTeX code to add a lambda symbol in
        front of the wavelength or not.

    Returns
    -------
    str
        A formatted string of the form 'Fe I 6138.313, Fe I 6139.390', if
        use_latex=False.

    """

    transition1, transition2, _ = pair_label.split('_')
    wavelength1 = transition1[:8]
    ion1 = transition1[8:]
    element1 = ion1[:-1]
    state1 = ion1[-1]
    wavelength2 = transition2[:8]
    ion2 = transition2[8:]
    element2 = ion2[:-1]
    state2 = ion2[-1]

    if use_latex:
        return f'{element1} {roman_numerals[int(state1)]}' +\
               rf' $\lambda{wavelength1}$, ' +\
               f'{element2} {roman_numerals[int(state2)]}' +\
               rf' $\lambda{wavelength2}$'
    else:
        return f'{element1} {roman_numerals[int(state1)]}' +\
               f' {wavelength1}, ' +\
               f'{element2} {roman_numerals[int(state2)]}' +\
               f' {wavelength2}'


def get_star(star_name):
    """
    Return a `varconlib.star.Star` object using this name.

    Parameters
    ----------
    star_name : str
        The name of a star corresponding the name of a directory for that star
        in `varconlib.output_dir`.

    Returns
    -------
    `varconlib.star.Star`
        A `Star` object made by using the name given and the default values.

    """

    return Star(star_name, vcl.output_dir / star_name)


# Main script body.
parser = argparse.ArgumentParser(description="Plot results for each pair"
                                 " of transitions for various parameters.")

parameter_options = parser.add_argument_group(
    title="Plot parameter options",
    description="Select what parameters to plot the pairs-wise velocity"
    " separations by.")

parser.add_argument('star', nargs='*', default=None, const=None, type=str,
                    help='The name of a single, specific star to make a plot'
                    ' from. If not given will default to using all stars.')

parser.add_argument('-m', '--model', type=str, action='store',
                    help='The name of a model to test against.')
parser.add_argument('--sigma', type=float, action='store',
                    help='The number of sigma at which to trim outliers.')

parser.add_argument('--heliocentric-distance', action='store_true',
                    help='Plot as a function of distance from the Sun.')
parser.add_argument('--galactocentric-distance', action='store_true',
                    help='Plot as a function of distance from galactic center.')
parser.add_argument('--sigma-sys-vs-pair-separations', action='store_true',
                    help='Plot the sigma_sys for each pair as a function'
                    ' of its weighted-mean separation.')
parser.add_argument('--model-diff-vs-pair-separations', action='store_true',
                    help='Plot the model difference for each pair as a function'
                    ' of it weighted-mean separation.')
parser.add_argument('--plot-duplicate-pairs', action='store_true',
                    help='Plot differences in measured and model-corrected'
                    ' pair separations for duplicate pairs for a given star.')
parser.add_argument('--plot-depth-differences', action='store_true',
                    help='Create a plot of systematic differences as a function'
                    ' of pair depth differences.')

parameter_options.add_argument('-T', '--temperature',
                               dest='parameters_to_plot',
                               action='append_const',
                               const='temperature',
                               help="Plot as a function of stellar"
                               "temperature.")
parameter_options.add_argument('-M', '--metallicity',
                               dest='parameters_to_plot',
                               action='append_const',
                               const='metallicity',
                               help="Plot as a function of stellar"
                               " metallicity.")
parameter_options.add_argument('-G', '--logg',
                               dest='parameters_to_plot',
                               action='append_const',
                               const='logg',
                               help="Plot as a function of stellar"
                               " surface gravity.")

parser.add_argument('--pair-label', action='store', type=str,
                    help='The full label of a specific pair to make a plot for'
                    " a single star of that pair's stability over time.")
parser.add_argument('--example-plot', action='store_true',
                    help='Plot an example of some good pairs.')

parser.add_argument('-v', '--verbose', action='store_true',
                    help="Print more output about what's happening.")

args = parser.parse_args()

# Define vprint to only print when the verbose flag is given.
vprint = vcl.verbose_print(args.verbose)

# Get the star from the name.
if len(args.star) == 1:
    star = get_star(args.star[0])

csv_dir = vcl.output_dir / 'pair_separation_files'

star_properties_file = csv_dir / 'star_properties.csv'

star_data = pd.read_csv(star_properties_file)

# Import the list of pairs to use.
with open(vcl.final_pair_selection_file, 'r+b') as f:
    pairs_list = pickle.load(f)

pairs_dict = {}
for pair in tqdm(pairs_list):
    for order_num in pair.ordersToMeasureIn:
        pair_label = "_".join([pair.label, str(order_num)])
        pairs_dict[pair_label] = pair

if args.parameters_to_plot:
    for parameter in tqdm(args.parameters_to_plot):
        vprint(f'Plotting vs. {parameter}')
        plot_vs(parameter)

if args.heliocentric_distance:
    plot_distance()

if args.galactocentric_distance:
    plot_galactic_distance()

if args.example_plot:
    create_example_plots()

if args.star is not None and args.pair_label:
    plot_pair_stability(star, args.pair_label)

if args.star is not None and args.sigma_sys_vs_pair_separations:
    plot_sigma_sys_vs_pair_separation(star)

# Create plots as a function of pair separation distance.
if args.star is not None and args.model is not None and args.sigma is not None\
        and args.model_diff_vs_pair_separations:
    if len(args.star) == 1:
        plot_model_diff_vs_pair_separation(star, args.model.replace('-', '_'),
                                           n_sigma=args.sigma)
    elif len(args.star) > 1:
        results_file = vcl.output_dir /\
            f'pair_separation_files/star_pair_separation_{args.sigma}sigma.csv'
        results = []
        for star in tqdm(args.star):
            results.append(plot_model_diff_vs_pair_separation(
                get_star(star), args.model.replace('-', '_'),
                n_sigma=args.sigma))
        with open(results_file, 'w', newline='') as f:
            datawriter = csv.writer(f)
            header = ('#star_name',
                      '#obs_pre', 'chisq_pre',
                      'w_mean_pre', 'eotwm_pre',
                      '#obs_post', 'chisq_post',
                      'w_mean_post', 'eotwm_post')
            datawriter.writerow(header)
            for row in results:
                datawriter.writerow(row)

if args.star is not None and args.plot_duplicate_pairs:
    if len(args.star) == 1:
        plot_duplicate_pairs(star)
    elif len(args.star) > 1:
        for star in args.star:
            plot_duplicate_pairs(get_star(star))

if args.star is not None and args.plot_depth_differences:
    if len(args.star) == 1:
        plot_pair_depth_differences(star)
    if len(args.star) > 1:
        for star_name in args.star:
            plot_pair_depth_differences(get_star(star_name))
