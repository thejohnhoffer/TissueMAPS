# TmLibrary - TissueMAPS library for distibuted image analysis routines.
# Copyright (C) 2016-2018 University of Zurich.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
class FileUploadStatus(object):

    '''Upload status of a file.'''

    #: The file is registered, but upload not yet started
    WAITING = 'WAITING'

    #: Upload is ongoing
    UPLOADING = 'UPLOADING'

    #: Upload is complete
    COMPLETE = 'COMPLETE'

    #: Upload has failed
    FAILED = 'FAILED'

