# -*- coding: utf-8 -*-
import json
import requests
import base64
import urllib
from config import *


TYPE_MULTILANG_CSV = 'multilangCsv'


class SmartcatException(Exception):
    def __init__(self, message, code=None):
        super(SmartcatException, self).__init__(message)
        self.code = code


def api_call(method, request_method='get', data=None):
    """Call Smartcat API method

    :returns :class:`Response <Response>` object
    :param str method: API method
    :param str request_method: (optional) get (default) or post
    :param dict data: (optional) POST data
    """

    token = (SMARTCAT_API_USERNAME + ':' + SMARTCAT_API_PASSWORD).encode('ascii')
    auth = 'Basic {0}'.format(base64.b64encode(token).decode())
    headers = {'Accept': 'application/json', 'Authorization': auth}
    url = '{0}/{1}'.format(SMARTCAT_API_BASE_URL, method)
    if request_method == 'post':
        # params get into url here
        if len(data):
            url = '{0}?{1}'.format(url, urllib.parse.urlencode(data))
        return requests.post(url, data=data, headers=headers)
    else:
        return requests.get(url, headers=headers)


def project_stats(project_id=None):
    """Project stats: name, dates, document ids/names etc

    :returns dict
    :param str project_id: (optional)
    :raises :class:`SmartcatException`
    """
    if project_id is None:
        project_id = SMARTCAT_PROJECT_ID
    method = 'v1/project/{0}'.format(project_id)
    response = api_call(method)
    if response.status_code != 200:
        raise SmartcatException('Invalid request status code {0} when calling {1}'.format(
            response.status_code, method), code=response.status_code)

    return json.loads(response.content.decode('utf-8'))


def export_request(document_ids, document_type=TYPE_MULTILANG_CSV):
    """Request document(s) export

    :returns str task ID which later can be checked with export()
    :param list document_ids:
    :param str document_type: (default: TYPE_MULTILANG_CSV)
    """
    method = 'v1/document/export'
    response = api_call(method, 'post',
                        {'documentIds': document_ids, 'type': document_type})
    if response.status_code != 200:
        raise SmartcatException('Invalid request status code {0} when calling {1}'.format(
            response.status_code, method), code=response.status_code)

    data = json.loads(response.content.decode('utf-8'))
    return data['id']


def export(task_id):
    """Export the document

    :returns str document content
    :param list task_id: Task ID obtained with export_request()
    :raises :class:`SmartcatException` on invalid response
    """
    method = 'v1/document/export/{0}'.format(task_id)
    response = api_call(method)
    if response.status_code != 200:
        raise SmartcatException('Invalid request status code {0} when calling {1}'.format(
            response.status_code, method), code=response.status_code)

    return response.content.decode('utf-8')
