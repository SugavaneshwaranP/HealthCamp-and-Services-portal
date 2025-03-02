from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import requests

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
OGD_API_KEY = "579b464db66ec23bdd00000165283796b058430f763ff16f065640b0"

INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
    "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
    "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
    "Uttarakhand", "West Bengal"
]

# Static data with state-specific health schemes
LOCATION_DATA = {
    "Tamil Nadu": {
        "vaccination": "Newborn Vaccination Reminders (NIS):\n- At Birth (within 24 hrs): BCG, OPV 0, Hepatitis B at Tamil Nadu government hospitals.\n- 6 Weeks: OPV 1, Pentavalent 1, RVV 1, PCV 1.\n- 10 Weeks: OPV 2, Pentavalent 2, RVV 2.\n- 14 Weeks: OPV 3, Pentavalent 3, RVV 3, PCV 2.",
        "schemes": "Chief Minister’s Comprehensive Health Insurance Scheme (CMCHIS):\n- Coverage: Up to ₹5 lakh per family per year.\n- Eligibility: Families earning < ₹72,000 annually.\n- Benefits: Cashless treatment for 1,016+ procedures at empanelled hospitals.",
        "camps": "Free health camps organized monthly in Chennai and rural Tamil Nadu (static fallback).",
        "elderly": "Tamil Nadu Health Systems Project offers specialized elderly care services."
    },
    "Kerala": {
        "vaccination": "Newborn Vaccination Reminders (NIS):\n- At Birth (within 24 hrs): BCG, OPV 0, Hepatitis B at PHCs.\n- 6 Weeks: OPV 1, Pentavalent 1, RVV 1, PCV 1.\n- 10 Weeks: OPV 2, Pentavalent 2, RVV 2.\n- 14 Weeks: OPV 3, Pentavalent 3, RVV 3, PCV 2.\nNote: High coverage in Kerala.",
        "schemes": "Karunya Arogya Suraksha Padhathi (KASP):\n- Coverage: Up to ₹5 lakh per family per year.\n- Eligibility: BPL families, APL with conditions.\n- Benefits: Covers 1,573 procedures, 3-day pre/15-day post-hospitalization.",
        "camps": "Weekly health camps in Kochi and rural Kerala (static fallback).",
        "elderly": "Special elderly care programs at Kerala Health Centers."
    },
    "Maharashtra": {
        "vaccination": "Newborn Vaccination Reminders (NIS):\n- At Birth (within 24 hrs): BCG, OPV 0, Hepatitis B in Mumbai/Pune clinics.\n- 6 Weeks: OPV 1, Pentavalent 1, RVV 1.\n- 10 Weeks: OPV 2, Pentavalent 2, RVV 2.\n- 14 Weeks: OPV 3, Pentavalent 3, RVV 3.",
        "schemes": "Mahatma Jyotiba Phule Jan Arogya Yojana (MJPJAY):\n- Coverage: Up to ₹1.5 lakh per family per year (₹5 lakh for PM-JAY integration).\n- Eligibility: BPL and distressed farmers.\n- Benefits: Free treatment at empanelled hospitals.",
        "camps": "Health camps every weekend in Mumbai slums (static fallback).",
        "elderly": "Elderly wellness programs in Maharashtra government hospitals."
    },
    "default": {
        "vaccination": "Newborn Vaccination Reminders (NIS):\n- At Birth (within 24 hrs): BCG, OPV 0, Hepatitis B per NIS.\n- 6 Weeks: OPV 1, Pentavalent 1, RVV 1, PCV 1 (where available).\n- 10 Weeks: OPV 2, Pentavalent 2, RVV 2.\n- 14 Weeks: OPV 3, Pentavalent 3, RVV 3, PCV 2 (where available).",
        "schemes": "Ayushman Bharat PM-JAY:\n- Coverage: Up to ₹5 lakh per family per year.\n- Eligibility: 10.74 crore poor families (SECC 2011 data).\n- Benefits: Cashless secondary/tertiary care at empanelled hospitals.",
        "camps": "Periodic health camps organized by local health authorities (static fallback).",
        "elderly": "Basic elderly care as per National Programme for Health Care of the Elderly."
    }
}

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT NOT NULL,
                 email TEXT UNIQUE NOT NULL,
                 password TEXT NOT NULL)''')
    try:
        c.execute("ALTER TABLE users ADD COLUMN location TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def fetch_ogd_data(state):
    api_url = "https://api.data.gov.in/resource/d4e26461-7690-4d9b-8f9b-74aa8e8ca1f2"
    params = {
        "api-key": OGD_API_KEY.strip(),
        "format": "json",
        "filters[state]": state,
        "limit": 100
    }
    
    try:
        response = requests.get(api_url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            records = data.get("records", [])
            camps = f"{len(records)} health facilities available for potential health camps in {state} (Source: OGD Hospital Directory)."
        else:
            error_msg = response.json().get("error", f"Status {response.status_code}")
            camps = f"Unable to fetch camp data for {state}: {error_msg}"
    except requests.RequestException as e:
        print(f"OGD API Exception: {e}")
        camps = f"Unable to fetch camp data for {state}: Network error"

    static_data = LOCATION_DATA.get(state, LOCATION_DATA["default"])
    return {
        "schemes": static_data["schemes"],
        "camps": camps,
        "elderly": static_data["elderly"]
    }

def fetch_vaccination_data(state):
    api_url = "https://api.data.gov.in/resource/d4e26461-7690-4d9b-8f9b-74aa8e8ca1f2"
    params = {
        "api-key": OGD_API_KEY.strip(),
        "format": "json",
        "filters[state]": state,
        "limit": 100
    }
    
    try:
        response = requests.get(api_url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            records = data.get("records", [])
            facility_count = len(records)
            vacc = f"{LOCATION_DATA.get(state, LOCATION_DATA['default'])['vaccination']}\nAvailable at: {facility_count} health facilities in {state} (Source: OGD Hospital Directory)."
        else:
            error_msg = response.json().get("error", f"Status {response.status_code}")
            vacc = f"{LOCATION_DATA.get(state, LOCATION_DATA['default'])['vaccination']}\nFacility data unavailable: {error_msg}"
    except requests.RequestException as e:
        print(f"OGD API Exception: {e}")
        vacc = f"{LOCATION_DATA.get(state, LOCATION_DATA['default'])['vaccination']}\nFacility data unavailable: Network error"
    return vacc

def fetch_health_schemes(state):
    # Placeholder for real-time API (none available yet)
    # Using Hospital Directory as context for scheme implementation
    api_url = "https://api.data.gov.in/resource/d4e26461-7690-4d9b-8f9b-74aa8e8ca1f2"
    params = {
        "api-key": OGD_API_KEY.strip(),
        "format": "json",
        "filters[state]": state,
        "limit": 100
    }
    
    try:
        response = requests.get(api_url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            records = data.get("records", [])
            facility_count = len(records)
            schemes = f"{LOCATION_DATA.get(state, LOCATION_DATA['default'])['schemes']}\nImplemented at: {facility_count} empanelled health facilities in {state} (Source: OGD Hospital Directory)."
        else:
            error_msg = response.json().get("error", f"Status {response.status_code}")
            schemes = f"{LOCATION_DATA.get(state, LOCATION_DATA['default'])['schemes']}\nFacility data unavailable: {error_msg}"
    except requests.RequestException as e:
        print(f"OGD API Exception: {e}")
        schemes = f"{LOCATION_DATA.get(state, LOCATION_DATA['default'])['schemes']}\nFacility data unavailable: Network error"
    return schemes

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form['email']
            password = generate_password_hash(request.form['password'])
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                     (name, email, password))
            conn.commit()
            conn.close()
            flash('Signup successful! Please login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists!')
            return redirect(url_for('signup'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            flash('Login successful!')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        flash('Please login first!')
        return redirect(url_for('login'))
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT name, location FROM users WHERE id = ?", (session['user_id'],))
    user = c.fetchone()
    conn.close()
    if request.method == 'POST':
        location = request.form['location']
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("UPDATE users SET location = ? WHERE id = ?", (location, session['user_id']))
        conn.commit()
        conn.close()
        flash('Location updated successfully!')
        return redirect(url_for('dashboard'))
    location_data = fetch_ogd_data(user[1]) if user[1] else LOCATION_DATA["default"]
    return render_template('dashboard.html', 
                         name=user[0], 
                         location=user[1], 
                         states=INDIAN_STATES, 
                         location_data=location_data)

@app.route('/vaccination')
def vaccination():
    if 'user_id' not in session:
        flash('Please login first!')
        return redirect(url_for('login'))
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT name, location FROM users WHERE id = ?", (session['user_id'],))
    user = c.fetchone()
    conn.close()
    vaccination_data = fetch_vaccination_data(user[1]) if user[1] else LOCATION_DATA["default"]["vaccination"]
    return render_template('vaccination.html', 
                         name=user[0], 
                         location=user[1], 
                         vaccination_data=vaccination_data)

@app.route('/health_schemes')
def health_schemes():
    if 'user_id' not in session:
        flash('Please login first!')
        return redirect(url_for('login'))
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT name, location FROM users WHERE id = ?", (session['user_id'],))
    user = c.fetchone()
    conn.close()
    schemes_data = fetch_health_schemes(user[1]) if user[1] else LOCATION_DATA["default"]["schemes"]
    return render_template('health_schemes.html', 
                         name=user[0], 
                         location=user[1], 
                         schemes_data=schemes_data)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully!')
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)