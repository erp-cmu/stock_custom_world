# Copyright (c) 2025, IECMU and contributors
# For license information, please see license.txt
import os
import re
import shutil

import frappe
import pandas as pd
from frappe.model.document import Document
from frappe.utils import get_site_path, getdate, now

from stock_custom_world.services.sales_import import process_sale_data
from stock_custom_world.services.utils import getCustomer, getItem


def insert_file_suffix_prefix(fname, suffix=None, prefix=None):
    if prefix is None:
        prefix = now()[:19].replace("-", "_").replace(" ", "-").replace(":", "_")  # i.e. 2025_03_15-11_30_32

    if suffix is None:
        suffix = ""

    if prefix:
        prefix = prefix + "_"

    if suffix:
        suffix = "_" + suffix

    f = fname.rsplit(".", 1)
    if len(f) == 1:
        partial, extn = f[0], ""
    else:
        partial, extn = f[0], "." + f[1]
    return f"{prefix}{partial}{suffix}{extn}"


def is_already_renamed(filepath):
    fname = os.path.basename(filepath)
    result = re.search(r"^\d{4}_\d{2}_\d{2}", fname)
    return bool(result)


class WorldAutoImport(Document):
    def before_save(self):
        cur_filepath = self.import_file or None

        if cur_filepath and not is_already_renamed(cur_filepath):
            if not cur_filepath.startswith(("/private/files/", "/files/")):
                frappe.throw("File path is not valid")

            split = os.path.split(cur_filepath)
            # path_prefix with have leading "/" but not trailing "/"
            path_prefix, cur_filename = split
            # Add trailing "/" to align with the convention
            path_prefix = path_prefix + "/"

            try:
                cur_file_doc = frappe.get_last_doc(
                    "File",
                    filters={"file_url": cur_filepath},
                )
                if cur_file_doc:
                    new_filename = insert_file_suffix_prefix(cur_filename)
                    new_filepath = f"{path_prefix}{new_filename}"

                    site_path = get_site_path()  #'./SITENAME'
                    cur_filepath_site = (
                        f"{site_path}{cur_filepath}"  # The cur_filepath already contains leading "/""
                    )
                    new_filepath_site = f"{site_path}{new_filepath}"
                    shutil.copyfile(cur_filepath_site, new_filepath_site)
                    os.remove(cur_filepath_site)

                    cur_file_doc.file_url = new_filepath
                    cur_file_doc.file_name = new_filename
                    cur_file_doc.save()
                    self.import_file = cur_file_doc.file_url
                else:
                    frappe.log_error("File not found.")
            except Exception as e:
                frappe.throw(
                    f"Error handling attachment: {str(e)}",
                    "Attachment Handling Exception",
                )

    def before_submit(self):
        try:
            inject_sales_invoice(self)
            self.status = "SUCCESS"
        except Exception as e:
            frappe.throw(
                f"Error handling attachment: {str(e)}",
                "Attachment Handling Exception",
            )
            frappe.db.rollback()
            self.status = "PARTIAL_SUCCESS"
        finally:
            pass

    def start_import(self):
        try:
            progress(0, "Starting Import")
            import_from_sale_file(self)
            self.status = "SUCCESS"
            progress(100, "Finish")
        except Exception as e:
            frappe.throw(
                f"Error handling attachment: {str(e)}",
                "Attachment Handling Exception",
            )
            frappe.db.rollback()
            self.status = "PENDING"
        finally:
            pass
        return self


@frappe.whitelist()
def form_start_import(doc_name: str):
    return frappe.get_doc("World Auto Import", doc_name).start_import()


def progress(prog: int, desc: str):
    frappe.publish_realtime("data_import_progress", {"progress": prog, "description": desc})


def import_from_sale_file(doc):
    filepath = frappe.get_site_path() + doc.import_file
    if not os.path.exists(filepath):
        frappe.throw(title="Error", msg="This file does not exist")

    try:
        dfr = pd.read_excel(filepath)
    except Exception:
        frappe.throw(title="Error", msg="Cannot read excel file.")

    # Process raw data
    source = doc.source
    if not source:
        frappe.throw(title="Error", msg="Cannot find source")

    dft = process_sale_data(dfr, source)

    def createSalesDetails(r):
        customer = getCustomer(customer_name=r["customer_ref"]) or doc.default_customer
        item_code, _ = getItem(item_code=r["item_code_ref"])
        is_pass = 1 if item_code is not None else 0

        params = dict(
            doctype="World Auto Import Details",
            is_pass=is_pass,
            customer=customer,
            item_code=item_code,
            warehouse=doc.default_warehouse,
            #
            order_number=r["order_number"],
            customer_ref=r["customer_ref"],
            item_ref=r["item_ref"],
            item_ref_code=r["item_code_ref"],
            item_ref_name=r["item_name_ref"],
            qty=r["qty"],
            rate=r["rate"],
            amount=r["amount"],
            order_discount=r["order_discount"],
            order_shipping=r["order_shipping"],
            order_total=r["order_total"],
            order_due_date=getdate(r["order_due_date"]),
        )
        row = frappe.get_doc(params)
        doc.append("sales_details", row)

    dft.apply(createSalesDetails, axis=1)


from collections import defaultdict


def inject_sales_invoice(self):
    sdGroupDict = defaultdict(list)
    for sd in self.sales_details:
        sdGroupDict[sd.order_number].append(dict(order_number=sd.order_number, data=sd))
    sdGroupDict = dict(sdGroupDict)

    for _, sdArr in sdGroupDict.items():
        sd0 = sdArr[0]["data"]  # First sales details to give the sales-invoice info
        paramsSalesInvoice = dict(
            doctype="Sales Invoice",
            customer=sd0.customer,
            due_date=getdate(sd0, parse_day_first=False),
            update_stock=1,
            set_wareouse=self.default_warehouse,
            is_pos=1,
            pos_profile="",
            discount_amount=sd0.order_discount,
            customer_order_number=sd0.order_number,
            customer_external_source=self.source,
        )
        salesInv = frappe.get_doc(paramsSalesInvoice)

        # Add items
        for _sd in sdArr:
            sd = _sd["data"]

            _, uom = getItem(sd.item_code)
            if uom is None:
                uom = "Nos"

            paramsItem = dict(
                doctype="Sales Invoice Item",
                item_name=sd.item_name,
                item_code=sd.item_code,  # If this is wrong, the stock ledger will not be updated.
                uom=uom,
                qty=sd.qty,
                rate=sd.rate,
                amount=sd.amount,
                warehouse=sd.warehouse,
                expense_account="Cost of Goods Sold - WG",
                income_account="Sales - WG",
                # price_list_rate = sd.rate
            )
            salesInvItem = frappe.get_doc(paramsItem)
            salesInv.append("items", salesInvItem)

        # Add payment
        paramsPayment = dict(
            doctype="Sales Invoice Payment",
            mode_of_payment="Cash",
            type="Cash",
            account="Cash - WG",
            base_amount=sd.order_total,
            amount=sd.order_total,
        )
        payment = frappe.get_doc(paramsPayment)
        salesInv.append("payments", payment)
        #
        salesInv.save()
        salesInv.submit()
