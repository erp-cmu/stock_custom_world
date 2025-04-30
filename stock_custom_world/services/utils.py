import frappe


def getUOM(item_name):
    stock_uom = frappe.db.get_value("Item", item_name, "stock_uom")
    return stock_uom


def getItemInternal(
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


def getItemExternal(item_code_ref, source):
    # See if the external item code already exists
    filters = dict(external_item_code=item_code_ref, source=source)
    items = frappe.db.get_all("External Item Codes", filters=filters)
    if len(items) == 0:
        return None

    if len(items) > 1:
        parents = [it.parent for it in items]
        parents_str = ", ".join(parents)
        frappe.msg(f"Found duplicated external item code for {item_code_ref} in {parents_str}.")

    return getItemInternal(items[0].parent)


def getItem(
    item_code,
    item_code_ref="",
    source="",
):
    item_name_pk, uom = getItemInternal(item_code=item_code)

    if item_name_pk:
        return item_name_pk, uom

    # Search for external item name
    getItemExternal(item_code_ref=item_code_ref, source=source)
    return None, None


def updateOrCreateExternalItemCode(item_name, item_code_ref, item_name_ref, source):
    # See if the external item code already exists
    filters = dict(external_item_code=item_code_ref, parenttype="Item", parent=item_name, source=source)
    extItemCodeName = frappe.db.exists("External Item Codes", filters)

    # If external item code already exists, only update the item name
    if extItemCodeName and item_name_ref != "":
        frappe.db.set_value("External Item Codes", extItemCodeName, "external_item_name", item_name_ref)
        return

    # External item code does not exist
    # First, check for duplication
    filters = dict(
        external_item_code=item_code_ref,
        parenttype="Item",
        parent=["!=", item_name],
        source=source,
    )
    itemName = frappe.db.exists("External Item Codes", filters)
    if itemName:
        frappe.throw(f"Found item {itemName} with similar external item code {source} : {item_code_ref}")

    # No duplication, create new external item code
    doc = frappe.get_doc("Item", item_name)
    doc.append(
        "External Item Codes",
        dict(external_item_code=item_code_ref, external_item_name=item_name_ref, source=source),
    )


def getCustomer(customer_name):
    customer_name_pk = frappe.db.exists("Customer", {"name": customer_name})
    if customer_name_pk:
        return customer_name_pk
    return None
