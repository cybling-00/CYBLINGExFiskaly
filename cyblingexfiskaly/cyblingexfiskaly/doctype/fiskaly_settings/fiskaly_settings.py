# Copyright (c) 2024, Codes Soft and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests
import json
import uuid


class FiskalySettings(Document):
    def validate(self):
        get_and_set_token(self)


def make_call(url, method, headers=None, payload=None, throw_error=True):
    if payload:
        payload = json.dumps(payload)
    response = requests.request(method, url, headers=headers, data=payload)
    if response.status_code == 200:
        # frappe.log_error("Fiskaly Call Passed", f"URL:{url},\nMethod:{method},\nHeaders:{headers},\nPayload:{payload},\nText:{response.text}")
        return response.json()
    else:
        # frappe.log_error("Fiskaly Call failed", f"URL:{url},\nMethod:{method},\nHeaders:{headers},\nPayload:{payload},\nReason:{response.reason},\nText:{response.text}")
        if throw_error:
            frappe.throw(str(response.text))
            return False
        else:
            return {}


def get_and_set_token(self=None):
    save = False
    if not self:
        self = frappe.get_doc("Fiskaly Settings", "Fiskaly Settings")
        save = True
    headers = {"Content-Type": "application/json"}
    self.token = ""
    self.organization_id = ""
    payload = {"api_key": self.api_key, "api_secret": self.api_secret}
    response_json = make_call(f"{self.base_url}/auth", "POST", headers, payload)
    if response_json:
        token = response_json.get("access_token")
        if token:
            self.token = token
            if save:
                self.save()
            # headers["Authorization"] = f"Bearer {token}"
