import requests
import json


class PowerDNS:
    def __init__(self, base_url, apikey):
        self.base_url = base_url
        self.apikey = apikey

    def _query(self, uri, method, kwargs = {}):
        headers = {
            'X-API-Key': self.apikey,
            'Accept': 'application/json'
        }

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
        return self._query("/servers/localhost/zones/%s." % domain, "GET")

    def set_records(self, domain, rrsets):
        return self._query("/servers/localhost/zones/%s" % domain, "PATCH", {
            'rrsets': rrsets
        })

    def search(self, q, max = 100, object_type = "all"):
        return self._query("/servers/localhost/search-data?q={0}&max={1}&object_type={2}".format(q, max, object_type), "GET")
