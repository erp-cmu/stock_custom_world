import json
from datetime import time, timedelta

import frappe
import numpy as np
import pandas as pd


def process_sale_data(dfr: pd.DataFrame, source: str):
    if source == "MyOrder":
        dfr = process_sale_data_my_order(dfr)
    elif source == "Lazada":
        pass
    elif source == "Shopee":
        pass
    else:
        frappe.throw(title="Error", msg="Incorrect Source")

    return dfr


def process_sale_data_my_order(dfr):
    return dfr
