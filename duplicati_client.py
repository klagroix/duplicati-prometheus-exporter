import requests
import urllib
from urllib.parse import urljoin


def build_url(base, path):
    return urljoin(base, path)

class Duplicati:
    def __init__(self, base_url, verify=True):
        self.base_url = base_url
        self.verify = verify
        self.token = None

    def login(self):
        if self.token is not None:
            return self.token

        print("Logging into Duplicati at {0}".format(self.base_url))
        r = requests.get(self.base_url, verify=self.verify, allow_redirects=True)
        r.raise_for_status() # Should probably add better error handling here

        xsrf_token = urllib.parse.unquote(r.cookies["xsrf-token"])
        if xsrf_token is None:
            raise Exception("Unable to get xsrf-token from cookies")

        self.token = xsrf_token

        print("Logged in")
        return 

    def get_backups_json(self):
        self.login() # Doesn't hurt to call multiple times

        backup_list_url = build_url(self.base_url, "api/v1/backups")
        cookies = {"xsrf-token": self.token}
        headers = {"X-XSRF-TOKEN": self.token}

        r = requests.get(backup_list_url, headers=headers, cookies=cookies, verify=self.verify)
        r.encoding='utf-8-sig'
        r.raise_for_status()

        return r.json()
    
    def get_backup_names(self):
        backup_info = self.get_backups_json()

        backups = []
        for backup_obj in backup_info:
            backups.append(backup_obj["Backup"]["Name"])

        return backups



