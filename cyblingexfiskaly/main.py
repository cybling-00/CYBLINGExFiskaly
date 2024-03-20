import frappe
import uuid
from cyblingexfiskaly.cyblingexfiskaly.doctype.fiskaly_settings.fiskaly_settings import (
    make_call,
)
import shutil
import qrcode
import os
from frappe.utils import cstr, flt


def get_currency(account):
    currency, company = frappe.db.get_value(
        "Account", account, ["account_currency", "company"]
    ) or ["", ""]
    if (not currency) and (company):
        currency = frappe.db.get_value("Company", company, "default_currency")
    return currency


def make_transaction(si, fs, tss, client):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {fs.token}",
    }
    guid = uuid.uuid4()
    url = f"{fs.base_url}/tss/{tss}/tx/{guid}?tx_revision=1"

    receipt = {}
    receipt["receipt_type"] = "RECEIPT"
    receipt["amounts_per_vat_rate"] = [
        {"vat_rate": "NORMAL", "amount": f'{flt(si.total_taxes_and_charges):.2f}'}
    ]
    amounts_per_payment_type = []
    mop = {}
    for p in si.payments:
        if p.mode_of_payment == "Cash":
            if "CASH" not in mop:
                mop["CASH"] = 0
            mop["CASH"] += flt(p.amount)
        else:
            if "NON_CASH" not in mop:
                mop["NON_CASH"] = 0
            mop["NON_CASH"] += flt(p.amount)
    for mode,payment in mop.items():
        amounts_per_payment_type.append({
            "payment_type": mode,
            "amount": f'{flt(payment):.2f}',
            "currency_code": si.currency,
        })
    receipt["amounts_per_payment_type"] = amounts_per_payment_type
    payload = {
        "schema": {
            "standard_v1": {
                "receipt": receipt
                # "order": order,
            }
        },
        "state": "ACTIVE",
        "client_id": client,
    }
    # frappe.throw(str(payload))
    response_json = make_call(url, "PUT", headers, payload)
    if response_json:
        return payload, response_json.get("_id")
    else:
        return False


def update_transaction(payload, trx_id, fs, tss, client):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {fs.token}",
    }
    url = f"{fs.base_url}/tss/{tss}/tx/{trx_id}?tx_revision=2"
    response_json = make_call(url, "PUT", headers, payload)
    if response_json:
        return payload, response_json.get("_id")
    else:
        return False


def finish_transaction(payload, trx_id, fs, tss, client):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {fs.token}",
    }
    url = f"{fs.base_url}/tss/{tss}/tx/{trx_id}?tx_revision=3"
    payload["state"] = "FINISHED"
    response_json = make_call(url, "PUT", headers, payload)
    if response_json:
        return response_json.get("qr_code_data")
    else:
        return False


def generate_qr_code(doc_name, qr_code_data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=4,
        border=4,
    )
    qr.add_data(qr_code_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    name_to_be = f"SalesInvoiceQRCode{doc_name}.png"
    img.save(name_to_be)
    site = frappe.utils.get_site_base_path()[2:]
    frappePath = cstr(os.getcwd())
    shutil.move(
        f"{frappePath}/{name_to_be}",
        f"{frappePath}/{site}/public/files/{name_to_be}",
    )
    return f"/files/{name_to_be}"


def sales_invoice_submit(self, method=None):
    if self.pos_profile:
        client = frappe.db.get_value(
            "POS Profile", self.pos_profile, "custom_client_id"
        )
        tss = frappe.db.get_value(
            "Company", self.company, "custom_technical_security_system_tss_id"
        )
        if tss and client:
            fs = frappe.get_doc("Fiskaly Settings", "Fiskaly Settings")
            payload, trx_id = make_transaction(self, fs, tss, client)
            payload, trx_id = update_transaction(payload, trx_id, fs, tss, client)
            qr_code_data = finish_transaction(payload, trx_id, fs, tss, client)
            self.custom_qr_code_data = generate_qr_code(self.name, qr_code_data)


def authenticate_admin_tss(tss_id, tss_pin):
    self = frappe.get_doc("Fiskaly Settings", "Fiskaly Settings")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {self.token}",
    }
    url = f"{self.base_url}/tss/{tss_id}/admin/auth"
    payload = {"admin_pin": tss_pin}
    response_json = make_call(url, "POST", headers, payload)


def check_tss(tss_id):
    self = frappe.get_doc("Fiskaly Settings", "Fiskaly Settings")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {self.token}",
    }
    url = f"{self.base_url}/tss/{tss_id}"
    response_json = make_call(url, "GET", headers, throw_error=False)
    if response_json:
        if response_json.get("_id"):
            if response_json.get("state") != "INITIALIZED":
                frappe.throw("TSS ID is not INITIALIZED.")
        else:
            frappe.throw("TSS ID is not correct.")
    else:
        frappe.throw("TSS ID is not correct.")


def check_client(client_id, tss_id):
    self = frappe.get_doc("Fiskaly Settings", "Fiskaly Settings")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {self.token}",
    }
    url = f"{self.base_url}/tss/{tss_id}/client/{client_id}"
    response_json = make_call(url, "GET", headers, throw_error=False)
    if response_json:
        if response_json.get("_id"):
            if response_json.get("state") != "REGISTERED":
                frappe.throw("Client ID is not REGISTERED.")
        else:
            frappe.throw("Client ID is not correct.")
    else:
        frappe.throw("Client ID is not correct.")


def company_validate(self, method=None):
    if not self.custom_technical_security_system_tss_id:
        frappe.throw("TSS ID is Mandatory.")
    if not self.custom_tss_pin:
        frappe.throw("TSS PIN is Mandatory.")
    check_tss(self.custom_technical_security_system_tss_id)
    authenticate_admin_tss(
        self.custom_technical_security_system_tss_id, self.custom_tss_pin
    )


def pos_profile_validate(self, method=None):
    if not self.custom_client_id:
        frappe.throw("Client ID is Mandatory.")
    tss_id = frappe.db.get_value(
        "Company", self.company, "custom_technical_security_system_tss_id"
    )
    if not tss_id:
        frappe.throw("TSS ID not Found in company.")
    check_client(self.custom_client_id, tss_id)
