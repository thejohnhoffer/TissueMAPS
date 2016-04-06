'''
A `Handle` instance describes a key-value pair which is either passed as
an argument to a Jterator module function or is returned by the function. The
approach can be considered a form of metaprogramming, where the object extends
the code of the actual module function via its properties and methods.
This is used to assert the correct type of arguments and return values and
enables storing data generated by modules to make it accessible outside the
scope of the module or retrieving data from the store when required by modules.
The object's attributes are specified as a mapping in a
`handles` YAML module input/output descriptor file.
'''
import sys
import numpy as np
import pandas as pd
import skimage
import logging
from abc import ABCMeta
from abc import abstractproperty
from abc import abstractmethod

from tmlib.utils import same_docstring_as
from tmlib.utils import assert_type
from tmlib.image_utils import find_border_objects

logger = logging.getLogger(__name__)


class Handle(object):

    '''Abstract base class for a handle.'''

    __metaclass__ = ABCMeta

    @assert_type(name='basestring', help='basestring')
    def __init__(self, name, help):
        '''
        Parameters
        ----------
        name: str
            name of the item, which must either match a parameter of the module
            function in case the item represents an input argument or the key
            of a key-value pair of the function's return value
        help: str
            help message
        '''
        self.name = name
        self.help = help

    @property
    def store(self):
        '''
        Returns
        -------
        dict
            in-memory key-value store
        '''
        return self._store


class InputHandle(Handle):

    '''Abstract base class for a handle whose value is used as an argument for
    a module function.
    '''

    __metaclass__ = ABCMeta

    def __init__(self, name, value, help):
        '''
        Parameters
        ----------
        name: str
            name of the item, which must match a parameter of the module
            function
        value:
            the actual argument of the module function parameter
        help: str
            help message
        '''
        super(InputHandle, self).__init__(name, help)
        self.value = value


class OutputHandle(Handle):

    '''Abstract base class for a handle whose value is returned by a module
    function.
    '''

    __metaclass__ = ABCMeta

    @same_docstring_as(Handle.__init__)
    def __init__(self, name, help):
        super(OutputHandle, self).__init__(name, help)

    @abstractproperty
    def value(self):
        '''value returned by module function'''
        pass


class PipeHandle(Handle):

    '''Abstract base class for a handle whose value can be piped between
    modules, i.e. returned by one module function and potentially passed as
    argument to another.
    '''

    __metaclass__ = ABCMeta

    @assert_type(key='basestring')
    def __init__(self, name, key, help):
        '''
        Parameters
        ----------
        name: str
            name of the item, which must either match a parameter of the module
            function in case the item represents an input argument or the key
            of a key-value pair of the function's return value
        key: str
            unique and hashable identifier; it serves as
            lookup identifier to retrieve the actual value of the item
        help: str
            help message

        '''
        super(PipeHandle, self).__init__(name, help)
        self.key = key

    @abstractproperty
    def value(self):
        '''Data that's returned by module function and possibly passed
        to other module functions.
        '''
        pass


class Image(PipeHandle):

    '''Abstract base class for an image handle.'''

    __metaclass__ = ABCMeta

    @same_docstring_as(PipeHandle.__init__)
    def __init__(self, name, key, help):
        super(Image, self).__init__(name, key, help)

    @abstractproperty
    def value(self):
        '''numpy.ndarray: 2D/3D pixels/voxels array
        '''
        pass


class IntensityImage(Image):

    '''Class for an intensity image handle, where image pixel values encode
    a quantity.
    '''

    def __init__(self, name, key, help=''):
        '''
        Parameters
        ----------
        name: str
            name of the item, which must either match a parameter of the module
            function in case the item represents an input argument or the key
            of a key-value pair of the function's return value
        key: str
            unique and hashable identifier; it serves as
            lookup identifier to retrieve the actual value of the item
        help: str, optional
            help message (default: ``""``)
        '''
        super(Image, self).__init__(name, key, help)

    @property
    def value(self):
        '''
        Returns
        -------
        numpy.ndarray[numpy.uint8 or numpy.uint16]: 2D/3D pixels/voxels array
        '''
        return self._value

    @value.setter
    def value(self, value):
        if not isinstance(value, np.ndarray):
            raise TypeError(
                'Returned value for "%s" must have type numpy.ndarray.'
                % self.name
            )
        if not(value.dtype == np.uint8 or value.dtype == np.uint16):
            raise TypeError(
                'Returned value for "%s" must have data type '
                'uint8 or uint16' % self.name
            )
        self._value = value

    def __str__(self):
        return '<IntensityImage(name=%r, key=%r)>' % (self.name, self.key)


class LabelImage(Image):

    '''Class for a label image handle, where image pixel values encode
    connected components. Each component has a unique one-based identifier
    label and background is zero.
    '''

    @same_docstring_as(IntensityImage.__init__)
    def __init__(self, name, key, help=''):
        super(Image, self).__init__(name, key, help)

    @property
    def value(self):
        '''numpy.ndarray[numpy.int32]: 2D/3D pixels/voxels array'''
        return self._value

    @value.setter
    def value(self, value):
        if not isinstance(value, np.ndarray):
            raise TypeError(
                'Returned value for "%s" must have type numpy.ndarray.'
                % self.name
            )
        if not value.dtype == np.int32:
            raise TypeError(
                'Returned value for "%s" must have data type int32.'
                % self.name
            )
        self._value = value

    def __str__(self):
        return '<LabelImage(name=%r, key=%r)>' % (self.name, self.key)


class BinaryImage(Image):

    '''Class for a binary image handle, where image pixel values encode
    either background or foreground. Background is ``0`` or ``False`` and
    foreground is ``1`` or ``True``. 
    '''

    @same_docstring_as(IntensityImage.__init__)
    def __init__(self, name, key, help=''):
        super(Image, self).__init__(name, key, help)

    @property
    def value(self):
        '''numpy.ndarray[numpy.bool]: 2D/3D pixels/voxels array'''
        return self._value

    @value.setter
    def value(self, value):
        if not isinstance(value, np.ndarray):
            raise TypeError(
                'Returned value for "%s" must have type numpy.ndarray.'
                % self.name
            )
        if value.dtype != np.bool:
            raise TypeError(
                'Returned value for "%s" must have data type bool.'
                % self.name
            )
        self._value = value

    def __str__(self):
        return '<BinaryImage(name=%r, key=%r)>' % (self.name, self.key)


class SegmentedObjects(LabelImage):

    '''Class for a segmented objects handle, which represents a special type of
    label image handle, where pixel values encode segmented objects that should
    ultimately be visualized by `TissueMAPS` and for which features can be
    extracted.
    '''

    @assert_type(key='basestring')
    def __init__(self, name, key, help=''):
        '''
        Parameters
        ----------
        name: str
            name of the item
        key: str
            name that should be assigned to the objects
        '''
        super(SegmentedObjects, self).__init__(name, key, help)
        self._features = list()
        self._attributes = list()

    @property
    def labels(self):
        '''List[int]: unique object identifier labels'''
        return map(int, np.unique(self.value[self.value > 0]))

    def calc_outlines(self, offset_y, offset_x, tolerance=1):
        '''Calculates the global map coordinates for each object outline.

        Parameters
        ----------
        offset_y: int
            vertical offset that needs to be added along the *y* axis
        offset_x: int
            horizontal offset that needs to be added along the *x* axis
        tolerance: int
            accuracy of polygon approximation; the larger the value the less
            accurate the polygon will be approximated, i.e. the less coordinate
            values will be used to describe its contour; if ``0`` the original
            contour is used (default: ``1``)

        Returns
        -------
        Dict[int, pandas.DataFrame[numpy.int64]]
            global *y* and *x* coordinates along the contour of each object,
            indexable by its one-based label
        '''
        logger.debug('calculate outlines for mapobject type "%s"', self.key)

        # Set border pixels to background to find complete contours of
        # objects at the border of the image
        image = self.value.copy()
        image[0, :] = 0
        image[-1, :] = 0
        image[:, 0] = 0
        image[:, -1] = 0

        outlines = dict()
        for label in self.labels:
            # We could do this for all objects at once, but doing it for each
            # object individually ensures that we get the correct number of
            # objects and that coordinates are in the correct order,
            # i.e. sorted according to their label.
            obj_im = image == label
            contours = skimage.measure.find_contours(
                obj_im, 0.5, fully_connected='high'
            )
            if len(contours) > 1:
                # It sometimes happens that more than one outline is
                # identified per object, in particular when the object has
                # "weird" shape, i.e. many small protrusions.
                # NOTE: I've tried the OpenCV function as well. It's faster,
                # but it has even more problems in terms of identifying a
                # single contour for a given object.
                # TODO: Don't simply take the first element, but measure some
                # properties and choose the one that makes the most sense.
                logger.warn(
                    '%d contours identified for object #%d',
                    len(contours), label
                )
            contour = contours[0].astype(np.int64)
            contour = skimage.measure.approximate_polygon(
                contour, tolerance
            ).astype(np.int64)
            outlines[label] = pd.DataFrame({
                'y': -1 * (contour[:, 0] + offset_y),
                'x': contour[:, 1] + offset_x
            })
        return outlines

    @property
    def is_border(self):
        '''pandas.Series[bool]: ``True`` if object lies at the border of
        the image and ``False`` otherwise
        '''
        return pd.Series(
            map(bool, find_border_objects(self.value)),
            name='is_border', index=self.labels
        )

    @property
    def attributes(self):
        '''pandas.DataFrame: attributes for segmented objects
        '''
        if self._attributes:
            return pd.concat(self._attributes, axis=1)
        else:
            return pd.DataFrame()

    def add_attribute(self, attribute):
        '''Adds an additional attribute.

        Parameters
        ----------
        attribute: tmlib.workflow.jterator.handles.Attribute
            attribute for each segmented object

        See also
        --------
        :py:attrbute:`tmlib.jterator.handles.Attribute`
        '''
        if not isinstance(attribute, Attribute):
            raise TypeError(
                'Argument "attribute" must have type '
                'tmlib.workflow.jterator.handles.Attribute.'
            )
        self._attributes.append(attribute.value)

    @property
    def measurements(self):
        '''pandas.DataFrame[numpy.float]: features extracted for
        segmented objects
        '''
        if self._features:
            return pd.concat(self._features, axis=1)
        else:
            return pd.DataFrame()

    def add_measurement(self, measurement):
        '''Adds an additional measurement.

        Parameters
        ----------
        measurement: tmlib.workflow.jterator.handles.Measurement
            measured features for each segmented object

        See also
        --------
        :py:attrbute:`tmlib.jterator.handles.Measurement`
        '''
        if not isinstance(measurement, Measurement):
            raise TypeError(
                'Argument "measurement" must have type '
                'tmlib.workflow.jterator.handles.Measurement.'
            )
        if any(measurement.value.index != np.array(self.labels)):
            raise IndexError(
                'The index of "measurement" must match the object labels.'
            )
        if len(np.unique(measurement.value.columns)) != len(measurement.value.columns):
            raise ValueError(
                'The column names of "measurement" must be unique.'
            )
        self._features.append(measurement.value)

    # TODO: generate label image from outlines, i.e. fill the outline polygon
    # with corresponding color (label)
    # => draw outlines and fill holes ndi.binary_fill_holes()

    def __str__(self):
        return '<SegmentedObjects(name=%r, key=%r)>' % (self.name, self.key)


class Scalar(InputHandle):

    '''Class for a scalar input argument handle.'''

    @assert_type(value={'int', 'float', 'basestring', 'bool'})
    def __init__(self, name, value, options=[], help=''):
        '''
        Parameters
        ----------
        name: str
            name of the item, which must match a parameter of the module
            function
        value: str or int or float or bool
            value of the item, i.e. the actual argument of the function
            parameter
        help: str, optional
            help message (default: ``""``)
        '''
        if options:
            if value is not None:
                if value not in options:
                    raise ValueError(
                            'Argument "value" can be either "%s"'
                            % '" or "'.join(options))
        super(Scalar, self).__init__(name, value, help)
        self.options = options

    def __str__(self):
        return '<Scalar(name=%r)>' % self.name


class Sequence(InputHandle):

    '''Class for a sequence input argument handle.'''

    @assert_type(value={'list'})
    def __init__(self, name, value, help=''):
        '''
        Parameters
        ----------
        name: str
            name of the item, which must match a parameter of the module
            function
        mode: str
            mode of the item, which defines the way it can be handled by the
            program
        value: List[str or int or float]
            value of the item, i.e. the actual argument of the function
            parameter
        help: str, optional
            help message (default: ``""``)
        '''
        for v in value:
            if all([not isinstance(v, t) for t in {int, float, basestring}]):
                raise TypeError(
                    'Elements of argument "value" must have type '
                        'int, float, or str.')
        super(Sequence, self).__init__(name, value, help)

    def __str__(self):
        return '<Sequence(name=%r)>' % self.name


class Plot(InputHandle):

    '''Class for a plot handle that indicates whether the module should
    generate a figure or rather run in headless mode.
    '''

    @assert_type(value='bool')
    def __init__(self, name, value=False, help=''):
        '''
        Parameters
        ----------
        name: str
            name of the item, which must match a parameter of the module
            function
        value: bool, optional
            whether plotting should be activated (default: ``False``)
        help: str, optional
            help message (default: ``""``)
        '''
        super(Plot, self).__init__(name, value, help)

    def __str__(self):
        return (
            '<Plot(name=%r, active=%r)>' % (self.name, self.value)
        )


class Measurement(OutputHandle):

    '''Class for a measurement handle whose value is a two-dimensional labeled
    array with *n* rows and *p* columns of type ``float``, where *n* is the
    number of segmented objects and *p* the number of features that were
    measured for the referenced segmented objects.
    '''

    @assert_type(
        objects_ref='basestring', channel_ref=['basestring', 'types.NoneType']
    )
    def __init__(self, name, objects_ref, channel_ref=None, help=''):
        '''
        Parameters
        ----------
        name: str
            name of the item, which must match a parameter of the module
            function
        objects_ref: str
            reference to the objects for which features were extracted
        channel_ref: str, optional
            reference to the channel from which features were extracted
            (default: ``None``)
        help: str, optional
            help message (default: ``""``)
        '''
        super(Measurement, self).__init__(name, help)
        self.objects_ref = objects_ref
        self.channel_ref = channel_ref

    @property
    def value(self):
        '''pandas.DataFrame[numpy.float]: features extracted for each segmented
        object
        '''
        return self._value

    @value.setter
    def value(self, value):
        if not isinstance(value, pd.DataFrame):
            raise TypeError(
                'Returned value of "%s" must have type pandas.DataFrame.'
                % self.name
            )
        if value.values.dtype != float:
            raise TypeError(
                'Returned value of "%s" must have data type float.'
                % self.name
            )
        self._value = value

    def __str__(self):
        if self.channel_ref is None:
            return (
                '<Measurement(name=%r, objects_ref=%r)>'
                % (self.name, self.objects_ref)
            )
        else:
            return (
                '<Measurement(name=%r, objects_ref=%r, channel_ref=%r)>'
                % (self.name, self.objects_ref, self.channel_ref)
            )


class Attribute(OutputHandle):

    '''Class for an attribute handle whose value is a one-dimensional labeled
    array with arbitrary type that describes a characteristic of
    the referenced segmented objects.
    '''

    @assert_type(objects_ref='basestring')
    def __init__(self, name, objects_ref, help=''):
        '''
        Parameters
        ----------
        name: str
            name of the item, which must match a parameter of the module
            function
        objects_ref: str
            reference to the objects that the attribute characterizes
        help: str, optional
            help message (default: ``""``)
        '''
        super(Attribute, self).__init__(name, help)
        self.objects_ref = objects_ref

    @property
    def value(self):
        '''pandas.Series: characteristic of segmented objects'''
        return self._value

    @value.setter
    def value(self, value):
        if not isinstance(value, pd.Series):
            raise TypeError(
                'Returned value of "%s" must have type pandas.Series.'
                % self.name
            )
        if isinstance(value.name, basestring):
            raise ValueError(
                'The attribute "name" of the returned value of "%s" '
                'must have type basestring.' % self.name
            )
        if not value.name:
            raise ValueError('')
        self._value = value

    def __str__(self):
        return (
            '<Attribute(name=%r, objects_ref=%r)>'
            % (self.name, self.objects_ref)
        )


class Figure(OutputHandle):

    '''Class for a figure handle whose value is a HTML string representing
    a figure created by a module.
    '''

    def __init__(self, name, help=''):
        '''
        Parameters
        ----------
        name: str
            name of the item, which must match a parameter of the module
            function
        key: str
            name that should be given to the objects 
        help: str, optional
            help message (default: ``""``)
        '''
        super(Figure, self).__init__(name, help)

    @property
    def value(self):
        '''str: HTML representation of a figure'''
        return self._value

    @value.setter
    def value(self, value):
        if not isinstance(value, basestring):
            raise TypeError(
                'Returned value of "%s" must have type basestring.'
                % self.name
            )
        # TODO: Additional checks to make sure the string encodes HTML?
        self._value = str(value)

    def __str__(self):
        return '<Figure(name=%r)>' % self.name


def create_handle(type, **kwargs):
    '''Factory function to create an instance of an implementation of the
    :py:class:`tmlib.workflow.jterator.handles.Handle` abstract base class.

    Parameters
    ----------
    type: str
        type of the handle item; must match a name of one of the
        implemented classes in :py:module:`tmlib.workflow.jterator.handles`
    **kwargs: dict
        keyword arguments that are passed to the constructor of the class

    Returns
    -------
    tmlib.jterator.handles.Handle

    Raises
    ------
    AttributeError
        when `type` is not a valid class name
    TypeError
        when an unexpected keyword is passed to the constructor of the class
    '''
    current_module = sys.modules[__name__]
    try:
        class_object = getattr(current_module, type)
    except AttributeError:
        raise AttributeError('Type "%s" is not a valid class name.' % type)
    return class_object(**kwargs)
