import os
import logging
from glob import glob
from .default import DefaultMetadataHandler
from .cellyoyager import CellvoyagerMetadataHandler
from .metamorph import MetamorphMetadataHandler
from ..cluster import ClusterRoutines
from ..writers import ImageMetadataWriter
from ..errors import NotSupportedError
from ..formats import Formats

logger = logging.getLogger(__name__)


class MetadataConverter(ClusterRoutines):

    '''
    Abstract base class for the handling of image metadata.

    It provides methods for conversion of metadata extracted from heterogeneous
    microscope file formats using the
    `Bio-Formats <http://www.openmicroscopy.org/site/products/bio-formats>`_
    library into a custom format. The original metadata has to be available
    in OMEXML format according to the
    `OME schema <http://www.openmicroscopy.org/Schemas/Documentation/Generated/OME-2015-01/ome.html>`_.

    The class further provides methods to complement the automatically
    retrieved metadata by making use of additional microscope-specific metadata
    files and/or user input.

    The metadata corresponding to the final PNG images are stored in a
    separate JSON file.
    '''

    def __init__(self, experiment, prog_name, file_format):
        '''
        Instantiate an instance of class MetadataConverter.

        Parameters
        ----------
        experiment: Experiment
            configured experiment object
        prog_name: str
            name of the corresponding program (command line interface)
        file_format: str
            name of the microscope file format for which additional files
            are provided, e.g. "metamorph"

        Raises
        ------
        NotSupportedError
            when `file_format` is not supported

        See also
        --------
        `tmlib.cfg`_
        '''
        super(MetadataConverter, self).__init__(experiment, prog_name)
        self.experiment = experiment
        self.file_format = file_format
        if self.file_format:
            if self.file_format not in Formats.SUPPORTED_ADDITIONAL_FILES:
                raise NotSupportedError('Additional metadata files are not '
                                        'supported for the provided format')

    @property
    def image_file_format_string(self):
        '''
        Returns
        -------
        image_file_format_string: str
            format string that specifies how the names of the final image PNG
            files should be formatted
        '''
        self._image_file_format_string = self.experiment.cfg.IMAGE_FILE
        return self._image_file_format_string

    def create_job_descriptions(self, **kwargs):
        '''
        Create job descriptions for parallel computing.

        Parameters
        ----------
        **kwargs: dict
            empty - no additional arguments

        Returns
        -------
        Dict[str, List[dict] or dict]
            job descriptions
        '''
        joblist = dict()
        joblist['run'] = list()
        for i, cycle in enumerate(self.cycles):
            joblist['run'].extend([{
                'id': i+1,
                'inputs': {
                    'uploaded_image_files':
                        glob(os.path.join(cycle.image_upload_dir, '*')),
                    'uploaded_additional_files':
                        glob(os.path.join(cycle.additional_upload_dir, '*')),
                    'ome_xml_files':
                        glob(os.path.join(cycle.ome_xml_dir, '*'))
                },
                'outputs': {
                    'metadata_files': [
                        os.path.join(cycle.metadata_dir,
                                     cycle.image_metadata_file)
                    ]
                },
                'cycle': cycle.name
            }])
        return joblist

    def _build_run_command(self, batch):
        job_id = batch['id']
        command = [self.prog_name]
        if self.file_format:
            command.extend(['-f', self.file_format])
        command.append(self.experiment.dir)
        command.extend(['run', '-j', str(job_id)])
        return command

    def run_job(self, batch):
        '''
        Format the OMEXML metadata extracted from image files, complement it
        with metadata retrieved from additional files and/or user input
        and write the formatted metadata to a JSON file.
        '''
        if self.file_format == 'metamorph':
            logger.debug('use "metamorph" reader')
            handler = MetamorphMetadataHandler(
                            batch['inputs']['uploaded_image_files'],
                            batch['inputs']['uploaded_additional_files'],
                            batch['inputs']['ome_xml_files'],
                            batch['cycle'])
        elif self.file_format == 'cellvoyager':
            logger.debug('use "cellvoyager" reader')
            handler = CellvoyagerMetadataHandler(
                            batch['inputs']['uploaded_image_files'],
                            batch['inputs']['uploaded_additional_files'],
                            batch['inputs']['ome_xml_files'],
                            batch['cycle'])
        else:
            logger.debug('use default reader')
            handler = DefaultMetadataHandler(
                            batch['inputs']['uploaded_image_files'],
                            batch['inputs']['uploaded_additional_files'],
                            batch['inputs']['ome_xml_files'],
                            batch['cycle'])
        meta = handler.format_image_metadata()
        meta = handler.add_additional_metadata(meta)
        # TODO: how shall we deal with user input?
        meta = handler.determine_grid_coordinates(meta)
        meta = handler.build_filenames_for_extracted_images(
                    meta, self.image_file_format_string)
        self._write_metadata_to_file(batch['outputs']['metadata_files'], meta)

    @staticmethod
    def _write_metadata_to_file(filenames, metadata):
        with ImageMetadataWriter() as writer:
            f = filenames[0]
            data = [md.serialize() for md in metadata]
            logger.info('write metadata to file: %s' % f)
            writer.write(f, data)

    def collect_job_output(self, batch):
        raise AttributeError('"%s" object doesn\'t have a "collect_job_output"'
                             ' method' % self.__class__.__name__)

    def apply_statistics(self, joblist, wells, sites, channels, output_dir,
                         **kwargs):
        raise AttributeError('"%s" object doesn\'t have a "apply_statistics"'
                             ' method' % self.__class__.__name__)
