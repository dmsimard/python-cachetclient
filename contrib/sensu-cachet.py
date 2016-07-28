#!/usr/bin/env python
#   Copyright Red Hat, Inc. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#

# This script is a Sensu handler meant to accept data from Sensu as stdin in
# order to post events to a Cachet instance.

# Requirements:
# - pip install python-cachetclient
# - A cachet.json configuration file in /etc/sensu/conf.d/cachet.json:
#   {
#     "endpoint": "http://status.domain.tld/api/v1",
#     "api_token": "token",
#     "uchiwa": "http://uchiwa.tld/"
#   }
# - A 'datacenter' parameter in Sensu clients (to be able to craft Uchiwa links
#   properly). TODO: Make this optional somehow
#

import os
import sys
import json

import cachetclient.cachet as cachet

# Load configuration
CONFIG_FILE = '/etc/sensu/conf.d/cachet.json'
if os.path.isfile(CONFIG_FILE):
    with open(CONFIG_FILE) as f:
        CONFIG = json.loads(f.read())
else:
    print('Unable to find configuration file: %s' % CONFIG_FILE)
    sys.exit(1)

try:
    ENDPOINT = CONFIG['endpoint']
    API_TOKEN = CONFIG['api_token']
    UCHIWA = CONFIG['uchiwa']
except KeyError as e:
    print("Unable to find required configuration key: %s" % str(e))
    sys.exit(1)

# Map of "nagios-like"/Sensu event statuses to Cachet statuses and incident
# names:
#   - https://docs.cachethq.io/docs/incident-statuses
#   - https://docs.cachethq.io/docs/component-statuses
STATUS = {
    'incident': {
        'create': 2, # Identified
        'resolve': 4, # Fixed
        'flapping': 1, # Investigating
        'unknown': 1 # Investigating
    },
    'component': {
        'create': 3,  # Partial outage
        'resolve': 1,  # Operational
        'flapping': 3,  # Partial outage
        'unknown': 3  # Partial outage
    },
    'action': {
        'create': "Incident: {0}",
        'resolve': "Resolved incident: {0}",
        'flapping': "Incident: {0}",
        'unknown': "Incident: {0}"
    }
}

# Incident templates
NEW_INCIDENT = """
### {component}
Our monitoring infrastructure detected an issue for this service.

The details of the problem are as follows:
```
# Host: {host}
# Check: {check}
{output}
```

More details are available on the [monitoring dashboard]({check_url}).
"""

RESOLVED_INCIDENT = """
### {component}
Our monitoring infrastructure considers an issue resolved for this service.

The details of the resolution are as follows:
```
# Host: {host}
# Check: {check}
{output}
```

More details are available on the [monitoring dashboard]({check_url}).
"""


def create_incident(**kwargs):
    """
    Creates an incident
    """
    incidents = cachet.Incidents(endpoint=ENDPOINT, api_token=API_TOKEN)
    if 'component_id' in kwargs:
        return incidents.post(name=kwargs['name'],
                              message=kwargs['message'],
                              status=kwargs['status'],
                              component_id=kwargs['component_id'],
                              component_status=kwargs['component_status'])
    else:
        return incidents.post(name=kwargs['name'],
                              message=kwargs['message'],
                              status=kwargs['status'])


def incident_exists(name, message, status):
    """
    Check if an incident with these attributes already exists
    """
    incidents = cachet.Incidents(endpoint=ENDPOINT)
    all_incidents = json.loads(incidents.get())
    for incident in all_incidents['data']:
        if name == incident['name'] and \
           status == incident['status'] and \
           message.strip() == incident['message'].strip():
            return True
    return False


def get_component(id):
    """
    Gets a Cachet component by id
    """
    components = cachet.Components(endpoint=ENDPOINT)
    component = json.loads(components.get(id=id))
    return component['data']


if __name__ == '__main__':
    # Load Sensu event from STDIN
    try:
        data = json.load(sys.stdin)
    except Exception as e:
        print("Unable to parse JSON: {0}".format(str(e)))
        sys.exit(1)

    # Map the data we're interested in
    host_params = ['action', 'client', 'check']
    params = {
        param: data.get(param, None)
        for param in host_params
    }

    # Sensu client event data
    host = params['client']['name']
    # datacenter is a custom client attribute in order to be able to generate
    # Uchiwa links properly
    datacenter = params['client']['datacenter']

    # Sensu check event data
    check = params['check']['name']
    output = params['check']['output']
    # component_id is a custom check attribute to maps to a Cachet component
    # Retrieve the real component from Cachet based on that ID
    component = params['check']['component_id']
    component = get_component(component)

    check_url = "{0}/#/client/{1}/{2}?check={3}".format(UCHIWA,
                                                        datacenter,
                                                        host,
                                                        check)

    if params['action'] in STATUS['action']:
        incident_name = STATUS['action'][params['action']].format(check)
        incident_status = STATUS['incident'][params['action']]
        component_status = STATUS['component'][params['action']]
    else:
        incident_name = STATUS['action']['unknown'].format(check)
        incident_status = STATUS['incident']['unknown']
        component_status = STATUS['component']['unknown']

    if params['action'] == 'resolve':
        message = RESOLVED_INCIDENT.format(host=host,
                                           check=check,
                                           component=component['name'],
                                           output=output,
                                           check_url=check_url)
    else:
        message = NEW_INCIDENT.format(host=host,
                                      check=check,
                                      component=component['name'],
                                      output=output,
                                      check_url=check_url)

    # If an incident with the same properties already exist, we can stop here
    # This probably means an ongoing issue, Sensu will send 'create' events
    # every time.
    if incident_exists(incident_name, message, incident_status):
        sys.exit(0)

    # Otherwise, create an incident and update the component if is it known.
    if component is not None:
        create_incident(name=incident_name,
                        message=message,
                        status=incident_status,
                        component_id=component['id'],
                        component_status=component_status)
