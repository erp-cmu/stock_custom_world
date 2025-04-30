import frappe
from erpnext.stock.doctype.item.item import Item


class CustomItem(Item):
    def validate(self):
        super().validate()
        self.custom_validation()

    def custom_validation(self):
        # Do not allow multiple external codes from the same source.
        sources = []
        for row in self.custom_external_item_codes:
            sources.append(row.source)

        dup = find_duplicates(sources)

        if len(dup) > 0:
            frappe.throw(f"Duplicated external item codes from source(s): {', '.join(dup)}")


def find_duplicates(arr):
    count = {}
    duplicates = []
    for item in arr:
        count[item] = count.get(item, 0) + 1
    for item, cnt in count.items():
        if cnt > 1:
            duplicates.append(item)
    return duplicates
