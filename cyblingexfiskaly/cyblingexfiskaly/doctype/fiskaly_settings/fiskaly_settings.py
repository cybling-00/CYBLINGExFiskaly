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


@frappe.whitelist()
def create_client_id(company):
    if company:
        tss_id, tss_pin = frappe.db.get_value(
            "Company",
            company,
            ["custom_technical_security_system_tss_id", "custom_tss_pin"],
        ) or [None, None]
        if not tss_id:
            frappe.throw("TSS ID not Found in company.")
        self = frappe.get_doc("Fiskaly Settings", "Fiskaly Settings")
        authenticate_admin(self, tss_id, tss_pin)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        guid = uuid.uuid4()
        url = f"{self.base_url}/tss/{tss_id}/client/{guid}"
        payload = {"serial_number": f"ERS {guid}"}
        response_json = make_call(url, "PUT", headers, payload)
        if response_json:
            return response_json.get("_id")
    return False


def authenticate_admin(self, tss_id, tss_pin):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {self.token}",
    }
    url = f"{self.base_url}/tss/{tss_id}/admin/auth"
    payload = {"admin_pin": tss_pin}
    response_json = make_call(url, "POST", headers, payload)

@frappe.whitelist()
def create_tss_id(admin_pin = "1234567890"):
    self = frappe.get_doc("Fiskaly Settings", "Fiskaly Settings")
    headers = {"Content-Type": "application/json", "Authorization": f'Bearer {self.token}'}
    guid = uuid.uuid4()
    url = f"{self.base_url}/tss/{guid}"
    payload = {"metadata": {}}
    response_json = make_call(url,"PUT", headers, payload)
    if response_json:
        personalize_tss_id(self, response_json.get("_id"), "UNINITIALIZED")
        change_admin_pin(self, response_json.get("_id"), response_json.get("admin_puk"), admin_pin)
        authenticate_admin(self, response_json.get("_id"), admin_pin)
        personalize_tss_id(self, response_json.get("_id"), "INITIALIZED")
        return response_json.get("_id")
    return False

def change_admin_pin(self, tss_id, admin_puk, admin_pin):
    headers = {"Content-Type": "application/json", "Authorization": f'Bearer {self.token}'}
    url = f"{self.base_url}/tss/{tss_id}/admin"
    payload = {
        "admin_puk": admin_puk,
        "new_admin_pin": admin_pin
    }
    response_json = make_call(url,"PATCH", headers, payload)

def personalize_tss_id(self, tss_id, state):
    headers = {"Content-Type": "application/json", "Authorization": f'Bearer {self.token}'}
    url = f"{self.base_url}/tss/{tss_id}"
    payload = {"state": state}
    response_json = make_call(url,"PATCH", headers, payload)