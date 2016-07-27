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

import cachetclient.cachet as cachet
import json

ENDPOINT = 'http://status.domain.tld/api/v1'
API_TOKEN = 'token'

# /ping
ping = cachet.Ping(endpoint=ENDPOINT)
print(ping.get())

# /version
version = cachet.Version(endpoint=ENDPOINT)
print(version.get())

# /components
components = cachet.Components(endpoint=ENDPOINT, api_token=API_TOKEN)
new_component = json.loads(components.post(name='Test component',
                                           status=1,
                                           description='Test component'))
print(components.get(id=new_component['id']))
print(components.put(id=new_component['id'], description='Updated component'))
components.delete(id=new_component['id'])

# /components/groups
groups = cachet.Groups(endpoint=ENDPOINT, api_token=API_TOKEN)
new_group = json.loads(groups.post(name='Test group'))
print(groups.get(id=new_group['id']))
print(groups.put(id=new_group['id'], name='Updated group'))
groups.delete(new_group['id'])

# /incidents
incidents = cachet.Incidents(endpoint=ENDPOINT, api_token=API_TOKEN)
new_incident = json.loads(incidents.post(name='Test incident',
                                         message='Houston, we have a problem.',
                                         status=1))
print(incidents.get(id=new_incident['id']))
print(incidents.put(id=new_incident['id'],
                    message="There's another problem, Houston."))
incidents.delete(id=new_incident['id'])
