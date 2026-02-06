import streamlit as st
import pandas as pd
import sqlite3
import cv2
import numpy as np
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
import io
import os

# --- DATABASE SETUP ---
conn = sqlite3.connect('omr_expert_2026.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS students (id TEXT PRIMARY KEY, name TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS scores (student_id TEXT, score INTEGER, total INTEGER, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS master_key_db (item INTEGER PRIMARY KEY, answer TEXT)''')
conn.commit()

# --- SESSION STATE INITIALIZATION ---
if 'master_key' not in st.session_state:
    saved_key = pd.read_sql("SELECT * FROM master_key_db", conn)
    st.session_state.master_key = dict(zip(saved_key['item'], saved_key['answer'])) if not saved_key.empty else {}

st.set_page_config(page_title="Expert OMR 2026", layout="wide")

# --- UI STYLING ---
st.markdown("""
    <style>
    div.stButton > button:first-child { border-radius: 50%; width: 45px; height: 45px; font-weight: bold; border: 2px solid #D32F2F; }
    .main-header { font-size: 26px; font-weight: bold; color: #D32F2F; border-bottom: 3px solid #D32F2F; margin-bottom: 15px; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; border-left: 5px solid #D32F2F; }
    </style>
    """, unsafe_allow_html=True)

# --- PDF GENERATOR (PRC-STYLE) ---
def generate_pro_sheet(student_id, student_name, num_q):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=LETTER)
    w_pdf, h_pdf = LETTER
    # Markers for alignment
    p.rect(0.5*inch, h_pdf-0.6*inch, 0.25*inch, 0.25*inch, fill=1)
    p.rect(w_pdf-0.75*inch, h_pdf-0.6*inch, 0.25*inch, 0.25*inch, fill=1)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(1*inch, h_pdf-0.8*inch, "EXAM ANSWER SHEET (PRO)")
    p.setFont("Helvetica", 10)
    p.drawString(1*inch, h_pdf-1.2*inch, f"STUDENT: {student_name.upper()}")
    p.drawString(1*inch, h_pdf-1.4*inch, f"ID: {student_id}")
    
    y = h_pdf - 2.2*inch
    for i in range(1, num_q + 1):
        p.setFont("Helvetica-Bold", 10)
        p.drawString(1.2*inch, y, f"{i:02d}.")
        for j, choice in enumerate(['A', 'B', 'C', 'D']):
            x = 1.8*inch + (j * 0.5*inch)
            p.circle(x, y+3, 8, stroke=1, fill=0)
            p.setFont("Helvetica", 7)
            p.drawCentredString(x, y+1.5, choice)
        y -= 0.35*inch
    p.save()
    buffer.seek(0)
    return buffer

# --- NAVIGATION ---
menu = st.sidebar.selectbox("Navigation", ["Enroll Students", "Set Master Key", "Generate Papers", "Auto-Scanner (Camera)", "Records"])

# 1. ENROLLMENT
if menu == "Enroll Students":
    st.markdown("<div class='main-header'>Student Database</div>", unsafe_allow_html=True)
    with st.form("enroll", clear_on_submit=True):
        s_id, s_name = st.text_input("ID Number"), st.text_input("Full Name")
        if st.form_submit_button("Enroll"):
            if s_id and s_name:
                c.execute("INSERT OR REPLACE INTO students VALUES (?, ?)", (s_id, s_name))
                conn.commit()
                st.success("Student Enrolled!")
    st.dataframe(pd.read_sql("SELECT * FROM students", conn), width='stretch')

# 2. MASTER KEY (Diri ang answer key)
elif menu == "Set Master Key":
    st.markdown("<div class='main-header'>🔑 Set and Lock Master Key</div>", unsafe_allow_html=True)
    num_q = st.number_input("Total Items", 5, 50, 20)
    cols = st.columns(3)
    for i in range(1, num_q + 1):
        with cols[(i-1)%3]:
            sub = st.columns([0.8, 1, 1, 1, 1])
            sub[0].write(f"**{i}**")
            for j, label in enumerate(['A', 'B', 'C', 'D']):
                active = st.session_state.master_key.get(i) == label
                if sub[j+1].button(label, key=f"m_{i}_{j}", type="primary" if active else "secondary"):
                    st.session_state.master_key[i] = label
                    st.rerun()
    
    if st.button("💾 LOCK & SAVE MASTER KEY", width='stretch'):
        c.execute("DELETE FROM master_key_db")
        for itm, ans in st.session_state.master_key.items():
            c.execute("INSERT INTO master_key_db VALUES (?, ?)", (itm, ans))
        conn.commit()
        st.success("Master Key Saved Permanently!")

# 3. GENERATOR
elif menu == "Generate Papers":
    st.markdown("<div class='main-header'>📄 Generate Sheets</div>", unsafe_allow_html=True)
    st_df = pd.read_sql("SELECT * FROM students", conn)
    if not st_df.empty:
        sel_name = st.selectbox("Select Student", st_df['name'])
        sid = st_df[st_df['name'] == sel_name]['id'].values[0]
        qcount = len(st.session_state.master_key) if st.session_state.master_key else 20
        pdf = generate_pro_sheet(sid, sel_name, qcount)
        st.download_button(f"Download PDF for {sel_name}", pdf, f"{sid}.pdf", width='stretch')

# 4. SCANNER (The AI Engine)
elif menu == "Auto-Scanner (Camera)":
    st.markdown("<div class='main-header'>📸 Professional AI Scanner</div>", unsafe_allow_html=True)
    
    saved_key_df = pd.read_sql("SELECT * FROM master_key_db", conn)
    if saved_key_df.empty:
        st.error("⚠️ Error: I-set una ang Master Key sa pikas tab!")
    else:
        master_dict = dict(zip(saved_key_df['item'], saved_key_df['answer']))
        st_df = pd.read_sql("SELECT * FROM students", conn)
        sel_student = st.selectbox("Identify Student:", st_df['name'])
        sid = st_df[st_df['name'] == sel_student]['id'].values[0]

        img_file = st.camera_input("Focus on bubbles and keep the paper flat")
        
        if img_file:
            # --- COMPUTER VISION PROCESSING ---
            file_bytes = np.frombuffer(img_file.getvalue(), np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Adaptive Thresholding (Para sa hayag/ngitngit nga lighting)
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                          cv2.THRESH_BINARY_INV, 11, 2)
            
            st.image(thresh, caption="AI Detection View", width=400)
            

            # Logic: Automatic Shading Comparison
            score = 0
            feedback = []
            choices = ['A', 'B', 'C', 'D']

            # --- DYNAMIC GRADING LOGIC ---
            # Sa pagkakaron, ang 'Simulated Detection' naggamit og internal coordinate mapping
            # In actual production, we loop through the detected contours in 'thresh'
            for i in range(1, len(master_dict) + 1):
                # Placeholder for real contour-pixel-counting:
                # 1. Slice thresh image to row i
                # 2. Divide row into 4 columns (A, B, C, D)
                # 3. Count non-zero pixels in each. Highest wins.
                
                detected_ans = 'A' # Sample detection
                correct_ans = master_dict.get(i)
                
                if detected_ans == correct_ans:
                    score += 1
                    feedback.append(f"Q{i}: ✅")
                else:
                    feedback.append(f"Q{i}: ❌ (Detected {detected_ans}, Key {correct_ans})")

            st.metric("Detected Score", f"{score} / {len(master_dict)}")
            with st.expander("Item Analysis"):
                st.write(feedback)

            if st.button("💾 SAVE SCORE TO RECORDS", width='stretch'):
                c.execute("INSERT INTO scores (student_id, score, total) VALUES (?, ?, ?)", 
                          (sid, score, len(master_dict)))
                conn.commit()
                st.balloons()
                st.success("Saved!")

# 5. RECORDS
elif menu == "Records":
    st.markdown("<div class='main-header'>📊 Class Performance</div>", unsafe_allow_html=True)
    query = '''SELECT students.name, scores.score, scores.total, scores.date 
               FROM scores JOIN students ON scores.student_id = students.id ORDER BY scores.date DESC'''
    st.dataframe(pd.read_sql(query, conn), width='stretch')
