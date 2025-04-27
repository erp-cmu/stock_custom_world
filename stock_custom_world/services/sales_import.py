import re
from datetime import datetime

import frappe
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
    # Format columns in general
    dfr.columns = [col.strip() for col in dfr.columns]

    # Format currency columns
    cols = ["ยอดเงิน(บาท)", "ส่วนลด(บาท)", "ค่าจัดส่ง(บาท)"]
    for col in cols:
        dfr[col] = dfr[col].astype(str)
        dfr[col] = dfr[col].str.replace(",", "")
        dfr[col] = dfr[col].str.replace("-", "0")
        dfr[col] = dfr[col].astype(float)
        dfr[col] = dfr[col].fillna(0)

    # Order number
    cols = ["Order No."]
    for col in cols:
        dfr[col] = dfr[col].astype(str)

    # Remove customer title
    dfr["ชื่อลูกค้า"] = dfr["ชื่อลูกค้า"].apply(lambda s: re.sub(r"^คุณ", "", s))

    # Date column
    cols = ["วันที่สั่งซื้อ", "วันที่ชำระเงิน"]
    for col in cols:
        dfr[col] = dfr[col].apply(lambda x: datetime.strptime(x, "%d/%m/%Y %H:%M"))

    # Util functions
    def extractNameQty(s: str):
        numberStr = re.findall(r"\((\d+)\)", s)
        s_sub = re.sub(r"\s+\((\d+)\)", "", s)
        return s_sub, int(numberStr[0])

    def formatItemStr(s: str):
        items = s.split(",")
        items = [it.strip() for it in items]
        datas = []
        for it in items:
            res = extractNameQty(it)
            data = dict(text=res[0], qty=res[1])
            datas.append(data)
        return datas

    def processRow(_row):
        item_codes = formatItemStr(_row["รหัสสินค้า (จำนวนชิ้น)"])
        item_names = formatItemStr(_row["สินค้า (จำนวนชิ้น)"])
        #
        order_no = _row["Order No."]
        customer_ref = _row["ชื่อลูกค้า"]
        order_due_date = _row["วันที่ชำระเงิน"].strftime("%Y-%m-%d")
        order_total = float(_row["ยอดเงิน(บาท)"])
        order_shipping = float(_row["ค่าจัดส่ง(บาท)"])
        order_discount = float(_row["ส่วนลด(บาท)"])
        #
        n_qty = 0
        for it in item_codes:
            n_qty = n_qty + it["qty"]
        #
        sub_total = order_total + order_discount - order_shipping
        item_rate_avg = sub_total / n_qty
        #
        dataArr = []
        for dCode, dName in zip(item_codes, item_names):
            item_code_ref = dCode["text"]
            item_name_ref = dName["text"]
            qty = dCode["qty"]
            # Fill in info
            data = dict(
                order_no=order_no,
                customer_ref=customer_ref,
                item_code_ref=item_code_ref,
                item_name_ref=item_name_ref,
                item_ref=f"{item_code_ref} : {item_name_ref}",
                qty=qty,
                rate=item_rate_avg,
                amount=qty * item_rate_avg,
                order_discount=order_discount,
                order_shipping=order_shipping,
                order_total=order_total,
                order_due_date=order_due_date,
            )
            dataArr.append(data)
        return pd.DataFrame.from_dict(dataArr)

    dfArr = dfr.apply(processRow, axis=1)
    dft = pd.concat(dfArr.values).reset_index(drop=True)
    return dft
