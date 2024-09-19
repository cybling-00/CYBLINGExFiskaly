import frappe
import uuid
from cyblingexfiskaly.cyblingexfiskaly.doctype.fiskaly_settings.fiskaly_settings import (
	make_call,
)
import shutil
import qrcode
import os
import ast
from frappe.utils import cstr, flt, cint, get_timestamp, now
from erpnext.controllers.taxes_and_totals import temporary_flag, get_itemised_tax_breakup_header, get_itemised_tax_breakup_data

def get_itemised_tax_breakup(doc):
	itemised_tax_data = [] 
	if not doc.taxes:
		return
	tax_accounts = []
	for tax in doc.taxes:
		if getattr(tax, "category", None) and tax.category == "Valuation":
			continue
		if tax.description not in tax_accounts:
			tax_accounts.append(tax.description)
	with temporary_flag("company", doc.company):
		# headers = get_itemised_tax_breakup_header(doc.doctype + " Item", tax_accounts)
		itemised_tax_data = get_itemised_tax_breakup_data(doc)
		# get_rounded_tax_amount(itemised_tax_data, doc.precision("tax_amount", "taxes"))
		# update_itemised_tax_data(doc)
	return itemised_tax_data

def get_currency(account):
	currency, company = frappe.db.get_value(
		"Account", account, ["account_currency", "company"]
	) or ["", ""]
	if (not currency) and (company):
		currency = frappe.db.get_value("Company", company, "default_currency")
	return currency

def get_custom_fiskaly_vat_title(account, company):
	template = None
	data = frappe.db.sql(f"""Select p.custom_fiskaly_vat_title 
	From `tabItem Tax Template` p inner join `tabItem Tax Template Detail` c 
	on p.name = c.parent where c.tax_type = '{account}' and p.company = '{company}' """)
	if data:
		template = data[0][0]
	return template

def make_transaction(si, fs, tss, client):
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {fs.token}",
	}
	guid = uuid.uuid4()
	url = f"{fs.base_url}/tss/{tss}/tx/{guid}?tx_revision=1"
	receipt = {}
	receipt["receipt_type"] = "RECEIPT"
	amounts_per_vat_rate = {}
	for row in si.taxes:
		template = get_custom_fiskaly_vat_title(row.account_head, si.company)
		if template:
			if template not in amounts_per_vat_rate:
				amounts_per_vat_rate[template] = 0
			amounts_per_vat_rate[template] += row.tax_amount
	receipt["amounts_per_vat_rate"] = [{"vat_rate": vat_rate, "amount": f'{flt(amount):.2f}'} for vat_rate, amount in amounts_per_vat_rate.items()]
	amounts_per_payment_type = []
	mop = {}
	for p in si.payments:
		if p.type == "Cash":
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
		return response_json, response_json.get("qr_code_data")
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
			data, qr_code_data = finish_transaction(payload, trx_id, fs, tss, client)
			self.custom_fiskaly_data = cstr(data)
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

def check_cash_register(client_id, tss_id):
	self = frappe.get_doc("Fiskaly Settings", "Fiskaly Settings")
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {self.token}",
	}
	url = f"{self.dsfinvk_base_url}/cash_registers/{client_id}"
	response_json = make_call(url, "GET", headers, throw_error=False)
	if response_json:
		if response_json.get("tss_id"):
			if response_json.get("tss_id") != tss_id:
				frappe.throw("Cash Register's TSS ID Does not match With Company's TSS ID.")
		else:
			frappe.throw(cstr(response_json.get("message")))
	else:
		frappe.throw("Cash Register is not Found.")

def company_validate(self, method=None):
	if self.custom_technical_security_system_tss_id:
		check_tss(self.custom_technical_security_system_tss_id)
		authenticate_admin_tss(
			self.custom_technical_security_system_tss_id, self.custom_tss_pin
		)

def pos_profile_validate(self, method=None):
	if self.custom_client_id:
		tss_id = frappe.db.get_value(
			"Company", self.company, "custom_technical_security_system_tss_id"
		)
		if not tss_id:
			frappe.throw("TSS ID not Found in company.")
		check_client(self.custom_client_id, tss_id)
		check_cash_register(self.custom_client_id, tss_id)

def make_cash_point_closings_transaction(pos_cs, fs, tss, client):
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {fs.token}",
	}
	guid = uuid.uuid4()
	url = f"{fs.dsfinvk_base_url}/cash_point_closings/{guid}"
	if pos_cs.pos_transactions:
		transaction_export_id = 1
		export_creation_date = cstr(cint(get_timestamp(pos_cs.posting_date)))
		payload_head = {
			"export_creation_date": export_creation_date,
			# "first_transaction_export_id": cstr(cint(get_timestamp(pos_cs.pos_transactions[0].get("creation")))),
			# "last_transaction_export_id": cstr(cint(get_timestamp(pos_cs.pos_transactions[-1].get("creation")))),
			"first_transaction_export_id": transaction_export_id,
			"last_transaction_export_id": transaction_export_id,
		}
		payload_cash_statement = {"payment" : {}}
		transactions = []
		for t in pos_cs.pos_transactions:
			transaction = {"head":{}, "data":{"lines": []}, "security":{}}
			tax_type = "Exclusive"
			si = frappe.get_doc("Sales Invoice", t.sales_invoice)
			if si.custom_fiskaly_data:
				for row in si.taxes:
					if row.included_in_print_rate:
						tax_type = "Inclusive"
				itemised_tax_breakup = get_itemised_tax_breakup(si)
				si_fiskaly_data = ast.literal_eval(cstr(si.custom_fiskaly_data))
				transaction["head"]["tx_id"] = si_fiskaly_data.get("_id")
				transaction["head"]["closing_client_id"] = client
				transaction["head"]["transaction_export_id"] = transaction_export_id
				transaction["head"]["number"] = t.idx
				transaction["head"]["type"] = "Beleg"
				transaction["head"]["storno"] = False
				transaction["head"]["timestamp_start"] = cstr(cint(get_timestamp(si.posting_date)))
				transaction["head"]["timestamp_end"] = export_creation_date
				transaction["data"]["full_amount_incl_vat"] = si.grand_total
				for row in si.items:
					line = {"item" : {}, "business_case": {"amounts_per_vat_id": []}}
					line["business_case"]["type"]  = frappe.db.get_value("Item", row.item_code, "custom_fiskaly_item_type")
					amounts_per_vat_id = {}
					tax_rate = 0
					tax_amount = 0
					taxable_amount = 0
					for itb in itemised_tax_breakup:
						if itb.get("item") == row.item_code:
							taxable_amount+=itb.get("taxable_amount") or 0
							for taxes_row in si.taxes:
								taxes_dict = itb.get(taxes_row.description) or {}
								tax_rate+=taxes_dict.get("tax_rate") or 0 
								tax_amount+=taxes_dict.get("tax_amount") or 0
    
					amounts_per_vat_id["vat_definition_export_id"] = row.idx
					if tax_type == "Inclusive":
						amounts_per_vat_id["incl_vat"] = taxable_amount + tax_amount
					elif tax_type == "Exclusive":
						amounts_per_vat_id["excl_vat"] = taxable_amount
						amounts_per_vat_id["vat"] = tax_amount
					line["business_case"]["amounts_per_vat_id"].append(amounts_per_vat_id)
					line["lineitem_export_id"]  = row.idx
					line["storno"]  = False
					line["text"] = row.item_name or row.item_code
					line["item"]["number"]  = cstr(row.item_name or row.item_code).upper()[0]
					line["item"]["quantity"]  = row.qty
					line["item"]["price_per_unit"]  = row.rate
					transaction["data"]["lines"].append(line)
				transaction["security"]["tss_tx_id"] = si_fiskaly_data.get("_id")
				transactions.append(transaction)
		payload_cash_statement["payment"]["full_amount"] = pos_cs.grand_total
		payload_cash_statement["payment"]["cash_amount"] = pos_cs.grand_total
		payload_cash_statement["payment"]["cash_amounts_by_currency"] = [{"currency_code": "USD", "amount": pos_cs.grand_total}]
		payload_cash_statement["payment"]["payment_types"] = [{"type": "Bar", "currency_code": "USD", "amount": pos_cs.grand_total}]
		payload = {
			"client_id": client,
			"cash_point_closing_export_id": transaction_export_id,
			"head": payload_head,
			"cash_statement": payload_cash_statement,
			"transactions": transactions,
		}
		frappe.log_error(title="POS Closing Api Call",message=f"Payload: \n{payload}")
		response_json = make_call(url, "PUT", headers, payload)
		if response_json:
			return response_json
		else:
			return False
	else:
		return False

def delete_cash_point_closings_transaction(pos_cs, fs):
	fiskaly_resonse = ast.literal_eval(cstr(pos_cs.custom_fiskaly_response))
	headers = {
		# "Content-Type": "application/json",
		"Authorization": f"Bearer {fs.token}",
	}
	if fiskaly_resonse:
		closing_id = fiskaly_resonse.get("closing_id")
		url = f"{fs.dsfinvk_base_url}/cash_point_closings/{closing_id}"
		response_json = make_call(url, "DELETE", headers)
		if response_json:
			return response_json
		else:
			return False
	else:
		return False

def pos_closing_shift_submit(self, method=None):
	if self.pos_profile and self.company:
		client = frappe.db.get_value(
			"POS Profile", self.pos_profile, "custom_client_id"
		)
		tss = frappe.db.get_value(
			"Company", self.company, "custom_technical_security_system_tss_id"
		)
		if tss and client:
			fs = frappe.get_doc("Fiskaly Settings", "Fiskaly Settings")
			self.custom_fiskaly_response = cstr(make_cash_point_closings_transaction(self, fs, tss, client))

def pos_closing_shift_cancel(self, method=None):
	if self.custom_fiskaly_response:
		fs = frappe.get_doc("Fiskaly Settings", "Fiskaly Settings")
		self.custom_fiskaly_response = cstr(delete_cash_point_closings_transaction(self, fs))