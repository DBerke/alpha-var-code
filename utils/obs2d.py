#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 13 11:54:34 2018

@author: dberke

This library contains functions to deal with opening 2D HARPS extracted e2ds
files.
"""

import configparser
import numpy as np
import unyt as u
import varconlib as vcl
from tqdm import tqdm, trange
from astropy.io import fits
from pathlib import Path
from conversions import air2vacESO

config_file = Path('/Users/dberke/code/config/variables.cfg')
config = configparser.ConfigParser(interpolation=configparser.
                                   ExtendedInterpolation())
config.read(config_file)


class HARPSFile2D(object):
    """Class to contain data from a HARPS 2D extracted spectrum file.

    """

    def __init__(self, FITSfile):
        if type(FITSfile) is str:
            self._filename = Path(FITSfile)
        else:
            self._filename = FITSfile
        with fits.open(self._filename) as hdulist:
            self._header = hdulist[0].header
            self._rawData = hdulist[0].data

    def __repr__(self):
        return "{}('{}')".format(self.__class__.__name__, self._filename)

    def __str__(self):
        return '{}, {}'.format(self._header['OBJECT'], self._filename.stem)

    def getHeaderCard(self, flag):
        """
        Get the value of the header card with the given flag.

        Parameters
        ----------
        flag : str
            The key of of the FITS header to get the value of.

        Returns
        -------
        str
            The value of the FITS header associated with the given key.

        """

        return self._header[flag]

    def plotSelf(self):
        """
        Return a plot of the data.
        """
        # TODO: Implement a plot system.
        pass


class HARPSFile2DScience(HARPSFile2D):
    """Subclass of HARPSFile2D to handle observations specifically.

    """

    def __init__(self, FITSfile, update=False):
        """Parse a given FITS file containing an observation into a usable
        HARPSFile2DScience object.

        Parameters
        ----------
        FITSfile : str or pathlib.Path object
            Represents the location of the file to read. If given as a string
            it will be converted to a Path object internally.

        Optional
        --------
        update : bool, Default : False
            Whether to force writing of the wavelength, flux, and error arrays.
            This process takes some time so normally if the arays are already
            present in the file (from having been opened previously) they will
            simply be read. If the process of creating these arrays is ever
            changed, opening the files with `update` set to *True* will cause
            the arrays to re rewritten using the new code.

        """
        if type(FITSfile) is str:
            self._filename = Path(FITSfile)
        else:
            self._filename = FITSfile
        if update:
            file_open_mode = 'update'
        else:
            file_open_mode = 'append'
        hdulist = fits.open(self._filename, mode=file_open_mode)
        self._header = hdulist[0].header
        self._rawData = hdulist[0].data
        self._wavelengthArray = None  # air wavelengths, not barycentric
        self._vacuumArray = None  # vacuum wavelengths, not barycentric
        self._barycentricArray = None  # vacuum wavelengths, barycentric
        self._rawFluxArray = self._rawData
        self._gainCorrectedFluxArray = None
        self._photonFluxArray = None
        self._errorArray = None
        self._blazeFile = None
        self._BERV = None
        self._radialVelocity = None

        # BERV = Barycentric Earth Radial Velocity
        self._BERV = float(self.getHeaderCard(
                'HIERARCH ESO DRS BERV')) * u.km / u.s
        self._radialVelocity = float(self.getHeaderCard(
                'HIERARCH ESO TEL TARG RADVEL')) * u.km / u.s

        # Since we may not have the blaze files on hand, only try to find
        # them if we really need them, i.e. when opening a file for the
        # first time or when explicitly updating it.
        if (len(hdulist) == 1) or file_open_mode == 'update':
            self._blazeFile = self.getBlazeFile()

        # Try to read the wavelength array, or create it if it doesn't
        # exist.
        err_str = "File opened in 'update' mode but no arrays exist!"
        try:
            self._wavelengthArray = hdulist['WAVE'].data * u.angstrom
        except KeyError:
            if update:
                raise RuntimeError(err_str)
            tqdm.write('Writing new wavelength HDU.')
            self.writeWavelengthHDU(hdulist, verify_action='warn')
        # If we're updating the file, overwrite the existing wavelengths.
        if update:
            tqdm.write('Overwriting wavelength HDU.')
            self.writeWavelengthHDU(hdulist, verify_action='warn')

        # Try to read the flux array, or create it if it doesn't exist.
        try:
            self._photonFluxArray = hdulist['FLUX'].data
        except KeyError:
            if update:
                raise RuntimeError(err_str)
            self.writePhotonFluxHDU(hdulist, verify_action='warn')
            tqdm.write('Writing new photon flux HDU.')
        # If we're updating the file, overwrite the existing fluxes.
        if update:
            tqdm.write('Overwriting photon flux HDU.')
            self.writePhotonFluxHDU(hdulist, verify_action='warn')

        # Try to read the error array, or create it if it doesn't exist.
        try:
            self._errorArray = hdulist['ERR'].data
        except KeyError:
            if update:
                raise RuntimeError(err_str)
            self.writeErrorHDU(hdulist, verify_action='warn')
            tqdm.write('Writing new error HDU.')
        # If we're updating the file, overwrite the existing uncertainties.
        if update:
            tqdm.write('Overwriting error array HDU.')
            self.writeErrorHDU(hdulist, verify_action='warn')
        hdulist.close(output_verify='warn')

    def getBlazeFile(self):
        """Find and return the blaze file associated with this observation.

        Returns
        -------
        obs2d.HARPSFile2D object
            A HARPSFile2D object created from the blaze file associated with
            this observation via its header card.

        """

        blaze_file = self.getHeaderCard('HIERARCH ESO DRS BLAZE FILE')

        file_date = blaze_file[6:16]

        blaze_file_dir = Path(config['PATHS']['blaze_file_dir'])
        blaze_file_path = blaze_file_dir / 'data/reduced/{}'.format(file_date)\
            / blaze_file

        if not blaze_file_path.exists():
            tqdm.write(str(blaze_file_path))
            raise RuntimeError("Blaze file path doesn't exist!")

        return HARPSFile2D(blaze_file_path)

    def getWavelengthArray(self):
        """Construct a wavelength array (in Angstroms) for the observation.

        By default, the wavelength array returned using the coefficients in
        the headers are in air wavelengths, and uncorrected for the Earth's
        barycentric motion.

        Returns
        -------
        NumPy array
            An array of the same shape as the input array specifying the
            wavelength of each pixel (element in the array) in Angstroms.

        Notes
        -----
        The algorithm used is derived from Dumusque 2018 [1]_.

        References
        ----------
        [1] Dumusque, X. "Measuring precise radial velocities on individual
        spectral lines I. Validation of the method and application to mitigate
        stellar activity", Astronomy & Astrophysics, 2018

        """

        source_array = self._rawFluxArray
        wavelength_array = np.zeros(source_array.shape)
        for order in trange(0, 72, total=72, unit='orders'):
            for i in range(0, 4, 1):
                coeff = 'ESO DRS CAL TH COEFF LL{0}'.format((4 * order) + i)
                coeff_val = self._header[coeff]
                for pixel in range(0, 4096):
                    wavelength_array[order, pixel] += coeff_val * (pixel ** i)

        return wavelength_array * u.angstrom

    def getVacuumArray(self):
        """Correct the calculated air wavelength array back into vacuum.

        Returns
        -------
        unyt_array
            The wavelength array for the observation converted into vacuum
            wavelengths using the Edlen 1953 formula used by the HARPS
            pipeline.

        """

        if self._wavelengthArray is None:
            self._wavelengthArray = self.getWavelengthArray()

        vacuumArray = air2vacESO(self._wavelengthArray)

        return vacuumArray

    def getBarycentricArray(self):
        """Correct the vacuum wavelength array by the barycentric Earth radial
        velocity (BERV).

        Returns
        -------
        unyt_array
            The vacuum wavelength array in barycentric coordinates.

        """

        if self._vacuumArray is None:
            self._vacuumArray = self.getVacuumArray()

        barycentricArray = self.shiftWavelengthArray(self._vacuumArray,
                                                     self._BERV)
        return barycentricArray

    def getGainCorrectedFluxArray(self,
                                  gain_card='HIERARCH ESO DRS CCD CONAD'):
        """Get the raw flux array gain-corrected from ADUs to photons.

        Optional
        --------
        gain_card : str
            The name of the header card where the gain information is listed.

        Return
        ------
        NumPy array
            An array with the same shape as self._rawFluxArray, representing
            the number of photons in each pixel of the array.

        """

        # Get the gain from the file header:
        gain = self._header[gain_card]
        assert type(gain) == float, f"Gain value is a {type(gain)}!"

        return self._rawFluxArray * gain

    def getPhotonFluxArray(self):
        """Calibrate the raw flux array using the gain, then correct it using
        the correct blaze file to recover the photoelectron flux.

        Returns
        -------
        NumPy array
            An array created by multiplying the input array by the gain from
            the file header.

        """

        # If the gain-corrected photon flux array doesn't exist yet, create it.
        if self._gainCorrectedFluxArray is None:
            self._gainCorrectedFluxArray = self.getGainCorrectedFluxArray()
        photon_flux_array = self._gainCorrectedFluxArray

        # Blaze-correct the photon flux array:
        if self._blazeFile is None:
            self._blazeFile = self.getBlazeFile()
        photon_flux_array /= self._blazeFile._rawData

        return photon_flux_array

    def getErrorArray(self, verbose=False):
        """Construct an error array based on the reported flux values for the
        observation, then blaze-correct it.

        Parameters
        ----------
        verbose : bool, Default: False
            If *True*, the method will print out how many pixels with negative
            flux were found during the process of constructing the error array
            (with the position of the pixel in the array and its flux) and
            in a summary afterwards state how many were found.

        Returns
        -------
        NumPy array
            An array with the same shape as the input array containing the
            errors, assuming Poisson statistics for the noise. This is simply
            the square root of the flux in each pixel.

        """

        # According to Dumusque 2018 HARPS has a dark-current and read-out
        # noise of 12 photo-electrons.
        dark_noise = 12

        # If the gain-corrected photon flux array doesn't exist yet, create it.
        if self._gainCorrectedFluxArray is None:
            self._gainCorrectedFluxArray = self.getGainCorrectedFluxArray()
        photon_flux_array = self._gainCorrectedFluxArray
        bad_pixels = 0
        error_array = np.ones(photon_flux_array.shape)
        for m in range(photon_flux_array.shape[0]):
            for n in range(photon_flux_array.shape[1]):
                if photon_flux_array[m, n] < 0:
                    if verbose:
                        tqdm.write(photon_flux_array[m, n], m, n)
                    error_array[m, n] = 1e5
                    bad_pixels += 1
                else:
                    # Add the dark noise in quadrature with the photon noise.
                    # Won't affect much unless at low SNR.
                    error_array[m, n] = np.sqrt(photon_flux_array[m, n] +
                                                dark_noise ** 2)
        if verbose:
            tqdm.write('{} pixels with negative flux found.'.
                       format(bad_pixels))

        # Correct the error array by the blaze function:
        if self._blazeFile is None:
            self._blazeFile = self.getBlazeFile()
        error_array /= self._blazeFile._rawData

        return error_array

    def writeWavelengthHDU(self, hdulist, verify_action='exception'):
        """Write out a wavelength array HDU to the currently opened file.

        Parameters
        ----------
        hdulist : an astropy HDUList object
            The HDU list of the file to modify.

        verify_action : str
            One of either ``'exception'``, ``'ignore'``, ``'fix'``,
            ``'silentfix'``, or ``'warn'``.
            <http://docs.astropy.org/en/stable/io/fits/api/verification.html
            #verify>`_
            The default value is to print a warning upon encountering a
            violation of any FITS standard.

        """
        # ??? Use the barycentric vacuum array here?
        self._wavelengthArray = self.getWavelengthArray()

        # Create an HDU for the wavelength array.
        wavelength_HDU = fits.ImageHDU(data=self._wavelengthArray,
                                       name='WAVE')

        # Add some cards to its header containing the minimum and maximum
        # wavelengths in each order.
        wavelength_cards = []
        for i in range(0, 72):
            for kind, pos in zip(('min', 'max'), (0, -1)):
                keyword = f'ORD{i}{kind.upper()}'
                value = '{:.3f}'.format(self._wavelengthArray[i, pos])
                comment = '{} wavelength of order {}'.format(kind.capitalize(),
                                                             i)
                wavelength_cards.append((keyword, value, comment))
        wavelength_HDU.header.extend(wavelength_cards)
        try:
            hdulist['WAVE'] = wavelength_HDU
        except KeyError:
            hdulist.append(wavelength_HDU)
        hdulist.flush(output_verify=verify_action, verbose=True)

    def writePhotonFluxHDU(self, hdulist, verify_action='exception'):
        """Write out a photon flux array HDU to the currently opened file.

        Parameters
        ----------
        hdulist : an astropy HDUList object
            The HDU list of the file to modify.

        verify_action : str
            One of either ``'exception'``, ``'ignore'``, ``'fix'``,
            ``'silentfix'``, or ``'warn'``.
            <http://docs.astropy.org/en/stable/io/fits/api/verification.html
            #verify>`_
            The default value is to print a warning upon encountering a
            violation of any FITS standard.

        """

        self._photonFluxArray = self.getPhotonFluxArray()

        # Create an HDU for the photon flux array.
        photon_flux_HDU = fits.ImageHDU(data=self._photonFluxArray,
                                        name='FLUX')
        try:
            hdulist['FLUX'] = photon_flux_HDU
        except KeyError:
            hdulist.append(photon_flux_HDU)
        hdulist.flush(output_verify=verify_action, verbose=True)

    def writeErrorHDU(self, hdulist, verify_action='exception'):
        """Write out an error array HDU to the currently opened file.

        Parameters
        ----------
        hdulist : an astropy HDUList object
            The HDU list of the file to modify.

        verify_action : str
            One of either ``'exception'``, ``'ignore'``, ``'fix'``,
            ``'silentfix'``, or ``'warn'``.
            More information can be found in the Astropy `documentation.
            <http://docs.astropy.org/en/stable/io/fits/api/verification.html
            #verify>`_
            The default value is to print a warning upon encountering a
            violation of any FITS standard.

        """

        self._errorArray = self.getErrorArray()

        # Create an HDU for the error array.
        error_HDU = fits.ImageHDU(data=self._errorArray,
                                  name='ERR')
        try:
            hdulist['ERR'] = error_HDU
        except KeyError:
            hdulist.append(error_HDU)
        hdulist.flush(output_verify=verify_action, verbose=True)

    def shiftWavelengthArray(self, wavelength_array, shift_velocity):
        """Doppler shift a wavelength array by an amount equivalent to a given
        velocity.

        Parameters
        ----------
        wavelength_array : unyt_array
            An array containing wavelengths to be Doppler shifted. Needs units
            of dimension length.

        velocity : unyt_quantity
            A Unyt quantity with dimensions length/time to shift the wavelength
            array by.

        Returns
        -------
        Unyt unyt_array
            An array of the same shape as the given array, Doppler shifted by
            the given radial velocity.

        """

        return vcl.shift_wavelength(wavelength=wavelength_array,
                                    shift_velocity=shift_velocity)

    def findWavelength(self, wavelength=None, closest_only=True):
        """Find which orders contain a given wavelength.

        This function will return the indices of the wavelength orders that
        contain the given wavelength. The result will be a length-1 or -2 tuple
        containing integers in the range [0, 71].

        Parameters
        ----------
        wavelength : unyt_quantity
            The wavelength to find in the wavelength array. This should be a
            unyt_quantity object of length 1.

        closest_only : bool, Default : True
            In a 2D extracted echelle spectrograph like HARPS, a wavelength
            near the ends of an order can appear a second time in an adjacent
            order. By default `findWavelength` will return only the single
            order where the wavelength is closest to the geometric center of
            the CCD, which corresponds to the point where the signal-to-noise
            ratio is highest. Setting this to *False* will allow for the
            possibility of a length-2 tuble being returned containing the
            numbers of both orders a wavelength is found in.

        Returns
        -------
        If closest_only is false: tuple
            A tuple of ints of length 1 or 2, representing the indices of
            the orders in which the input wavelength is found.

        If closest_only is true: int
            An int representing the order in which the wavelength found is
            closest to the geometrical center.

            In both cases the integers returned will be in the range [0, 71].

        """

        wavelength_to_find = wavelength.to(u.angstrom)

        # Create the barycentric wavelength array if it doesn't exist yet.
        if self._barycentricArray is None:
            self._barycentricArray = self.getBarycentricArray()

        # Make sure the wavelength to find is in the array in the first place.
        array_min = self._barycentricArray[0, 0]
        array_max = self._barycentricArray[71, -1]
        assert array_min <= wavelength_to_find <= array_max,\
            "Given wavelength not found within array limits! ({}, {})".format(
                    array_min, array_max)

        # Set up a list to hold the indices of the orders where the wavelength
        # is found.
        orders_wavelength_found_in = []
        for order in range(0, 72):
            order_min = self._wavelengthArray[order, 0]
            order_max = self._wavelengthArray[order, -1]
            if order_min <= wavelength_to_find <= order_max:
                orders_wavelength_found_in.append(order)
        assert len(orders_wavelength_found_in) < 3,\
            "Wavelength found in more than two orders!"

        if closest_only:
            # Only one array: great, return it.
            if len(orders_wavelength_found_in) == 1:
                return orders_wavelength_found_in[0]

            # Found in two arrays: figure out which is closer to the geometric
            # center of the CCD, which conveiently falls around the middle
            # of the 4096-element array.
            elif len(orders_wavelength_found_in == 2):
                order1, order2 = orders_wavelength_found_in
                index1 = vcl.wavelength2index(wavelength_to_find,
                                              self._barycentricArray[order1])
                index2 = vcl.wavelength2index(wavelength_to_find,
                                              self._barycentricArray[order2])
                # Check which index is closest to the pixel in the geometric
                # center of the array, given 0-indexing in Python.
                if abs(index1 - 2047.5) > abs(index2 - 2047.5):
                    return index1
                else:
                    return index2
        else:
            return tuple(orders_wavelength_found_in)

    def plotOrder(self, index, passed_axis, **kwargs):
        """Plot a single order of the data, given its index.

        Parameters
        ----------
        index : int
            An integer in the range [0, 71] representing the index of the
            order to plot.
        passed_axis : a matplotlib Axes instance
            The order specified will be plotted onto this Axes object.
        **kwargs
            Any additional keyword arguments are passed on to matplotlib's
            `plot` function.

        """

        # Check that the index is correct.
        assert 0 <= index <= 71, "Index is not in [0, 71]!"

        ax = passed_axis

        # Plot onto the given axis.
        ax.plot(self._wavelengthArray[index], self._photonFluxArray[index],
                **kwargs)