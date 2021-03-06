#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 25 13:52:11 2019

@author: dberke

The TransitionPair class contains information about a single pair of atomic
transitions.
"""

import unyt as u

from varconlib.exceptions import SameWavelengthsError
from varconlib.miscellaneous import wavelength2velocity as wave2vel


class TransitionPair(object):
    """Holds information relating to a single pair of transition lines, in the
    form of two Transition objects.

    Attributes
    ----------
    velocitySeparation : `unyt.unyt_quantity` with dimensions distance / dimte
        The nominal velocity separation between the wavelengths of the two
        transitions in this pair.
    label : str
        A string uniquely identifying the transition pair, in a human-readable
        manner.
    blendTuple : len-2 tuple of ints
        A tuple containing two integers, representing the blendedness of each
        individual transition as manifested in a solar spectrum.

    """

    def __init__(self, transition1, transition2):
        """Create an instance of TransitionPair.

        Parameters
        ----------
        transition1, transition2: `transition_line.Transition` objects
        The transitions should be two `Transition` objects, each representing a
        single atomic transition.

        """

        # Note that comparison of transitions compares their wavelength, not
        # their energy. So the "lower energy transition" is the one with the
        # longer wavelength.
        if transition1 > transition2:
            self._lowerEnergyTransition = transition1
            self._higherEnergyTransition = transition2
        elif transition1 < transition2:
            self._lowerEnergyTransition = transition2
            self._higherEnergyTransition = transition1
        else:
            msg = 'Tried to make pair with two transitions of same wavelength!'
            raise SameWavelengthsError(msg)

        # This attribute records which HARPS order(s) to measure a pair's
        # separation in, and is modified by other code for individual pairs.
        self.ordersToMeasureIn = None

    @property
    def velocitySeparation(self):
        if not hasattr(self, '_velocitySeparation'):
            self._velocitySeparation = wave2vel(
                    self._higherEnergyTransition.wavelength,
                    self._lowerEnergyTransition.wavelength)
        return self._velocitySeparation

    @property
    def label(self):
        if not hasattr(self, '_label'):
            self._label = '_'.join([self._higherEnergyTransition.label,
                                    self._lowerEnergyTransition.label])
        return self._label

    @property
    def blendTuple(self):
        if not hasattr(self, '_blendTuple'):
            try:
                self._blendTuple = tuple(sorted([self._higherEnergyTransition.
                                         blendedness,
                                         self._lowerEnergyTransition.
                                         blendedness]))
            except AttributeError:
                raise AttributeError
        return self._blendTuple

    def __iter__(self):
        return iter([self._higherEnergyTransition,
                     self._lowerEnergyTransition])

    def __repr__(self):
        return '{}({}, {})'.format(self.__class__.__name__,
                                   self._higherEnergyTransition,
                                   self._lowerEnergyTransition)

    def __str__(self):
        return 'Pair: {} {} {:.3f}, '.format(
                self._higherEnergyTransition.atomicSymbol,
                self._higherEnergyTransition.ionizationState,
                self._higherEnergyTransition.wavelength.to(u.angstrom)) +\
                '{} {} {:.3f}'.format(
                self._lowerEnergyTransition.atomicSymbol,
                self._lowerEnergyTransition.ionizationState,
                self._lowerEnergyTransition.wavelength.to(u.angstrom))

    def __eq__(self, other):
        """Return equal if both higher and lower energy transitions are the
        same.

        """

        if (self._lowerEnergyTransition == other._lowerEnergyTransition)\
           and (self._higherEnergyTransition == other._higherEnergyTransition):
            return True
        else:
            return False

    def __gt__(self, other):
        """Sort first by higher energy, then by lower energy.

        """

        if self == other:
            return False
        elif self._higherEnergyTransition > other._higherEnergyTransition:
            return True
        elif self._higherEnergyTransition == other._higherEnergyTransition:
            if self._lowerEnergyTransition > other._lowerEnergyTransition:
                return True
            else:
                return False
        else:
            return False

    def __lt__(self, other):
        """Sort first by higher energy, then by lower energy.

        """

        if self == other:
            return False
        elif self._higherEnergyTransition < other._higherEnergyTransition:
            return True
        elif self._higherEnergyTransition == other._higherEnergyTransition:
            if self._lowerEnergyTransition < other._lowerEnergyTransition:
                return True
            else:
                return False
        else:
            return False
