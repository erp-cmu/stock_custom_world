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
    process_sale_data()

    row = frappe.get_doc({"doctype": "World Auto Import Details", "customer": "CUS001", "item": "ITEM001"})
    doc.append("sales_details", row)
    pass


def inject_sales_invoice(self):
    for row in self.sales_details:
        frappe.msgprint(row.name)
    pass
