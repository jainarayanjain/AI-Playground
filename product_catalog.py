import streamlit as st
import mysql.connector
import os
import json
from collections import defaultdict
from openai import OpenAI

# ---------------- CONFIG ----------------

DB_CONFIG = {
    "host": "",
    "port": "",
    "database": "",
    "user": "",
    "password": ""
}

client = OpenAI(
    api_key=""
)
MODEL = "gpt-4o"

# ---------------- FUNCTIONS ----------------

def fetch_rows(query):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


# ✅ KEEPING GROUPING BY PRODUCT_ID (as requested)
def group_products(rows):
    grouped = defaultdict(lambda: {"sku": "", "images": []})

    for pid, sku, type_, url in rows:
        grouped[pid]["sku"] = sku
        grouped[pid]["images"].append(url)

    return grouped


# ✅ FIXED: Proper image input format
# def analyze(prompt, images):
#
#     content = [
#         {
#             "type": "input_text",
#             "text": prompt
#         }
#     ]
#
#     # Add images correctly
#     for img in images:
#         content.append({
#             "type": "input_image",
#             "image_url": img
#         })
#
#     response = client.responses.create(
#         model=MODEL,
#         temperature=0,
#         input=[
#             {
#                 "role": "user",
#                 "content": content
#             }
#         ]
#     )
#
#     return response.output_text

def analyze(prompt, images):

    content = [
        {
            "type": "input_text",
            "text": prompt
        }
    ]

    for img in images:
        content.append({
            "type": "input_image",
            "image_url": img
        })

    response = client.responses.create(
        model=MODEL,
        temperature=0,
        input=[
            {
                "role": "user",
                "content": content
            }
        ],
        text={                      # ✅ THIS is correct for Responses API
            "format": {
                "type": "json_object"
            }
        }
    )

    return response.output_text
# ---------------- UI ----------------

st.set_page_config(layout="wide")
st.title("🧠 Footwear AI Classification Tool")

col1, col2 = st.columns(2)

with col1:
    sql_query = st.text_area(
        "SQL Query",
        height=250,
        placeholder="Paste your SQL here..."
    )

with col2:
    prompt_template = st.text_area(
        "Prompt Template",
        height=250,
        placeholder="Paste your classification prompt here..."
    )

run_btn = st.button("Run Analysis")

# ---------------- RUN ----------------

if run_btn:
    if not sql_query or not prompt_template:
        st.warning("SQL and Prompt both required")
    else:
        try:
            rows = fetch_rows(sql_query)
            grouped = group_products(rows)

            for pid, info in grouped.items():

                st.divider()
                st.subheader(f"Product ID: {pid} | SKU: {info['sku']}")

                # Show images
                st.write("Images:")
                cols = st.columns(len(info["images"]))
                for i, img in enumerate(info["images"]):
                    cols[i].image(img, width=150)

                final_prompt = prompt_template + f"\n\nProduct ID: {pid}"

                with st.spinner("Analyzing with AI..."):
                    result = analyze(final_prompt, info["images"])

                st.write("### Raw AI Output")
                st.code(result)

                # Try parsing JSON safely
                try:
                    parsed = json.loads(result)

                    st.write("### Parsed Result")
                    st.json(parsed)

                except Exception:
                    st.error("AI did not return valid JSON.")

        except Exception as e:
            st.error(str(e))