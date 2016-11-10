# TmServer - TissueMAPS server application.
# Copyright (C) 2016  Markus D. Herrmann, University of Zurich and Robin Hafen
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
"""API view functions for querying resources related to mapobjects
like their polygonal outlines or feature data.
"""
import os.path as p
import json
import logging
import numpy as np
from cStringIO import StringIO
from zipfile import ZipFile

from geoalchemy2.shape import to_shape
import skimage.draw

from flask_jwt import current_identity, jwt_required
from flask import jsonify, request, send_file
from sqlalchemy.sql import text
from werkzeug import secure_filename

import tmlib.models as tm
from tmlib.image import SegmentationImage

from tmserver.api import api
from tmserver.util import decode_query_ids, assert_query_params
from tmserver.error import MalformedRequestError, ResourceNotFoundError


logger = logging.getLogger(__name__)


@api.route('/experiments/<experiment_id>/features', methods=['GET'])
@jwt_required()
@decode_query_ids()
def get_features(experiment_id):
    """
    .. http:get:: /api/experiments/(string:experiment_id)/features

        Get a list of feature objects supported for this experiment.

        **Example response**:

        .. sourcecode:: http

            HTTP/1.1 200 OK
            Content-Type: application/json

            {
                "data": {
                    "Cells": [
                        {
                            "name": "Cell_Area"
                        },
                        ...
                    ],
                    "Nuclei": [
                        ...
                    ],
                    ...
                }
            }

        :reqheader Authorization: JWT token issued by the server
        :statuscode 200: no error
        :statuscode 400: malformed request

    """
    with tm.utils.ExperimentSession(experiment_id) as session:
        features = session.query(tm.Feature).all()
        if not features:
            logger.waring('no features found')
        return jsonify({
            'data': features
        })


@api.route(
    '/experiments/<experiment_id>/mapobjects/<object_name>/segmentations',
    methods=['GET']
)
@jwt_required()
@assert_query_params('plate_name', 'well_name', 'x', 'y', 'zplane', 'tpoint')
@decode_query_ids()
def get_mapobjects_segmentation(experiment_id, object_name):
    """
    .. http:get:: /api/experiments/(string:experiment_id)/mapobjects/(string:mapobject_type)/segmentations

        Get the segmentation image at a specified coordinate.

        :reqheader Authorization: JWT token issued by the server
        :statuscode 200: no error
        :statuscode 400: malformed request

        :query plate_name: the plate's name
        :query well_name: the well's name
        :query x: x-coordinate
        :query y: y-coordinate
        :query zplane: the zplane
        :query tpoint: the time point

    """
    plate_name = request.args.get('plate_name')
    well_name = request.args.get('well_name')
    # TODO: raise MissingGETParameterError when arg missing
    x = request.args.get('x', type=int)
    y = request.args.get('y', type=int)
    zplane = request.args.get('zplane', type=int)
    tpoint = request.args.get('tpoint', type=int)
    label = request.args.get('label', None)
    with tm.utils.MainSession() as session:
        experiment = session.query(tm.ExperimentReference).get(experiment_id)
        experiment_name = experiment.name

    with tm.utils.ExperimentSession(experiment_id) as session:
        site = session.query(tm.Site).\
            join(tm.Well).\
            join(tm.Plate).\
            filter(
                tm.Plate.name == plate_name,
                tm.Well.name == well_name,
                tm.Site.x == x, tm.Site.y == y
            ).\
            one()
        mapobject_type = session.query(tm.MapobjectType).\
            filter_by(name=object_name).\
            one()
        segmentations = session.query(
                tm.MapobjectSegmentation.label,
                tm.MapobjectSegmentation.geom_poly
            ).\
            join(tm.Mapobject).\
            join(tm.MapobjectType).\
            filter(
                tm.MapobjectType.name == object_name,
                tm.MapobjectSegmentation.site_id == site.id,
                tm.MapobjectSegmentation.zplane == zplane,
                tm.MapobjectSegmentation.tpoint == tpoint
            ).\
            all()

        if len(segmentations) == 0:
            raise ResourceNotFoundError('No segmentations found.')
        polygons = dict()
        for seg in segmentations:
            polygons[(tpoint, zplane, seg.label)] = seg.geom_poly

        height = site.height - (
            site.intersection.lower_overhang + site.intersection.upper_overhang
        )
        width = site.width - (
            site.intersection.left_overhang + site.intersection.right_overhang
        )
        y_offset, x_offset = site.offset
        y_offset += site.intersection.lower_overhang
        x_offset += site.intersection.right_overhang

        filename = '%s_%s_x%.3d_y%.3d_z%.3d_t%.3d_%s.png' % (
            experiment_name, site.well.name, site.x, site.y, zplane, tpoint,
            object_name
        )

    img = SegmentationImage.create_from_polygons(
        polygons, y_offset, x_offset, (height, width)
    )
    f = StringIO()
    f.write(img.encode('png'))
    f.seek(0)
    return send_file(
        f,
        attachment_filename=secure_filename(filename),
        mimetype='image/png',
        as_attachment=True
    )


@api.route(
    '/experiments/<experiment_id>/mapobjects/<object_name>/feature-values',
    methods=['GET']
)
@jwt_required()
@decode_query_ids()
def get_feature_values(experiment_id, object_name):
    """
    .. http:get:: /api/experiments/(string:experiment_id)/mapobjects/(string:mapobject_type)/feature-values

        Get all feature values for a given ``mapobject_type`` as a
        zip-compressed CSV file.

        :reqheader Authorization: JWT token issued by the server
        :statuscode 200: no error
        :statuscode 400: malformed request

    """
    with tm.utils.MainSession() as session:
        experiment = session.query(tm.ExperimentReference).get(experiment_id)
        experiment_name = experiment.name

    with tm.utils.ExperimentSession(experiment_id) as session:
        mapobject_type = session.query(tm.MapobjectType).\
            filter_by(name=object_name).\
            one()
        features = mapobject_type.get_feature_value_matrix()
        metadata = mapobject_type.get_metadata_matrix()

    if features.values.shape[0] != metadata.values.shape[0]:
        raise ValueError(
            'Features and metadata must have same number of "%s" objects'
            % object_name
        )
    if any(features.index.values != metadata.index.values):
        raise ValueError(
            'Features and metadata must have the same index.'
        )
    basename = secure_filename(
        '%s_%s_features' % (experiment_name, object_name)
    )
    data_filename = '%s_data.csv' % basename
    metadata_filename = '%s_metadata.csv' % basename
    f = StringIO()
    with ZipFile(f, 'w') as zf:
        zf.writestr(
            data_filename,
            features.to_csv(None, encoding='utf-8', index=False)
        )
        zf.writestr(
            metadata_filename,
            metadata.to_csv(None, encoding='utf-8', index=False)
        )
    f.seek(0)
    # TODO: These files may become very big, we may need to use a generator to
    # stream the file: http://flask.pocoo.org/docs/0.11/patterns/streaming
    # On the client side the streaming requests can be handled by an iterator:
    # http://docs.python-requests.org/en/master/user/advanced/#streaming-requests
    return send_file(
        f,
        attachment_filename='%s.zip' % basename,
        mimetype='application/octet-stream',
        as_attachment=True
    )
