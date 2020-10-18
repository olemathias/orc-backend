import requests
import json


class PowerDNS:
    def __init__(self, base_url, apikey, domain):
        self.base_url = base_url
        self.apikey = apikey
        self.domain = "{}.".format(domain)

    def _query(self, uri, method, kwargs):
        headers = {
            'X-API-Key': self.apikey,
            'Accept': 'application/json'
        }

        print(self.base_url+uri)
        if method == "GET":
            request = requests.get(self.base_url+uri, headers=headers)
        elif method == "POST":
            request = requests.post(self.base_url+uri, headers=headers, data=kwargs)
        elif method == "PUT":
            request = requests.put(self.base_url+uri, headers=headers, data=kwargs)
        elif method == "PATCH":
            request = requests.patch(self.base_url+uri, headers=headers, json=kwargs)
        elif method == "DELETE":
            request = requests.delete(self.base_url+uri, headers=headers)

        if request.headers.get('content-type') == 'application/json':
            return request.json()
        return None

    def get_zone(self, domain):
        return self._query("/servers/localhost/zones/%s." % self.domain, "GET")

    def set_records(self, rrsets):
        return self._query("/servers/localhost/zones/%s" % self.domain, "PATCH", {
            'rrsets': rrsets
        })
