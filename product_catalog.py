import streamlit as st
import mysql.connector
import os
import json
from collections import defaultdict
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd
from io import BytesIO

# ---------------- CONFIG ----------------

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT")),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
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


def group_products(rows):
    grouped = defaultdict(lambda: {"sku": "", "images": [], "handle": ""})
    for pid, sku, type_, url, handle in rows:
        grouped[pid]["sku"] = sku
        grouped[pid]["images"].append(url)
        grouped[pid]["handle"] = handle
    return grouped


def analyze(prompt, images):
    content = [{"type": "input_text", "text": prompt}]
    for img in images:
        content.append({"type": "input_image", "image_url": img})

    response = client.responses.create(
        model=MODEL,
        temperature=0,
        input=[{
            "role": "user",
            "content": content
        }],
        text={"format": {"type": "json_object"}}
    )

    return response.output_text


# ---------------- SESSION STATE ----------------

if "all_results" not in st.session_state:
    st.session_state.all_results = []

if "grouped_data" not in st.session_state:
    st.session_state.grouped_data = None

if "raw_outputs" not in st.session_state:
    st.session_state.raw_outputs = {}

if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False


# ---------------- UI ----------------

st.set_page_config(layout="wide")
st.title("🧠 Footwear AI Classification Tool")

col1, col2 = st.columns(2)

with col1:
    sql_query = st.text_area("SQL Query", height=250)

with col2:
    prompt_template = st.text_area("Prompt Template", height=250)

run_btn = st.button("Run Analysis", type="primary")


# ---------------- RUN ANALYSIS (FAULT TOLERANT) ----------------

if run_btn:
    st.session_state.all_results = []
    st.session_state.grouped_data = None
    st.session_state.raw_outputs = {}
    st.session_state.analysis_done = False

    if not sql_query or not prompt_template:
        st.warning("SQL and Prompt both required")
    else:
        try:
            rows = fetch_rows(sql_query)
            grouped = group_products(rows)
            st.session_state.grouped_data = grouped

            total = len(grouped)
            progress_bar = st.progress(0)

            for index, (pid, info) in enumerate(grouped.items()):



                try:
                    final_prompt = prompt_template + f"\n\nProduct name: {info['handle']}"
                    result = analyze(final_prompt, info["images"])


                    # Store raw output
                    st.session_state.raw_outputs[pid] = result

                    try:
                        parsed = json.loads(result)

                        row_data = {
                            "product_id": pid,
                            "sku": info["sku"],
                            "handle": info["handle"],
                            "status": "success"
                        }

                        for key, value in parsed.items():
                            row_data[key] = value

                        st.session_state.all_results.append(row_data)

                    except Exception:
                        st.session_state.all_results.append({
                            "product_id": pid,
                            "sku": info["sku"],
                            "handle": info["handle"],
                            "status": "invalid_json"
                        })

                except Exception as e:
                    # Catch API failure or any unexpected error
                    st.session_state.all_results.append({
                        "product_id": pid,
                        "sku": info["sku"],
                        "handle": info["handle"],
                        "status": "failed",
                        "error": str(e)
                    })

                progress_bar.progress((index + 1) / total)

            st.session_state.analysis_done = True

        except Exception as e:
            st.error(f"Unexpected Error: {str(e)}")


# ---------------- DISPLAY RESULTS ----------------

if st.session_state.analysis_done and st.session_state.grouped_data:

    for pid, info in st.session_state.grouped_data.items():

        st.divider()
        st.subheader(f"Product ID: {pid} | SKU: {info['sku']}")

        # Show images
        st.write("Images:")
        cols = st.columns(len(info["images"]))
        for i, img in enumerate(info["images"]):
            cols[i].image(img, width=150)

        # Show raw + parsed output if available
        if pid in st.session_state.raw_outputs:
            st.write("### Raw AI Output")
            st.code(st.session_state.raw_outputs[pid])

            try:
                parsed = json.loads(st.session_state.raw_outputs[pid])
                st.write("### Parsed Result")
                st.json(parsed)
            except:
                st.warning("Invalid JSON returned.")

    # -------- Excel Download --------
    if st.session_state.all_results:

        df = pd.DataFrame(st.session_state.all_results)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Results")

        output.seek(0)

        st.download_button(
            label="📥 Download Excel",
            data=output,
            file_name="footwear_classification_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )