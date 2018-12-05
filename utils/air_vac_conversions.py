#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 13 12:00:40 2018

@author: dberke

This library contains functions used for converting wavelengths between vacuum
and air.
"""
import numpy as np


def air_indexEdlen53(l, t=15., p=760.):
    """Return the index of refraction of air at given temperature, pressure,
    and wavelength in Angstroms.

    l : float
        Vacuum wavelength in Angstroms
    t : float
        Temperature in °C. (Don't actually change this from the default.)
    p : float
        Pressure in mmHg. (Don't actually change this from the default.)

    The formula is from Edlen 1953, provided directly by ESO.

    """

    n = 1e-6 * p * (1 + (1.049-0.0157*t)*1e-6*p) / 720.883 / (1 + 0.003661*t)\
        * (64.328 + 29498.1/(146-(1e4/l)**2) + 255.4/(41-(1e4/l)**2))
    n = n + 1
    return n


def vac2airESO(ll):
    """Return a vacuum wavlength from an air wavelength (A) using Edlen 1953.

    This is the function used in the ESO archive, according to them.

    ll : float
        Air wavelength in Angstroms

    """

    llair = ll/air_indexEdlen53(ll)
    return llair


def air2vacESO(air_arr):
    """Take an array of air wls (A) and return an array of vacuum wls

    Parameters
    ----------
    air_arr: array-like
        A list of wavelengths in air, in Angstroms.

    Returns
    -------
    array
        An array of wavelengths in vacuum, in Angstroms.
    """
    if not type(air_arr) == np.ndarray:
        air_arr = np.array(air_arr)

    tolerance = 1e-12

    vac = []

    for i in range(0, len(air_arr)):
        newwl = air_arr[i]
        oldwl = 0.
        while abs(oldwl - newwl) > tolerance:
            oldwl = newwl
            n = air_indexEdlen53(newwl)
            newwl = air_arr[i] * n

        vac.append(round(newwl, 2))
    vac_arr = np.array(vac)

    return vac_arr


def vac2airMorton00(wl_vac):
    """Take an input vacuum wavelength in Angstroms and return the air
    wavelength.

    Formula taken from 'www.astro.uu.se/valdwiki/Air-to-vacuum%20conversion'
    from Morton (2000, ApJ. Suppl., 130, 403) (IAU standard)
    """
    s = 1e4 / wl_vac
    n = 1 + 0.0000834254 + (0.02406147 / (130 - s**2)) +\
        (0.00015998 / (38.9 - s**2))
    return wl_vac / n


def air2vacMortonIAU(wl_air):
    """Take an input air wavelength in Angstroms and return the vacuum
    wavelength.

    Formula taken from 'www.astro.uu.se/valdwiki/Air-to-vacuum%20conversion'
    """
    s = 1e4 / wl_air
    n = 1 + 0.00008336624212083 + (0.02408926869968 / (130.1065924522 - s**2))\
        + (0.0001599740894897 / (38.92568793293 - s**2))
    return wl_air * n
