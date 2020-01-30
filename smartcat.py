# -*- coding: utf-8 -*-
import json
import requests
from config import *
import base64


def project_stats():
    token = (SMARTCAT_API_USERNAME + ':' + SMARTCAT_API_PASSWORD).encode('ascii')
    auth = 'Basic {0}'.format(base64.b64encode(token).decode())
    headers = {'Accept': 'application/json', 'Authorization': auth}
    url = '{0}/v1/project/{1}'.format(SMARTCAT_API_BASE_URL, SMARTCAT_PROJECT_ID)
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return json.loads(response.content.decode('utf-8'))
    else:
        return None
