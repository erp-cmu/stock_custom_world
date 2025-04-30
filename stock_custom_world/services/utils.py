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
    items = frappe.db.get_all("External Item Codes", filters=filters, fields=["*"])
    if len(items) == 0:
        return None, None

    if len(items) > 1:
        parents = [it.parent for it in items]
        parents_str = ", ".join(parents)
        frappe.msg(f"Found duplicated external item code for {item_code_ref} in {parents_str}.")

    item_code, uom = getItemInternal(items[0].parent)
    return item_code, uom


def getItem(
    item_code,
    source="",
):
    item_name_pk, uom = getItemInternal(item_code=item_code)

    if item_name_pk:
        return item_name_pk, uom

    # Search for external item name
    item_name_pk, uom = getItemExternal(item_code_ref=item_code, source=source)
    if item_name_pk:
        return item_name_pk, uom

    return None, None


def updateOrCreateExternalItemCode(item_code, item_code_ref, item_name_ref, source, remove_duplication=False):
    # See if the external item code already exists
    filters = dict(external_item_code=item_code_ref, parenttype="Item", parent=item_code, source=source)
    extItemCodeName = frappe.db.exists("External Item Codes", filters)

    # If external item code already exists, only update the item name, if needed.
    if extItemCodeName:
        if item_name_ref != "":
            frappe.db.set_value("External Item Codes", extItemCodeName, "external_item_name", item_name_ref)
        return

    # External item code does not exist.
    # Check if there is already existing external item with the same source or not.
    filters = dict(parenttype="Item", parent=item_code, source=source)
    extItems = frappe.db.get_all("External Item Codes", filters=filters, fields=["*"])
    if len(extItems) > 0:
        # Remove existing data first
        for row in extItems:
            remove_child_row("Item", item_code, "custom_external_item_codes", row.name)

    # Check for duplication in other items
    filters = dict(
        external_item_code=item_code_ref,
        parenttype="Item",
        parent=["!=", item_code],
        source=source,
    )
    extItems = frappe.db.get_all("External Item Codes", filters=filters, fields=["*"])

    # If duplication is found, handle it
    if len(extItems) > 0:
        # Give warning
        if not remove_duplication:
            parentNames = [it.parent for it in extItems]
            parentNamesStr = ", ".join(parentNames)
            frappe.throw(
                f"Found item {parentNamesStr} with similar external item (code {source} : {item_code_ref}) to {item_code}."
            )
        # Remove external item code from other items
        else:
            for row in extItems:
                remove_child_row("Item", row.parent, "custom_external_item_codes", row.name)

    # Now we can create new external item code
    itemDoc = frappe.get_doc("Item", item_code)
    itemDoc.append(
        "custom_external_item_codes",
        dict(external_item_code=item_code_ref, external_item_name=item_name_ref, source=source),
    )
    itemDoc.save()


def remove_child_row(parent_doctype, parent_name, child_table_field, child_row_name):
    # Load the parent document
    doc = frappe.get_doc(parent_doctype, parent_name)

    # Find the child row by name
    row_to_remove = None
    for row in getattr(doc, child_table_field):
        if row.name == child_row_name:
            row_to_remove = row
            break

    if row_to_remove:
        # Remove the child row
        doc.remove(row_to_remove)
        # Save the parent document
        doc.save()


def getCustomer(customer_name):
    customer_name_pk = frappe.db.exists("Customer", {"name": customer_name})
    if customer_name_pk:
        return customer_name_pk
    return None
