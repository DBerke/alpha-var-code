#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 13 12:00:40 2018

@author: dberke

This library contains functions used for converting wavelengths between vacuum
and air.
"""

import numpy as np
import unyt as u
from tqdm import tqdm, trange


def air_indexEdlen53(l, t=15., p=760.):
    """Return the index of refraction of air at given temperature, pressure,
    and wavelength in Angstroms.


    The formula is from Edlen 1953, provided directly by ESO.

    Parameters
    ----------
    l : float
        Vacuum wavelength in Angstroms
    t : float
        Temperature in °C. (Don't actually change this from the default!)
    p : float
        Pressure in mmHg. (Don't actually change this from the default!)

    Returns
    -------
    float
        The index of refraction for air at the given parameters.

    """

    n = 1e-6 * p * (1 + (1.049-0.0157*t)*1e-6*p) / 720.883 / (1 + 0.003661*t)\
        * (64.328 + 29498.1/(146-(1e4/l)**2) + 255.4/(41-(1e4/l)**2))
    n = n + 1
    return n


def vac2airESO(ll):
    """Return an air wavelength from a vacuum wavelength using the formula from
    Edlen 1953.

    This is the function used in the ESO archive, according to the code
    provided by the archival team. It *only* work with units in *Angstroms*.

    Parameters
    ----------
    ll : float or `unyt.unyt_quantity` or `numpy.ndarray` or `unyt.unyt_array`
        Air wavelength to convert. Needs to be in Angstroms if given as a float
        or array.

    Returns
    -------
    float or `unyt.unyt_quantity`
        The wavelength in air.

    """

    if isinstance(ll, (u.array.unyt_quantity, u.array.unyt_array)):
        original_units = ll.units
        ll.convert_to_units(u.angstrom)
        ll = ll.value
    elif isinstance(ll, (float, np.ndarray)):
        original_units = 1

    llair = ll/air_indexEdlen53(ll)
    return llair * original_units


def air2vacESO(air_wavelengths_array, verbose=False):
    """Take an array of air wavelengths and return an array of vacuum
    wavelengths in the same units.

    Parameters
    ----------
    air_arr : `unyt.unyt_array`
        A list of wavelengths in air, with dimensions length. Will be converted
        to Angstroms internally.


    Optional
    --------
    verbose : bool, Default : False
        If *True*, will print out additional information while running.

    Returns
    -------
    `unyt.unyt_array`
        A unyt_array of wavelengths in vacuum, in the original units.

    """

    reshape = False
    original_units = air_wavelengths_array.units
    if air_wavelengths_array.ndim == 2:
        # We need to flatten the array to 1-D, then reshape it afterwards.
        reshape = True
        original_shape = air_wavelengths_array.shape
        air_wavelengths_array = air_wavelengths_array.flatten()

    air_wavelengths_array.convert_to_units(u.angstrom)

    tolerance = 2e-12
    num_iter = 100

    vacuum_wavelengths_list = []

    if verbose:
        tqdm.write('Converting air wavelengths to vacuum using Edlen 1953.')
    for i in trange(0, len(air_wavelengths_array)):
        new_wavelength = air_wavelengths_array[i].value
        old_wavelength = 0.
        iterations = 0
        past_iterations = [new_wavelength]
        while abs(old_wavelength - new_wavelength) > tolerance:
            old_wavelength = new_wavelength
            n_refraction = air_indexEdlen53(new_wavelength)
            new_wavelength = air_wavelengths_array[i].value * n_refraction
            iterations += 1
            past_iterations.append(new_wavelength)
            if iterations > num_iter:
                print(past_iterations)
                raise RuntimeError('Max number of iterations exceeded!')

        vacuum_wavelengths_list.append(new_wavelength)
    vacuum_array = u.unyt_array(vacuum_wavelengths_list, u.angstrom)

    if reshape:
        # Reshape the array back to its original shape.
        return vacuum_array.reshape(original_shape).to(original_units)
    else:
        return vacuum_array.to(original_units)


def vac2airMorton00(wl_vac):
    """Take an input vacuum wavelength in Angstroms and return the air
    wavelength.

    Formula taken from
    https://www.astro.uu.se/valdwiki/Air-to-vacuum%20conversion
    from Morton (2000, ApJ. Suppl., 130, 403) (IAU standard)
    """
    s = 1e4 / wl_vac
    n = 1 + 0.0000834254 + (0.02406147 / (130 - s**2)) +\
        (0.00015998 / (38.9 - s**2))
    return wl_vac / n


def air2vacMortonIAU(wl_air):
    """Take an input air wavelength in Angstroms and return the vacuum
    wavelength.

    Formula taken from
    https://www.astro.uu.se/valdwiki/Air-to-vacuum%20conversion
    """
    s = 1e4 / wl_air
    n = 1 + 0.00008336624212083 + (0.02408926869968 / (130.1065924522 - s**2))\
        + (0.0001599740894897 / (38.92568793293 - s**2))
    return wl_air * n
