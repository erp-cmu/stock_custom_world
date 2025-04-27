import frappe


def getUOM(item_name):
    stock_uom = frappe.db.get_value("Item", item_name, "stock_uom")
    return stock_uom


def getItem(
    item_code,
    item_name="",
    also_search_item_name=False,
):
    item_name_pk = frappe.db.exists("Item", {"item_code": item_code})

    if item_name_pk:
        return item_name_pk, getUOM(item_name_pk)

    # NOTE: Since item name is not guarantee unique, I might ended getting the wrong or duplicated items which
    # can be problematic when importing sales invoice. Threrefore, this search will only be activated on demand.
    if also_search_item_name:
        item_name_pk = frappe.db.exists("Item", {"item_name": item_name})
        if item_name_pk:
            return item_name_pk, getUOM(item_name_pk)

    return None, None


def getCustomer(customer_name):
    customer_name_pk = frappe.db.exists("Customer", {"name": customer_name})
    if customer_name_pk:
        return customer_name_pk
    return None
