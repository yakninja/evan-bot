# -*- coding: utf-8 -*-

"""
smartcat.web
~~~~~~~~~~~~

Missing smartcat API functionality augmented by web requests
This can stop working at any time. Needs admin username/password to function

"""

import logging
import pickle

import requests

from .api import SmartCAT, SmartcatException


class SmartCATWeb(object):
    BASE_URL = 'https://smartcat.ai'

    def __init__(self, session_filename,
                 admin_email, admin_password,
                 api_username, api_password, api_server_url=SmartCAT.SERVER_EUROPE):
        """
        Constructor

        :param admin_email: SmartCAT admin email.
        :param admin_password: SmartCAT admin password.
        """
        self.session_filename = session_filename
        self.admin_email = admin_email
        self.admin_password = admin_password
        self.api = SmartCAT(api_username, api_password, api_server_url)

        try:
            with open(self.session_filename, 'rb') as f:
                self.session = pickle.load(f)
        except FileNotFoundError:
            self.session = requests.Session()
            self.session.headers.update({'Accept': 'application/json'})

    def dump_session(self):
        with open(self.session_filename, 'wb') as f:
            pickle.dump(self.session, f)

    def sign_in(self):
        logging.info('Logging in as %s' % self.admin_email)
        post_data = {
            'eMail': self.admin_email,
            'password': self.admin_password,
            'rememberMe': True,
            'allowPartialLogin': False,
            'accountName': None,
            'usePersonalAccount': None,
            'backUrl': None
        }
        url = self.BASE_URL + '/api/auth/SignInUser'
        response = self.session.post(url, post_data)
        if response.status_code != 200:
            logging.warning('Could not sign in as %s' % self.admin_email)
            raise SmartcatException(code=response.status_code, message=response.content)

        logging.info(response.content)
        self.dump_session()
        return response

    def get_workflow_stages(self, project_id, document_list_id):
        url = self.BASE_URL + \
              '/api/WorkflowAssignments/%s/GetWorkflowStages?documentListId=%s' % (project_id, document_list_id)
        response = self.session.get(url)
        if response.status_code == 403:
            logging.info(response.content)
            self.sign_in()
            return self.session.get(url)
        else:
            return response

    def create_document_list_id(self, document_id):
        url = self.BASE_URL + '/api/WorkflowAssignments/CreateDocumentListId'
        response = self.session.post(url, json=[document_id])
        if response.status_code == 403:
            logging.info(response.content)
            self.sign_in()
            return self.session.post(url, json=[document_id])
        else:
            return response

