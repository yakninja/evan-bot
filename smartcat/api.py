# -*- coding: utf-8 -*-

"""
smartcat.api
~~~~~~~~~~~~

This module contains classes that make http requests to SmartCAT
`API Documentation <https://smartcat.ai/api/methods/>`_

Original project at https://github.com/gilyaev/smartcat-python-sdk

Modified by Andrey Kravchuk https://github.com/yakninja (added account part, some methods etc)

"""

import json
from abc import ABCMeta

import requests


class SmartcatException(Exception):
    def __init__(self, message, code=0):
        super(SmartcatException, self).__init__(message)
        self.code = code
        self.message = message


class SmartCAT(object):
    """SmartCAT API

    Provides functionality for SmartCAT resource management:
        - project
        - document
    Manage Project Resource::

        >>> from smartcat.api import SmartCAT
        >>> api = SmartCAT('username', 'password', SmartCAT.SERVER_EUROPE)
        >>> project_resource = api.project
        <smartcat.api.Project>
        >>> project_model = {
            "name": "Sample Project",
            "sourceLanguage": "en",
            "targetLanguages": ["ru"],
            "assignToVendor": False
        }
        >>>  res = project_resource.create(data=project_model)
        <Response [200]>

    Manage Document Resource::

        >>> from smartcat.api import SmartCAT
        >>> api = SmartCAT('username', 'password', SmartCAT.SERVER_EUROPE)
        >>> document_resource = api.document
        <smartcat.api.Document>
        >>>  res = document_resource.request_export(document_ids=['project1_doc1', 'project1_doc2', 'project2_doc1'])
        <Response [200]>
        >>>  res = document_resource.request_export(document_ids='project1_doc1')
        <Response [200]>
    """

    SERVER_USA = 'https://us.smartcat.ai'
    SERVER_EUROPE = 'https://smartcat.ai'

    def __init__(self, username, password, server_url=SERVER_EUROPE):
        """
        Constructor

        :param username: SmartCAT API username.
        :param password: SmartCAT API password.
        :param server_url (optional): The API server: SmartCAT.SERVER_EUROPE or SmartCAT.SERVER_USA
        """
        self.username = username
        self.password = password
        self.server_url = server_url

        #: :class:`Project <Project>`.
        self._project = None
        self._document = None
        self._account = None
        pass

    @property
    def project(self):
        """Returns instance of class:`Project <smartcat.api.Project>`.

        :return: :class:`Project <smartcat.api.Project>` object
        :rtype: smartcat.api.Project
        """
        if self._project is not None:
            return self._project

        self._project = self._create_api_resource('Project')

        return self._project

    @property
    def document(self):
        """Returns instance of `Document <smartcat.api.Document>`

        :return: :class:`Document <smartcat.api.Document>` object
        :rtype: smartcat.api.Document
        """
        if self._document is not None:
            return self._document

        self._document = self._create_api_resource('Document')
        return self._document

    @property
    def account(self):
        """Returns instance of `Account <smartcat.api.Account>`

        :return: :class:`Account <smartcat.api.Account>` object
        :rtype: smartcat.api.Account
        """
        if self._account is not None:
            return self._account

        self._account = self._create_api_resource('Account')
        return self._account

    def _create_api_resource(self, resource):
        """Creates and returns API resource
        :return: :class:`BaseResource <BaseResource>` object
        :rtype: smartcat.BaseResource
        """
        return globals()[resource](self.username, self.password, self.server_url)


class BaseResource(object):
    __metaclass__ = ABCMeta

    def __init__(self, username, password, server):
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({'Accept': 'application/json'})
        self.server = server

    def send_get_request(self, path, **kwargs):
        url = self.server + path
        return self.session.get(url, **kwargs)

    def send_options_request(self, path, **kwargs):
        url = self.server + path
        return self.session.options(url, **kwargs)

    def send_head_request(self, path, **kwargs):
        url = self.server + path
        return self.session.put(url, **kwargs)

    def send_post_request(self, path, data=None, json=None, **kwargs):
        url = self.server + path
        return self.session.post(url, data=data, json=json, **kwargs)

    def send_put_request(self, path, data=None, **kwargs):
        url = self.server + path
        return self.session.put(url, data=data, **kwargs)

    def send_patch_request(self, path, data=None, **kwargs):
        url = self.server + path
        return self.session.patch(url, data=data, **kwargs)

    def send_delete_request(self, path, **kwargs):
        url = self.server + path
        return self.session.delete(url, **kwargs)


class Project(BaseResource):

    def create(self, data, files=None):
        # type: (dict) -> requests.Response
        """Create a new project

        :param data: The project information.
        :type data: dict
        :param files: (optional) Dictionary of ``'name': file-like-objects`` (or ``{'name': file-tuple}``)
         for multipart encoding upload.
            ``file-tuple`` can be a 2-tuple ``('filename', fileobj)``, 3-tuple ``('filename', fileobj, 'content_type')``
            or a 4-tuple ``('filename', fileobj, 'content_type', custom_headers)``, where ``'content-type'`` is a string
            defining the content type of the given file and ``custom_headers`` a dict-like object containing additional
            headers to add for the file
        """

        if files is None:
            files = {}

        files["model"] = (None, json.dumps(data), 'application/json')

        return self.send_post_request(
            '/api/integration/v1/project/create',
            files=files)

    def update(self, id, data):
        """Update project by id

        :param id: The project identifier.
        :param data: The project information.
        :type data: dict
        :return: :class:`Response <Response>` object
        :rtype: requests.Response
        """
        return self.send_put_request(
            '/api/integration/v1/project/%s' % id,
            json=data)

    def delete(self, id):
        """Delete project

        :param id: The project identifier.
        :return: :class:`Response <Response>` object
        :rtype: requests.Response
        """
        return self.send_delete_request('/api/integration/v1/project/%s' % id)

    def cancel(self, id):
        """Cancel the project

        :param id: The project identifier.
        :return: :class:`Response <Response>` object
        :rtype: requests.Response
        """

        return self.send_post_request(
            '/api/integration/v1/project/cancel',
            params={'projectId': id})

    def restore(self, id):
        """Restore the project

        :param id: The project identifier.
        :return: :class:`Response <Response>` object
        :rtype: requests.Response
        """

        return self.send_post_request(
            '/api/integration/v1/project/restore',
            params={'projectId': id})

    def get(self, id):
        """Get project

        :param id: The project identifier.
        :return: :class:`Response <Response>` object
        :rtype: requests.Response
        """
        return self.send_get_request('/api/integration/v1/project/%s' % id)

    def completed_work_statistics(self, id):
        """Receiving statistics for the completed parts of the project.

        :param id: The project identifier.
        :return: :class:`Response <Response>` object
        :rtype: requests.Response
        """
        return self.send_get_request('/api/integration/v1/project/%s/completedWorkStatistics' % id)

    def get_all(self):
        """Get document list.

        :return: :class:`Response <Response>` object
        :rtype: requests.Response
        """
        return self.send_get_request('/api/integration/v1/project/list')

    def attach_document(self, id, files):
        """Adds document to project.

        :param id: The project identifier.
        :param files: (optional) Dictionary of ``'name': file-like-objects`` (or ``{'name': file-tuple}``)
         for multipart encoding upload.
            ``file-tuple`` can be a 2-tuple ``('filename', fileobj)``, 3-tuple ``('filename', fileobj, 'content_type')``
            or a 4-tuple ``('filename', fileobj, 'content_type', custom_headers)``, where ``'content-type'`` is a string
            defining the content type of the given file and ``custom_headers`` a dict-like object containing additional
            headers to add for the file
        :return: :class:`Response <Response>` object
        :rtype: requests.Response
        """
        params = {'projectId': id}
        return self.send_post_request('/api/integration/v1/project/document', files=files, params=params)

    def add_target_lang(self, id, lang):
        """Add a new target language to the project

        :param id: The project identifier.
        :param lang: Target language code.
        :return: :class:`Response <Response>` object
        :rtype:
        """

        return self.send_post_request(
            '/api/integration/v1/project/language',
            params={'projectId': id, 'targetLanguage': lang})

    def get_document_by_name(self, project_id, document_name):
        """Return document dict by name or id

        :param project_id: The project identifier.
        :param document_name: Document name or id.
        :return dict: If no document with the name was found, return None
        """
        response = self.get(project_id)
        if response.status_code != 200:
            raise SmartcatException(code=response.status_code, message='Invalid response code')

        project_data = json.loads(response.content.decode('utf-8'))
        if not project_data:
            raise SmartcatException(message='Invalid response')

        name = document_name.lower()
        for d in project_data['documents']:
            if d['id'] == name or d['name'].lower() == name:
                return d

        return None


class Document(BaseResource):
    def update(self, document_id, files):
        """Updates document

        :param document_id: The document identifier.
        :param files: (optional) Dictionary of ``'name': file-like-objects`` (or ``{'name': file-tuple}``)
         for multipart encoding upload.
            ``file-tuple`` can be a 2-tuple ``('filename', fileobj)``, 3-tuple ``('filename', fileobj, 'content_type')``
            or a 4-tuple ``('filename', fileobj, 'content_type', custom_headers)``, where ``'content-type'`` is a string
            defining the content type of the given file and ``custom_headers`` a dict-like object containing additional
            headers to add for the file
        :return: :class:`Response <Response>` object
        :rtype: requests.Response

        todo:: implement updateDocumentModel
        """
        return self.send_put_request(
            '/api/integration/v1/document/update',
            files=files,
            params={'documentId': document_id})

    def rename(self, id, name):
        """Renames document

        :param id: The document identifier.
        :param name: New name.
        :return: :class:`Response <Response>` object
        :rtype: requests.Response
        """

        return self.send_put_request(
            '/api/integration/v1/document/rename',
            params={'documentId': id, 'name': name})

    def get_translation_status(self, id):
        """Receive the status of adding document translation.

        :return: :class:`Response <Response>` object
        :rtype: requests.Response
        """
        return self.send_get_request(
            '/api/integration/v1/document/translate/status',
            params={'documentId': id})

    def translate(self, id, files):
        """Translate the selected document using the uploaded translation file.

        note::Available only for updatable file formats (in actual practice,
        these currently include resource files with unique resource IDs)
        This assigns a task to be processed; the translation
        job may not be finished at the time the request is completed.

        :param id: The document identifier.
        :param files: (optional) Dictionary of ``'name': file-like-objects`` (or ``{'name': file-tuple}``)
         for multipart encoding upload.
            ``file-tuple`` can be a 2-tuple ``('filename', fileobj)``, 3-tuple ``('filename', fileobj, 'content_type')``
            or a 4-tuple ``('filename', fileobj, 'content_type', custom_headers)``, where ``'content-type'`` is a string
            defining the content type of the given file and ``custom_headers`` a dict-like object containing additional
            headers to add for the file
        :return: :class:`Response <Response>` object
        :rtype: requests.Response
        """

        return self.send_put_request(
            '/api/integration/v1/document/translate',
            files=files,
            params={'documentId': id})

    def request_export(self, document_ids, target_type='target'):
        """Sends task to export translations

        :param document_ids: The document identifier string or list of the identifier.
        :param target_type: (optional): The translation document type: xliff or target.
        :return: :class:`Response <Response>` object
        :rtype: requests.Response
        """
        if isinstance(document_ids, str):
            document_ids = [document_ids]

        params = {
            'documentIds': '\n'.join(document_ids),
            'type': target_type
        }

        return self.send_post_request('/api/integration/v1/document/export', params=params)

    def download_export_result(self, task_id):
        """Download the results of export

        :param task_id: The export task identifier
        """
        return self.send_get_request('/api/integration/v1/document/export/%s' % task_id, stream=True)

    def assign(self, document_id, stage_number, executive_user_id):
        params = {
            'documentId': document_id,
            'stageNumber': stage_number,
        }
        data = {
            "executives": [
                {
                    "id": executive_user_id,
                    "wordsCount": 0
                }
            ],
            "minWordsCountForExecutive": 0,
            "assignmentMode": "distributeAmongAll"
        }
        return self.send_post_request('/api/integration/v1/document/assign', params=params, json=data)

    def unassign(self, document_id, stage_number, executive_user_id):
        params = {
            'documentId': document_id,
            'stageNumber': stage_number,
        }
        return self.send_post_request('/api/integration/v1/document/unassign', params=params, json=executive_user_id)


class Account(BaseResource):
    def search_my_team(self, params):
        return self.send_post_request('/api/integration/v1/account/searchMyTeam', json=params)
