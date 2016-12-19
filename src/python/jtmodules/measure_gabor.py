# Copyright 2016 Markus D. Herrmann, University of Zurich
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
'''Jterator module for measuring Gabor texture features.'''
import collections
import jtlib.features

VERSION = '0.1.0'

Output = collections.namedtuple('Output', ['measurements', 'figure'])


def main(extract_objects, assign_objects, intensity_image,
        aggregate=False, plot=False):
    '''Measures texture features for objects in `extract_objects` based
    on grayscale values in `intensity_image` and assign them to `assign_objects`.

    Parameters
    ----------
    extract_objects: numpy.ndarray[int32]
        label image with objects for which features should be extracted
    assign_objects: numpy.ndarray[int32]
        label image with objects to which extracted features should be
        assigned; if different from `label_image` aggregates are computed
    intensity_image: numpy.ndarray[unit8 or uint16]
        grayscale image from which features should be extracted
    aggregate: bool, optional
        whether features extracted for objects in `extract_objects` should be
        aggregated for objects in `assign_objects` (default: ``False``)
    plot: bool, optional
        whether a plot should be generated (default: ``False``)

    Returns
    -------
    jtmodules.maeasure_gabor.Output

    See Also
    --------
    :class:`jtlib.features.Gabor`
    '''
    f = jtlib.features.Gabor(
        label_image=extract_objects, ref_label_image=assign_objects,
        intensity_image=intensity_image
    )

    if aggregate:
        measurements = [f.extract_aggregate()]
    else:
        measurements = [f.extract()]

    if plot:
        figure = f.plot()
    else:
        figure = str()

    return Output(measurements, figure)
