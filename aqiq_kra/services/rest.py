import frappe
import json
import requests

@frappe.whitelist()
def send_request(invoice):
    
    invoice_items = frappe.db.get_all("Sales Invoice Item", {'parent': invoice}, ['item_code', 'item_name', 'rate', 'qty', 'discount_amount'])
    grand_total = frappe.db.get_value("Sales Invoice", invoice, ['grand_total'])    
    
    try:
        items = []
        exclude_from_tax = 0

        for item in invoice_items:            
            item_tax_template = frappe.db.get_value("Item Tax", {'parent': item.item_code}, ['item_tax_template'])
            tax_type, tax_rate = frappe.db.get_value("Item Tax Template Detail", {'parent': item_tax_template}, ['tax_type', 'tax_rate'])

            tax_value = 1 + (tax_rate / 100)
            unitPrice = round((item.rate * tax_value), 2)

            tax_type = tax_type.split("-", 1)
            tax_type = tax_type[0].strip()


            if tax_type == 'Exempted':

                tax_exempt_code = frappe.db.get_value('Item', {'name': item[0].item_name}, ['tax_exempt_code'])

                new_item = {
                    "productCode": tax_exempt_code,
                    "productDesc": item.item_name,
                    "quantity": item.qty,
                    "unitPrice": unitPrice,
                    "discount": item.discount_amount,
                    "taxtype": 'exempted'
                }

                exclude_from_tax = exclude_from_tax + (unitPrice * item.qty)

            else:
                new_item = {
                    "productCode": item.item_code,
                    "productDesc": item.item_name,
                    "quantity": item.qty,
                    "unitPrice": unitPrice,
                    "discount": item.discount_amount,
                    "taxtype": int(tax_rate)
                }
            
            items.append(new_item)            
        

        VAT_A_NET = (((grand_total) - exclude_from_tax) / 1.16)
        VAT_A = VAT_A_NET * 0.16

        payload = {
            "saleType":"sales",
            "cuin":"",
            "till":"1",
            "rctNo":"1245",
            "total": grand_total,
            "Paid": grand_total,
            "Payment":"Cash",
            "CustomerPIN":"A00700144557P",
            "VAT_A_Net": VAT_A_NET,
            "VAT_A": VAT_A,
            "VAT_B_Net":"0",
            "VAT_B":"0",
            "VAT_C_Net":"0",
            "VAT_C":"0",
            "VAT_D_Net":"0",
            "VAT_D":"0",
            "VAT_E_Net":"0",
            "VAT_E":"0",
            "VAT_F_Net": exclude_from_tax,
            "VAT_F":"0",
            "data": items
        }

        URL, PORT = frappe.db.get_value('Lynx Setup', {'status': 'Active'}, ['url', 'port_number'])

        url = f"{URL}:{PORT}/api/values/PostTims"

        response = requests.post(url, json=payload)
        data = json.loads(response.text)

        # Create QR Code entry
        qr_code = frappe.get_doc({
            "doctype":"QR Demo", 
            "title": data['QRCode'],
            "invoice_number": invoice
        })
        
        qr_code.insert()
        frappe.db.commit()
        
        
        # Create KRA response
        kra_response = frappe.get_doc({
            "doctype": "KRA Response",
            "response_code": data["ResponseCode"],
            "message": data["Message"],
            "tin": data["TSIN"],
            "cusn": data["CUSN"],
            "cuin": data["CUIN"],
            "qr_code": data["QRCode"],
            "signing_time": data["dtStmp"],
            "invoice_number": invoice
        })
        
        kra_response.insert()
        frappe.db.commit()
        

        return data

    except Exception as e:
        print ("\n\n\n Received error response:%s \n\n\n" %str(e))
        return e


def get_qr_code(doc):
    qr_code = frappe.db.get_value("QR Demo", {'invoice_number': doc.name}, ['qr_code'])
        
    tin, cusn, cuin, qr_code_url, signing_date = frappe.db.get_value("KRA Response", {"invoice_number": doc.name}, ["tin", "cusn", "cuin", "qr_code", "signing_time"])
        
    response = {
        "qr_code": qr_code,
        "tin": tin,
        "cusn": cusn,
        "cuin": cuin,
        "qr_code_url": qr_code_url,
        "signing_date": signing_date
    }

    return response