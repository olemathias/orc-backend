#!/usr/bin/env python

import requests
import string
import random

from getpass import getpass
orc_password = getpass()

vm_name = input("VM Name: ")

auth_form = {
    "username": "olemathias",
    "password": orc_password
}

# Add error check
jwt_token = requests.post('http://localhost:8000/api-token-auth/', json = auth_form).json()['access']

username = "techo"
password = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(10))

userdata = [
    "useradd -s /usr/bin/bash -m -p $(openssl passwd -1 {}) {}".format(password, username),
    "usermod -aG sudo {}".format(username),
    "sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config",
    "echo '{} ALL=(ALL) NOPASSWD: ALL' | EDITOR='tee -a' visudo".format(username),
    "systemctl restart sshd"
]

vm = {
    "name":vm_name,
    "platform": 2,
    "network": 2,
    "vm_template": 2,
    "memory": 2,
    "cpu_cores": 1,
    "os_disk": 16,
    "userdata": userdata
}

# Add error check
vm_id = requests.post('http://localhost:8000/vm/', json = vm, headers={"Authorization": "JWT " + jwt_token}).json()['id']
vm = requests.get('http://localhost:8000/vm/{}'.format(vm_id), headers={"Authorization": "JWT " + jwt_token}).json()

print("")
print("Username: {}".format(username))
print("Password: {}".format(password))
print("FQDN: {}".format(vm['fqdn']))
